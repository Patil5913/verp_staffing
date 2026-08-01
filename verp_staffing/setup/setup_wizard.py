import frappe
from frappe import _

def setup_complete(args=None):
    args = frappe._dict(args or {})

    company = create_company(args)

    create_fiscal_year(args, company)

    if args.get("add_sample_data"):
        from verp_staffing.setup.sample_data import create_sample_data

        create_sample_data(company)


def create_company(args):
    company_name = args.get("company_name")
    currency = args.get("currency")
    country = args.get("country")

    abbr = "".join([word[0] for word in company_name.split() if word])[:10].upper()
    frappe.errprint(f"currency:{currency}")
    company = frappe.get_doc(
        {
            "doctype": "Company",
            "company_name": company_name,
            "abbr": abbr,
            "default_currency": currency,
            "country": country,
        }
    )

    company.insert(ignore_permissions=True)
    frappe.db.set_single_value(
        "Accounts Settings",
        "default_company",
        company.name,
    )
    return company


def create_fiscal_year(args, company):
    start_date = args.get("fy_start_date")
    end_date = args.get("fy_end_date")

    start_year = str(start_date)[:4]
    end_year = str(end_date)[:4]

    fy = frappe.get_doc(
        {
            "doctype": "Fiscal Year",
            "year": f"{start_year}-{end_year}",
            "year_start_date": start_date,
            "year_end_date": end_date,
            "included_companies": [{"company": company.name}],
        }
    )

    fy.insert(ignore_permissions=True)

    return fy
