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


def get_default_receivable_account(company):
    """Return the default receivable account for *company*."""
    account = frappe.get_cached_value("Company", company, "default_receivable_account")
    if not account:
        frappe.throw(
            f"No default receivable account configured for company '{company}'. "
            "Please set it in Company master."
        )
    return account


def get_default_payable_account(company):
    """Return the default payable account for *company*."""
    account = frappe.get_cached_value("Company", company, "default_payable_account")
    if not account:
        frappe.throw(
            f"No default payable account configured for company '{company}'. "
            "Please set it in Company master."
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
    """
    Return an existing Customer whose ``name1`` matches *customer_name*,
    or create and return a new one.

    ``company`` and ``currency`` are accepted for API symmetry but are not
    stored on the Customer doctype directly.
    """
    existing = frappe.db.get_value("Customer", {"name1": customer_name}, "name")
    if existing:
        return existing

    try:
        customer = get_doc({"doctype": "Customer", "name1": customer_name})
        customer.insert(ignore_permissions=True)
        return customer.name
    except frappe.DuplicateEntryError:
        existing = frappe.db.get_value("Customer", {"name1": customer_name}, "name")
        if existing:
            return existing
        raise


def get_or_create_test_customer(company):
    """
    Convenience wrapper that returns a deterministic test Customer scoped to
    *company*.  Uses ``create_customer_if_not_exists`` internally.
    """
    return create_customer_if_not_exists(
        customer_name=f"_Test Customer {company}",
    )


def create_supplier_if_not_exists(supplier_name, supplier_type="Individual"):
    """
    Return an existing Supplier whose ``supplier_name`` matches *supplier_name*,
    or create and return a new one.
    """
    existing = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
    if existing:
        return existing

    try:
        supplier = get_doc(
            {
                "doctype": "Supplier",
                "supplier_name": supplier_name,
                "supplier_type": supplier_type,
            }
        )
        supplier.insert(ignore_permissions=True)
        return supplier.name
    except frappe.DuplicateEntryError:
        existing = frappe.db.get_value(
            "Supplier", {"supplier_name": supplier_name}, "name"
        )
        if existing:
            return existing
        raise


def get_or_create_test_supplier(company):
    """
    Convenience wrapper that returns a deterministic test Supplier scoped to
    *company*.  Uses ``create_supplier_if_not_exists`` internally.
    """
    return create_supplier_if_not_exists(
        supplier_name=f"_Test Supplier {company}",
        supplier_type="Individual",
    )


def get_or_create_cash_account(company):
    account = frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Cash", "is_group": 0},
        "name",
    )
    if account:
        return account

    # "Current Assets - v" already exists and is a non-root group — use it directly
    parent = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": "Current Assets", "is_group": 1},
        "name",
    )
    if not parent:
        frappe.throw(f"Cannot find 'Current Assets' group for company '{company}'.")

    cash = get_doc(
        {
            "doctype": "Account",
            "account_name": "Cash",
            "company": company,
            "account_type": "Cash",
            "root_type": "Asset",
            "is_group": 0,
            "parent_account": parent,
        }
    )
    cash.insert(ignore_permissions=True)
    return cash.name


def get_or_create_income_account(company):
    account = frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Income Account", "is_group": 0},
        "name",
    )
    if account:
        return account

    # Step 1 — create Income root group if missing
    income_root = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "root_type": "Income",
            "is_group": 1,
            "parent_account": ("is", "not set"),
        },
        "name",
    )
    if not income_root:
        root_doc = get_doc(
            {
                "doctype": "Account",
                "account_name": "Income",
                "company": company,
                "root_type": "Income",
                "is_group": 1,
                "parent_account": None,
                "report_type": "Profit and Loss",
            }
        )
        root_doc.insert(ignore_permissions=True)
        income_root = root_doc.name

    # Step 2 — create a child Income group under the root
    income_group = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "root_type": "Income",
            "is_group": 1,
            "parent_account": income_root,
        },
        "name",
    )
    if not income_group:
        group_doc = get_doc(
            {
                "doctype": "Account",
                "account_name": "Direct Income",
                "company": company,
                "root_type": "Income",
                "is_group": 1,
                "parent_account": income_root,
                "report_type": "Profit and Loss",
            }
        )
        group_doc.insert(ignore_permissions=True)
        income_group = group_doc.name

    # Step 3 — create the leaf Income account
    income_doc = get_doc(
        {
            "doctype": "Account",
            "account_name": "Sales",
            "company": company,
            "account_type": "Income Account",
            "root_type": "Income",
            "is_group": 0,
            "parent_account": income_group,
            "report_type": "Profit and Loss",
        }
    )
    income_doc.insert(ignore_permissions=True)
    return income_doc.name


def get_or_create_write_off_account(company):
    """Return existing write-off account or create one and set it on the Company master."""
    # Check if already configured on company
    existing = frappe.get_cached_value("Company", company, "write_off_account")
    if existing:
        return existing

    # Find or create a write-off leaf account under the Income group
    account = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": "Write Off", "is_group": 0},
        "name",
    )
    if not account:
        parent = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "root_type": "Income",
                "is_group": 1,
                "parent_account": ["!=", ""],
            },
            "name",
        )
        if not parent:
            frappe.throw(
                f"No Income group found for company '{company}' to create write-off account."
            )

        wo = get_doc(
            {
                "doctype": "Account",
                "account_name": "Write Off",
                "company": company,
                "root_type": "Income",
                "is_group": 0,
                "parent_account": parent,
                "report_type": "Profit and Loss",
            }
        )
        wo.insert(ignore_permissions=True)
        account = wo.name

    # Set it on the Company master
    frappe.db.set_value("Company", company, "write_off_account", account)
    frappe.get_doc("Company", company).reload()

    return account


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
