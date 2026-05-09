# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_days, now_datetime, today

# HOOKS — called by Frappe event system


def on_fiscal_year_save(doc, method):
    """
    Triggered on Fiscal Year after_insert and on_update.
    Decides whether to calculate immediately or mark as not-due.
    Does NOT block saving — fires background job and returns instantly.
    """
    # Only act if the status is blank or failed (avoid re-triggering on every save)
    current_status = doc.get("opening_balance_status") or ""
    if current_status in ("In Progress", "Completed"):
        return

    _trigger_or_schedule(doc.name, doc.year_start_date)


def on_gl_entry_submit(doc, method):
    """
    Triggered on GL Entry submit AND cancel.
    If the posting date falls BEFORE any completed fiscal year's start date
    for this company, mark that fiscal year as dirty so it gets recalculated.
    """
    posting_date = getdate(doc.posting_date)

    # Find all fiscal years for this company that start AFTER this posting date
    # and are already calculated (Completed) — those opening balances are now stale
    affected = frappe.db.sql(
        """
        SELECT fy.name
        FROM `tabFiscal Year` fy
        INNER JOIN `tabFiscal Year Company` fyc ON fyc.parent = fy.name
        WHERE fyc.company        = %s
          AND fy.year_start_date > %s
          AND fy.opening_balance_status = 'Completed'
    """,
        (doc.company, posting_date),
        as_dict=True,
    )

    for fy in affected:
        frappe.db.set_value(
            "Fiscal Year", fy.name, "opening_balance_dirty", 1, update_modified=False
        )


# SCHEDULED JOBS — registered in hooks.py scheduler_events → daily


def daily_check_pending_fiscal_years():
    """
    Runs daily.
    Finds fiscal years created in advance (Pending - Not Due) whose start date
    has now arrived, and fires their opening balance calculation.
    """
    today_date = getdate(today())

    pending = frappe.db.get_all(
        "Fiscal Year",
        filters={
            "opening_balance_status": "Pending - Not Due",
            "year_start_date": ("<=", today_date),
        },
        fields=["name"],
    )

    if not pending:
        return

    for fy in pending:
        frappe.db.set_value(
            "Fiscal Year",
            fy.name,
            "opening_balance_status",
            "Pending",
            update_modified=False,
        )
        _enqueue_calculation(fy.name)

    frappe.db.commit()


def recalculate_dirty_fiscal_years():
    """
    Runs daily.
    Finds fiscal years where opening_balance_dirty = 1, meaning a backdated
    GL entry was posted that affects the stored opening balances.
    Triggers recalculation for each.
    """
    dirty = frappe.db.get_all(
        "Fiscal Year",
        filters={
            "opening_balance_dirty": 1,
            "opening_balance_status": ("not in", ["In Progress", "Pending"]),
        },
        fields=["name"],
    )

    for fy in dirty:
        _enqueue_calculation(fy.name)


# BACKGROUND JOB — the actual calculation


def calculate_opening_balances(fiscal_year_name):
    """
    Background job (long queue).
    For each company in the fiscal year, sums all GL entries up to the day
    before the fiscal year start date and stores debit/credit totals per
    account in the opening_balances JSON field.

    Storage format:
    {
        "Company A": {
            "Cash - A":     {"debit": 50000.0, "credit": 10000.0},
            "Debtors - A":  {"debit": 20000.0, "credit":  5000.0},
            ...
        },
        "Company B": { ... }
    }
    """
    frappe.db.set_value(
        "Fiscal Year",
        fiscal_year_name,
        "opening_balance_status",
        "In Progress",
        update_modified=False,
    )
    frappe.db.commit()

    try:
        fy = frappe.get_doc("Fiscal Year", fiscal_year_name)
        cutoff_date = add_days(getdate(fy.year_start_date), -1)

        companies = [row.company for row in fy.get("included_companies", [])]

        if not companies:
            # No companies linked — store empty and mark complete
            _save_result(fiscal_year_name, {})
            return

        opening_balances = {}

        for company in companies:
            rows = frappe.db.sql(
                """
                    SELECT
                        account,
                        SUM(debit_in_company_currency) - SUM(credit_in_company_currency) AS net
                    FROM `tabGL Entry`
                    WHERE company      = %s
                    AND posting_date <= %s
                    GROUP BY account
                    HAVING (SUM(debit_in_company_currency) - SUM(credit_in_company_currency)) != 0
                """,
                (company, cutoff_date),
                as_dict=True,
            )

            opening_balances[company] = {
                row.account: float(row.net or 0) for row in rows
            }

        _save_result(fiscal_year_name, opening_balances)

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Opening Balance Calculation Failed — {fiscal_year_name}",
        )
        frappe.db.set_value(
            "Fiscal Year",
            fiscal_year_name,
            "opening_balance_status",
            "Failed",
            update_modified=False,
        )
        frappe.db.commit()


# PUBLIC READER — called by Balance Sheet report


def get_opening_balances_for_company(fiscal_year_name, company):
    """
    Returns the stored opening balance map for a single company.

    Return value format: { account_name: {"debit": x, "credit": y} }
    Returns empty dict if:
      - No data stored yet
      - Status is not Completed
      - Any error during parse
    Caller should fall back to full-history GL scan when empty dict is returned.
    """
    if not fiscal_year_name or not company:
        return {}

    stored = frappe.db.get_value(
        "Fiscal Year",
        fiscal_year_name,
        ["opening_balances", "opening_balance_status"],
        as_dict=True,
    )

    if not stored or stored.get("opening_balance_status") != "Completed":
        return {}

    try:
        all_balances = frappe.parse_json(stored.get("opening_balances") or "{}")
        return all_balances.get(company, {})
    except Exception:
        return {}


# INTERNAL HELPERS


def _trigger_or_schedule(fiscal_year_name, year_start_date):
    today_date = getdate(today())
    fy_start = getdate(year_start_date)

    if today_date < fy_start:
        # FY created in advance — cannot calculate yet, will be picked up by daily job
        frappe.db.set_value(
            "Fiscal Year",
            fiscal_year_name,
            "opening_balance_status",
            "Pending - Not Due",
            update_modified=False,
        )
    else:
        # FY has started — enqueue immediately
        frappe.db.set_value(
            "Fiscal Year",
            fiscal_year_name,
            "opening_balance_status",
            "Pending",
            update_modified=False,
        )
        _enqueue_calculation(fiscal_year_name)


def _enqueue_calculation(fiscal_year_name):
    frappe.enqueue(
        "verp_staffing.accounts.utils.fiscal_year_opening_balance.calculate_opening_balances",
        fiscal_year_name=fiscal_year_name,
        queue="long",
        timeout=3600,
        now=False,  # always async — never blocks UI
        job_id=f"ob_calc_{fiscal_year_name}",  # prevent duplicate jobs
    )


def _save_result(fiscal_year_name, opening_balances):
    frappe.db.set_value(
        "Fiscal Year",
        fiscal_year_name,
        {
            "opening_balances": frappe.as_json(opening_balances),
            "opening_balance_status": "Completed",
            "opening_balance_calculated_at": now_datetime(),
            "opening_balance_dirty": 0,
        },
        update_modified=False,
    )
    frappe.db.commit()

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_fiscal_years_for_company(doctype, txt, searchfield, start, page_len, filters):
    """Function fetches all fiscal years for a given company"""
    company = filters.get("company") if filters else None
    if not company:
        return []
    return frappe.db.sql("""
        SELECT fy.name
        FROM `tabFiscal Year` fy
        INNER JOIN `tabFiscal Year Company` fyc ON fyc.parent = fy.name
        WHERE fyc.company = %s
          AND fy.name LIKE %s
        ORDER BY fy.year_start_date DESC
        LIMIT %s OFFSET %s
    """, (company, "%%%s%%" % txt, page_len, start))