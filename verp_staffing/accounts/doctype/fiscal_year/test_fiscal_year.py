# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFiscalYear(FrappeTestCase):
	pass


def create_fiscal_year_if_not_exists(
    fiscal_year,
    companies,
    start_date,
    end_date,
):
    """
    Ensure a Fiscal Year exists and is linked to given companies.

    Args:
        fiscal_year (str): Fiscal year name (e.g. "2026")
        companies (list): List of company names
        start_date (date)
        end_date (date)

    Returns:
        Document: Fiscal Year doc
    """

    # 🔒 Validate input
    if not companies:
        frappe.throw("At least one company is required")

    # ─────────────────────────────
    # 1. If Fiscal Year exists
    # ─────────────────────────────
    if frappe.db.exists("Fiscal Year", fiscal_year):
        fy = frappe.get_doc("Fiscal Year", fiscal_year)

        # Ensure all companies are linked
        existing_companies = {c.company for c in fy.included_companies}

        for company in companies:
            if company not in existing_companies:
                fy.append("included_companies", {"company": company})

        fy.save(ignore_permissions=True)
        return fy

    # ─────────────────────────────
    # 2. Check if FY exists for any company
    # ─────────────────────────────
    for company in companies:
        existing = frappe.db.get_value(
            "Fiscal Year Company",
            {"company": company},
            "parent",
        )
        if existing:
            return frappe.get_doc("Fiscal Year", existing)

    # ─────────────────────────────
    # 3. Create new Fiscal Year
    # ─────────────────────────────
    fy = frappe.get_doc({
        "doctype": "Fiscal Year",
        "year": fiscal_year,
        "year_start_date": start_date,
        "year_end_date": end_date,
    })

    for company in companies:
        fy.append("included_companies", {"company": company})

    fy.insert(ignore_permissions=True)

    return fy