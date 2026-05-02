import frappe
from frappe import get_doc


def create_company_if_not_exists(company_name,default_currency="INR"):

    if not frappe.db.exists("Company", company_name):
        company = get_doc(
            {
                "doctype": "Company",
                "company_name": company_name,
                "country": "India",
                "default_currency": default_currency,
            }
        )

        company.insert()
        return company
    else:
        return get_doc("Company", company_name)


def create_account_if_not_exists(account_name, company):

    if not frappe.db.exists(
        "Account", {"account_name": account_name, "company": company}
    ):
        account = get_doc(
            {"doctype": "Account", "account_name": account_name, "company": company}
        )
        account.insert()
        return account
    else: 
        return get_doc("Account",{"account_name": account_name})

def create_fiscal_year_if_not_exists(fiscal_year, companies, start_date, end_date):
    if not frappe.db.exists("Fiscal Year", fiscal_year):
        fiscal_year_doc = get_doc(
            {
                "doctype": "Fiscal Year",
                "year": fiscal_year,
                "year_start_date": start_date,
                "year_end_date": end_date,
            }
        )
        for company in companies:
            fiscal_year_doc.append("included_companies", {"company": company})
        fiscal_year_doc.insert()
        return fiscal_year_doc
    else:
        return get_doc("Fiscal Year", fiscal_year)