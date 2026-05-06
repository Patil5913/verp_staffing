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