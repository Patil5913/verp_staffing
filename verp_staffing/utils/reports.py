import frappe
from frappe import _

# Filter definitions for the 12 Script Reports in the sidebar's "Reports"
# group. These live only in each report's classic-desk .js file
# (frappe.query_reports["<name>"].filters) — the Report doctype record
# itself carries no filter metadata — so there's no way to discover them
# generically at runtime. Hand-transcribed here once; conditional
# show/hide behavior and company/fiscal-year-scoped Link queries from the
# .js files are intentionally simplified to plain Link pickers (every field
# is always shown, no cascading defaults) — this is a filter *bar*, not a
# reimplementation of each report's client-side script.
REPORT_FILTERS = {
    "Call Details": [
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee"},
        {"fieldname": "start_date", "label": "Start Date", "fieldtype": "Date"},
        {"fieldname": "end_date", "label": "End Date", "fieldtype": "Date"},
        {"fieldname": "timeline", "label": "Timeline", "fieldtype": "Select", "options": "\nMonthly\n3 Months\n6 Months\nYearly"},
    ],
    "Future Interviews Per Customer": [
        {"fieldname": "to_date", "label": "Up To Date", "fieldtype": "Date"},
        {"fieldname": "customer", "label": "Customer", "fieldtype": "Link", "options": "Customer"},
        {"fieldname": "periodicity", "label": "Periodicity", "fieldtype": "Select", "options": "\nMonthly\nQuarterly\nYearly"},
        {"fieldname": "year", "label": "Year", "fieldtype": "Int"},
        {"fieldname": "limit", "label": "Limit", "fieldtype": "Int", "default": 25},
    ],
    "General Ledger": [
        {"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company", "reqd": 1},
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date", "reqd": 1},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date", "reqd": 1},
        {"fieldname": "account", "label": "Account", "fieldtype": "Link", "options": "Account"},
        {"fieldname": "fiscal_year", "label": "Fiscal Year", "fieldtype": "Link", "options": "Fiscal Year"},
        {"fieldname": "finance_book", "label": "Finance Book", "fieldtype": "Link", "options": "Finance Book"},
        {"fieldname": "party_type", "label": "Party Type", "fieldtype": "Select", "options": "\nCustomer\nSupplier\nEmployee\nShareholder"},
        {"fieldname": "party", "label": "Party", "fieldtype": "Data"},
        {"fieldname": "is_opening", "label": "Is Opening", "fieldtype": "Select", "options": "\nYes\nNo"},
        {"fieldname": "is_advance", "label": "Is Advance", "fieldtype": "Select", "options": "\nYes\nNo"},
        {"fieldname": "show_in_account_currency", "label": "Show in Account Currency", "fieldtype": "Check"},
        {"fieldname": "group_by", "label": "Group By", "fieldtype": "Select", "options": "\nGroup by Account\nGroup by Party", "default": "Group by Voucher"},
        {"fieldname": "show_remarks", "label": "Show Remarks", "fieldtype": "Check"},
    ],
    "Interview Target Report": [
        {"fieldname": "from_date", "label": "Select Date", "fieldtype": "Date", "reqd": 1},
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee"},
    ],
    "Interviews Per Customer": [
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "Up To Date", "fieldtype": "Date"},
        {"fieldname": "customer", "label": "Customer", "fieldtype": "Link", "options": "Customer"},
        {"fieldname": "periodicity", "label": "Periodicity", "fieldtype": "Select", "options": "\nMonthly\nQuarterly\nYearly"},
        {"fieldname": "year", "label": "Year", "fieldtype": "Int"},
        {"fieldname": "limit", "label": "Limit", "fieldtype": "Int"},
    ],
    "Lead Conversion Funnel": [
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"},
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee"},
    ],
    "Lead Details": [
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"},
        {"fieldname": "source", "label": "Source", "fieldtype": "Link", "options": "Lead Source"},
        {"fieldname": "lead_owner", "label": "Lead Owner", "fieldtype": "Link", "options": "Employee"},
    ],
    "Lead Per Employee": [
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"},
        {
            "fieldname": "visa_status",
            "label": "Visa Status",
            "fieldtype": "Select",
            "options": "\nF1 CPT\nF1 OPT\nSTEM OPT\nH1 B\nH4\nGREEN CARD\nUSC\nEB - 1\nEB - 2\nEB - 3\nL - 1\nL - 2\nTN\nO - 1\nWORK PERMIT\nPR",
        },
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee"},
    ],
    "Profiles Per Recruiter": [
        {"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"},
        {"fieldname": "recruiter", "label": "Recruiter", "fieldtype": "Link", "options": "Employee"},
    ],
    "Profit and Loss Statement": [
        {"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company", "reqd": 1},
        {"fieldname": "finance_book", "label": "Finance Book", "fieldtype": "Link", "options": "Finance Book"},
        {"fieldname": "filter_based_on", "label": "Filter Based On", "fieldtype": "Select", "options": "Fiscal Year\nDate Range", "default": "Fiscal Year", "reqd": 1},
        {"fieldname": "from_fiscal_year", "label": "Start Year", "fieldtype": "Link", "options": "Fiscal Year"},
        {"fieldname": "to_fiscal_year", "label": "End Year", "fieldtype": "Link", "options": "Fiscal Year"},
        {"fieldname": "from_date", "label": "Start Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "End Date", "fieldtype": "Date"},
        {"fieldname": "periodicity", "label": "Periodicity", "fieldtype": "Select", "options": "Yearly\nHalf-Yearly\nQuarterly\nMonthly", "default": "Yearly", "reqd": 1},
        {"fieldname": "currency", "label": "Currency", "fieldtype": "Link", "options": "Currency"},
        {"fieldname": "view", "label": "Select View", "fieldtype": "Select", "options": "Report View\nGrowth View\nMargin View", "default": "Report View"},
        {"fieldname": "show_accumulated_values", "label": "Show Accumulated Values (YTD)", "fieldtype": "Check"},
        {"fieldname": "include_default_fb_entries", "label": "Include Default FB Entries", "fieldtype": "Check", "default": 1},
    ],
    "Revenue Of Employee": [
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee"},
        {"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company", "reqd": 1},
        {"fieldname": "start_date", "label": "Start Date", "fieldtype": "Date"},
        {"fieldname": "end_date", "label": "End Date", "fieldtype": "Date"},
        {"fieldname": "timeline", "label": "Timeline", "fieldtype": "Select", "options": "\nMonthly\n3 Months\n6 Months\nYearly"},
    ],
    "Balance Sheet": [
        {"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company", "reqd": 1},
        {"fieldname": "finance_book", "label": "Finance Book", "fieldtype": "Link", "options": "Finance Book"},
        {"fieldname": "filter_based_on", "label": "Filter Based On", "fieldtype": "Select", "options": "Fiscal Year\nDate Range", "default": "Fiscal Year", "reqd": 1},
        {"fieldname": "from_fiscal_year", "label": "Start Year", "fieldtype": "Link", "options": "Fiscal Year"},
        {"fieldname": "to_fiscal_year", "label": "End Year", "fieldtype": "Link", "options": "Fiscal Year"},
        {"fieldname": "from_date", "label": "Start Date", "fieldtype": "Date"},
        {"fieldname": "to_date", "label": "End Date", "fieldtype": "Date"},
        {"fieldname": "periodicity", "label": "Periodicity", "fieldtype": "Select", "options": "Yearly\nHalf-Yearly\nQuarterly\nMonthly", "default": "Yearly", "reqd": 1},
        {"fieldname": "currency", "label": "Presentation Currency", "fieldtype": "Link", "options": "Currency"},
        {"fieldname": "view", "label": "Select View", "fieldtype": "Select", "options": "Report View\nGrowth View", "default": "Report View"},
        {"fieldname": "exchange_rate", "label": "Exchange Rate", "fieldtype": "Float", "default": 1},
        {"fieldname": "show_period_movement", "label": "Show Period Movement (Advanced)", "fieldtype": "Check"},
    ],
}


@frappe.whitelist()
def get_report_filters(report_name):
    if report_name not in REPORT_FILTERS:
        frappe.throw(_("Unknown report: {0}").format(report_name), frappe.DoesNotExistError)

    ref_doctype = frappe.db.get_value("Report", report_name, "ref_doctype")
    if ref_doctype and not frappe.has_permission(ref_doctype, "read"):
        frappe.throw(
            _("You do not have permission to view {0}").format(report_name),
            frappe.PermissionError,
        )

    return {"report_name": report_name, "filters": REPORT_FILTERS[report_name]}
