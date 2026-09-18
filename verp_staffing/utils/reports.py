import frappe
from frappe import _
from frappe.utils import add_months, get_first_day, get_last_day, getdate, nowdate

# Filter definitions for the Script Reports the new frontend runs (the
# sidebar's "Reports" group plus Trial Balance). Each report's filters live
# only in its classic-desk .js (frappe.query_reports["<name>"].filters) — the
# Report doctype record carries no filter metadata — so they're transcribed
# here once, including what makes the desk filter bar smart:
#
#   query        whitelisted standard query for a Link (desk's get_query.query)
#   link_filters filters for a Link's search; a "$name" value reads another
#                filter's current value (desk's get_query filters closure)
#   options_from a Link whose target doctype is another filter's value
#                (General Ledger's Party follows Party Type)
#   depends_on   "eval:<js over doc>" — show the filter only when true
#   clears       filters to empty when this one is set (desk's on_change)
#   default      a literal, or an "@token" resolved server-side (see _token)
#
# Reports whose defaults depend on a company (fiscal year, currency) get them
# from get_company_report_defaults when the company is chosen.

EMPLOYEE_LEAD = "verp_staffing.crm.api.report_helper.get_lead_hierarchy_employees"
EMPLOYEE_MARKETING_TARGET = "verp_staffing.marketing.report.interview_target_report.interview_target_report.get_marketing_hierarchy_employees"
EMPLOYEE_MARKETING_RECRUITER = "verp_staffing.marketing.report.profiles_per_recruiter.profiles_per_recruiter.get_marketing_hierarchy_employees"
EMPLOYEE_CALLS = "verp_staffing.crm.report.call_details.call_details.get_hierarchy_employees"
EMPLOYEE_SALES = "verp_staffing.crm.report.revenue_of_employee.revenue_of_employee.get_sales_hierarchy_employees"
CUSTOMERS_WITH_INTERVIEWS = "verp_staffing.marketing.report.interviews_per_customer.interviews_per_customer.get_customers_with_interviews"
FY_OF_COMPANY_GL = "verp_staffing.accounts.doctype.fiscal_year.fiscal_year.get_fiscal_years_for_company"
FY_OF_COMPANY = "verp_staffing.accounts.utils.fiscal_year_opening_balance.get_fiscal_years_for_company"

VISA_OPTIONS = "\nF1 CPT\nF1 OPT\nSTEM OPT\nH1 B\nH4\nGREEN CARD\nUSC\nEB - 1\nEB - 2\nEB - 3\nL - 1\nL - 2\nTN\nO - 1\nWORK PERMIT\nPR"
TIMELINE = "\nMonthly\n3 Months\n6 Months\nYearly"


def _date(fieldname, label, **extra):
    return {"fieldname": fieldname, "label": label, "fieldtype": "Date", **extra}


def _link(fieldname, label, options, **extra):
    return {"fieldname": fieldname, "label": label, "fieldtype": "Link", "options": options, **extra}


def _statement_filters(balance_sheet):
    """Balance Sheet and Profit & Loss share their filter bar."""
    return [
        _link("company", "Company", "Company", reqd=1, default="@default_company"),
        _link("finance_book", "Finance Book", "Finance Book"),
        {"fieldname": "filter_based_on", "label": "Filter Based On", "fieldtype": "Select", "options": "Fiscal Year\nDate Range", "default": "Fiscal Year", "reqd": 1},
        _link("from_fiscal_year", "Start Year", "Fiscal Year", query=FY_OF_COMPANY, link_filters={"company": "$company"}, depends_on="eval:doc.filter_based_on=='Fiscal Year'"),
        _link("to_fiscal_year", "End Year", "Fiscal Year", query=FY_OF_COMPANY, link_filters={"company": "$company"}, depends_on="eval:doc.filter_based_on=='Fiscal Year'"),
        _date("from_date", "Start Date", depends_on="eval:doc.filter_based_on=='Date Range'"),
        _date("to_date", "End Date", depends_on="eval:doc.filter_based_on=='Date Range'"),
        {"fieldname": "periodicity", "label": "Periodicity", "fieldtype": "Select", "options": "Yearly\nHalf-Yearly\nQuarterly\nMonthly", "default": "Yearly", "reqd": 1},
        _link("currency", "Presentation Currency" if balance_sheet else "Currency", "Currency"),
        {
            "fieldname": "view",
            "label": "Select View",
            "fieldtype": "Select",
            "options": "Report View\nGrowth View" if balance_sheet else "Report View\nGrowth View\nMargin View",
            "default": "Report View",
        },
        *(
            [
                {"fieldname": "exchange_rate", "label": "Exchange Rate", "fieldtype": "Float", "default": 1},
                {"fieldname": "show_period_movement", "label": "Show Period Movement (Advanced)", "fieldtype": "Check"},
            ]
            if balance_sheet
            else [{"fieldname": "show_accumulated_values", "label": "Show Accumulated Values (YTD)", "fieldtype": "Check"}]
        ),
        {"fieldname": "include_default_fb_entries", "label": "Include Default FB Entries", "fieldtype": "Check", "default": 1},
    ]


REPORT_FILTERS = {
    "Call Details": [
        _link("employee", "Employee", "Employee", query=EMPLOYEE_CALLS),
        _date("start_date", "Start Date"),
        _date("end_date", "End Date"),
        {"fieldname": "timeline", "label": "Timeline", "fieldtype": "Select", "options": TIMELINE},
    ],
    "Future Interviews Per Customer": [
        _date("to_date", "Up To Date", depends_on="eval:!doc.periodicity", clears=["periodicity"]),
        _link("customer", "Customer", "Customer", query=CUSTOMERS_WITH_INTERVIEWS, depends_on="eval:!doc.periodicity", clears=["periodicity"]),
        {
            "fieldname": "periodicity",
            "label": "Periodicity",
            "fieldtype": "Select",
            "options": "\nMonthly\nQuarterly\nYearly",
            "clears": ["customer", "to_date"],
        },
        {"fieldname": "year", "label": "Year", "fieldtype": "Int", "default": "@year", "depends_on": "eval:['Monthly','Quarterly'].includes(doc.periodicity)"},
        {"fieldname": "limit", "label": "Limit", "fieldtype": "Int", "default": 25, "max": 500, "description": "Maximum 500 records", "depends_on": "eval:!doc.periodicity"},
    ],
    "General Ledger": [
        _link("company", "Company", "Company", reqd=1, default="@default_company"),
        _date("from_date", "From Date", reqd=1, default="@month_ago"),
        _date("to_date", "To Date", reqd=1, default="@today", clears=["fiscal_year"]),
        _link("account", "Account", "Account", link_filters={"company": "$company"}),
        _link("fiscal_year", "Fiscal Year", "Fiscal Year", query=FY_OF_COMPANY_GL, link_filters={"company": "$company"}, sets_dates=True),
        _link("finance_book", "Finance Book", "Finance Book"),
        _link("party_type", "Party Type", "DocType", link_filters={"name": ["in", ["Customer", "Supplier", "Employee", "Shareholder"]]}, clears=["party"]),
        _link("party", "Party", "Customer", options_from="party_type", depends_on="eval:doc.party_type"),
        {"fieldname": "is_opening", "label": "Is Opening", "fieldtype": "Select", "options": "\nYes\nNo"},
        {"fieldname": "is_advance", "label": "Is Advance", "fieldtype": "Select", "options": "\nYes\nNo"},
        {"fieldname": "show_in_account_currency", "label": "Show in Account Currency", "fieldtype": "Check"},
        {"fieldname": "group_by", "label": "Group By", "fieldtype": "Select", "options": "\nGroup by Account\nGroup by Party", "default": ""},
        {"fieldname": "show_remarks", "label": "Show Remarks", "fieldtype": "Check"},
    ],
    "Interview Target Report": [
        _date("from_date", "Select Date", reqd=1, default="@today", auto_run=True),
        _link("employee", "Employee", "Employee", query=EMPLOYEE_MARKETING_TARGET),
    ],
    "Interviews Per Customer": [
        _date("from_date", "From Date", depends_on="eval:!doc.periodicity", clears=["periodicity"]),
        _date("to_date", "Up To Date", depends_on="eval:!doc.periodicity", clears=["periodicity"]),
        _link("customer", "Customer", "Customer", query=CUSTOMERS_WITH_INTERVIEWS, depends_on="eval:!doc.periodicity", clears=["periodicity"]),
        {
            "fieldname": "periodicity",
            "label": "Periodicity",
            "fieldtype": "Select",
            "options": "\nMonthly\nQuarterly\nYearly",
            "clears": ["customer", "to_date", "from_date"],
        },
        {"fieldname": "year", "label": "Year", "fieldtype": "Int", "default": "@year", "depends_on": "eval:['Monthly','Quarterly'].includes(doc.periodicity)"},
        {"fieldname": "limit", "label": "Limit", "fieldtype": "Int", "max": 500, "description": "Maximum 500 records", "depends_on": "eval:!doc.periodicity"},
    ],
    "Lead Conversion Funnel": [
        _date("from_date", "From Date", default="@month_start"),
        _date("to_date", "To Date", default="@month_end"),
        _link("employee", "Employee", "Employee", query=EMPLOYEE_LEAD),
    ],
    "Lead Details": [
        _date("from_date", "From Date"),
        _date("to_date", "To Date"),
        _link("source", "Source", "Lead Source"),
        _link("lead_owner", "Lead Owner", "Employee", query=EMPLOYEE_LEAD),
    ],
    "Lead Per Employee": [
        _date("from_date", "From Date"),
        _date("to_date", "To Date"),
        {"fieldname": "visa_status", "label": "Visa Status", "fieldtype": "Select", "options": VISA_OPTIONS},
        _link("employee", "Employee", "Employee", query=EMPLOYEE_LEAD),
    ],
    "Profiles Per Recruiter": [
        _date("from_date", "From Date"),
        _date("to_date", "To Date"),
        _link("recruiter", "Recruiter", "Employee", query=EMPLOYEE_MARKETING_RECRUITER),
    ],
    "Profit and Loss Statement": _statement_filters(balance_sheet=False),
    "Revenue Of Employee": [
        _link("employee", "Employee", "Employee", query=EMPLOYEE_SALES),
        _link("company", "Company", "Company", reqd=1, default="@default_company"),
        _date("start_date", "Start Date"),
        _date("end_date", "End Date"),
        {"fieldname": "timeline", "label": "Timeline", "fieldtype": "Select", "options": TIMELINE},
    ],
    "Balance Sheet": _statement_filters(balance_sheet=True),
    "Trial Balance": [
        _link("company", "Company", "Company", reqd=1, default="@default_company"),
        _link("fiscal_year", "Fiscal Year", "Fiscal Year", reqd=1, query=FY_OF_COMPANY, link_filters={"company": "$company"}, sets_dates=True),
        _date("from_date", "From Date", reqd=1),
        _date("to_date", "To Date", reqd=1),
        _link("finance_book", "Finance Book", "Finance Book"),
        _link("currency", "Currency", "Currency"),
        {"fieldname": "with_period_closing_entry", "label": "With Period Closing Entry For Opening Balances", "fieldtype": "Check", "default": 1},
        {"fieldname": "period_closing_entry", "label": "Period Closing Entry For Current Period", "fieldtype": "Check", "default": 0},
        {"fieldname": "show_zero_values", "label": "Show Zero Values", "fieldtype": "Check", "default": 0},
        {"fieldname": "show_unclosed_fy_pl_balances", "label": "Show Unclosed Fiscal Year's P&L Balances", "fieldtype": "Check", "default": 0},
        {"fieldname": "include_default_fb_entries", "label": "Include Default FB Entries", "fieldtype": "Check", "default": 1},
        {"fieldname": "show_net_values", "label": "Show Net Values in Opening and Closing Columns", "fieldtype": "Check", "default": 0},
    ],
}

# The reports hub: what each is for, grouped by area. `name` must be a key of
# REPORT_FILTERS. Access is still decided per report by its ref doctype.
REPORT_INDEX = [
    {"group": "Sales & Leads", "name": "Lead Details", "description": "Every lead with its status, owner and source.", "icon": "users"},
    {"group": "Sales & Leads", "name": "Lead Conversion Funnel", "description": "How leads move to opportunities and customers.", "icon": "filter"},
    {"group": "Sales & Leads", "name": "Lead Per Employee", "description": "Leads handled by each employee, split by visa status.", "icon": "user-check"},
    {"group": "Sales & Leads", "name": "Call Details", "description": "Calls logged against opportunities, and their duration.", "icon": "phone"},
    {"group": "Sales & Leads", "name": "Revenue Of Employee", "description": "Revenue each sales employee has closed against their target.", "icon": "trending-up"},
    {"group": "Marketing", "name": "Interviews Per Customer", "description": "Interviews scheduled per customer, by period.", "icon": "calendar-check"},
    {"group": "Marketing", "name": "Future Interviews Per Customer", "description": "Upcoming interviews per customer.", "icon": "calendar-clock"},
    {"group": "Marketing", "name": "Interview Target Report", "description": "Applications logged against each marketing target.", "icon": "target"},
    {"group": "Marketing", "name": "Profiles Per Recruiter", "description": "Profiles handled by each recruiter.", "icon": "id-card"},
    {"group": "Accounts", "name": "General Ledger", "description": "Every posting by account, party or voucher.", "icon": "book-open"},
    {"group": "Accounts", "name": "Trial Balance", "description": "Opening, period and closing balances for every account.", "icon": "scale"},
    {"group": "Accounts", "name": "Profit and Loss Statement", "description": "Income against expenses for the period.", "icon": "chart-line"},
    {"group": "Accounts", "name": "Balance Sheet", "description": "Assets, liabilities and equity at period end.", "icon": "landmark"},
]


def _has_access(report_name):
    ref_doctype = frappe.db.get_value("Report", report_name, "ref_doctype")
    return not ref_doctype or bool(frappe.has_permission(ref_doctype, "read"))


def _default_company():
    """ERP Configuration's default company — unless it has nothing posted yet
    (a fresh Demo Company), in which case the company with the most GL
    entries, so a report opens on data rather than an empty statement."""
    configured = frappe.db.get_single_value("ERP Configuration", "default_company") or frappe.defaults.get_user_default("Company")
    if configured and frappe.db.exists("GL Entry", {"company": configured}):
        return configured
    busiest = frappe.db.sql(
        "select company from `tabGL Entry` group by company order by count(*) desc limit 1"
    )
    return busiest[0][0] if busiest else configured


def _token(token):
    today = getdate(nowdate())
    return {
        "@today": str(today),
        "@month_start": str(get_first_day(today)),
        "@month_end": str(get_last_day(today)),
        "@month_ago": str(add_months(today, -1)),
        "@year": today.year,
        "@default_company": _default_company(),
    }.get(token)


@frappe.whitelist()
def get_company_report_defaults(company):
    """What choosing a company fills in on the financial reports (the desk's
    _apply_company_defaults): its currency, the fiscal years it belongs to,
    and the latest one with its dates."""
    if not company or not frappe.db.exists("Company", company):
        return {}

    year_names = frappe.get_all("Fiscal Year Company", filters={"company": company, "parenttype": "Fiscal Year"}, pluck="parent")
    years = (
        frappe.get_all(
            "Fiscal Year",
            filters={"name": ["in", year_names]},
            fields=["name", "year_start_date", "year_end_date"],
            order_by="year_start_date asc",
        )
        if year_names
        else []
    )
    latest = years[-1] if years else None
    return {
        "currency": frappe.db.get_value("Company", company, "default_currency"),
        "fiscal_years": [y.name for y in years],
        "latest_fiscal_year": latest.name if latest else None,
        "fy_start": str(latest.year_start_date) if latest else None,
        "fy_end": str(latest.year_end_date) if latest else None,
    }


@frappe.whitelist()
def get_fiscal_year_dates(fiscal_year):
    row = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
    return {"from": str(row.year_start_date), "to": str(row.year_end_date)} if row else {}


@frappe.whitelist()
def get_report_filters(report_name):
    if report_name not in REPORT_FILTERS:
        frappe.throw(_("Unknown report: {0}").format(report_name), frappe.DoesNotExistError)

    if not _has_access(report_name):
        frappe.throw(
            _("You do not have permission to view {0}").format(report_name),
            frappe.PermissionError,
        )

    filters = REPORT_FILTERS[report_name]
    defaults = {}
    for f in filters:
        value = f.get("default")
        if isinstance(value, str) and value.startswith("@"):
            value = _token(value)
        if value not in (None, ""):
            defaults[f["fieldname"]] = value

    # Financial statements open on the company's latest fiscal year.
    company = defaults.get("company")
    if company and any(f["fieldname"] in ("from_fiscal_year", "fiscal_year") for f in filters):
        cd = get_company_report_defaults(company)
        if cd.get("latest_fiscal_year"):
            if any(f["fieldname"] == "from_fiscal_year" for f in filters):
                defaults["from_fiscal_year"] = defaults["to_fiscal_year"] = cd["latest_fiscal_year"]
            if any(f["fieldname"] == "fiscal_year" for f in filters) and report_name == "Trial Balance":
                defaults["fiscal_year"] = cd["latest_fiscal_year"]
                defaults["from_date"], defaults["to_date"] = cd["fy_start"], cd["fy_end"]
        if cd.get("currency") and any(f["fieldname"] == "currency" for f in filters):
            defaults["currency"] = cd["currency"]

    description = next((r["description"] for r in REPORT_INDEX if r["name"] == report_name), "")
    return {"report_name": report_name, "filters": filters, "defaults": defaults, "description": description}


@frappe.whitelist()
def get_reports_index():
    """The reports the current user may open, grouped for the hub."""
    return [r for r in REPORT_INDEX if _has_access(r["name"])]
