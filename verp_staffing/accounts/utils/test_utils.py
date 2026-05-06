import frappe
from frappe import get_doc


def create_company_if_not_exists(company_name, default_currency="INR"):
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
        return get_doc("Account", {"account_name": account_name})


def create_fiscal_year_if_not_exists(fiscal_year, companies, start_date, end_date):
    if not frappe.db.exists("Fiscal Year", fiscal_year):
        for company in companies:
            existing = frappe.db.get_value(
                "Fiscal Year Company",
                {"company": company},
                "parent",
            )
            if existing:
                return get_doc("Fiscal Year", existing)

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


def get_company_currency(company):
    """Return the default currency configured for *company*."""
    return frappe.get_cached_value("Company", company, "default_currency")


def get_default_company_account(company, account_type):
    """
    Return the default account for *company* based on *account_type*.
    Uses the Account doctype's known mapping of account_type → company field.
    """
    account_type_to_field = {
        "Receivable": "default_receivable_account",
        "Payable": "default_payable_account",
        "Bank": "default_bank_account",
        "Cash": "default_cash_account",
        "Write Off": "write_off_account",
        "Exchange Gain/Loss": "exchange_gain_loss_account",
        "Cost of Goods Sold": "default_expense_account",
        "Stock": "default_inventory_account",
        "Round Off": "round_off_account",
    }

    field = account_type_to_field.get(account_type)
    if not field:
        frappe.throw(
            f"Account type '{account_type}' is not mapped to any Company field."
        )

    account = frappe.get_cached_value("Company", company, field)
    if not account:
        frappe.throw(
            f"No default '{account_type}' account configured for company '{company}'. "
            f"Please set '{field}' in the Company master."
        )
    return account


def create_uom_if_not_exists(uom_name):
    """Return an existing UOM or create one with *uom_name*."""
    if not frappe.db.exists("UOM", uom_name):
        uom = get_doc({"doctype": "UOM", "uom_name": uom_name})
        uom.insert()
        return uom
    return get_doc("UOM", uom_name)


def create_customer_if_not_exists(customer_name):
    """Return an existing Customer or create and return a new one."""
    if frappe.db.exists("Customer", {"name1": customer_name}):
        return get_doc("Customer", {"name1": customer_name}).name

    customer = get_doc({"doctype": "Customer", "name1": customer_name})
    customer.insert(ignore_permissions=True)
    return customer.name


def create_supplier_if_not_exists(supplier_name, supplier_type="Individual"):
    """Return an existing Supplier or create and return a new one."""
    if frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
        return get_doc("Supplier", {"supplier_name": supplier_name}).name

    supplier = get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": supplier_name,
            "supplier_type": supplier_type,
        }
    )
    supplier.insert(ignore_permissions=True)
    return supplier.name


def create_party_types_if_not_exists():
    """Seed Customer and Supplier into the Party Type master with correct account types."""
    party_type_map = {
        "Customer": "Receivable",
        "Supplier": "Payable",
    }

    for party_type, account_type in party_type_map.items():
        if not frappe.db.exists("Party Type", party_type):
            get_doc(
                {
                    "doctype": "Party Type",
                    "party_type": party_type,
                    "account_type": account_type,
                }
            ).insert(ignore_permissions=True)
        else:
            # Fix it if it already exists with wrong account_type
            existing = frappe.db.get_value("Party Type", party_type, "account_type")
            if existing != account_type:
                frappe.db.set_value(
                    "Party Type", party_type, "account_type", account_type
                )

              
