# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate ,add_days

from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
    get_company_currency,
    get_default_company_account,
)
from verp_staffing.accounts.doctype.account.test_account import (
    create_account_if_not_exists,
)
from verp_staffing.crm.doctype.customer.test_customer import (
    create_customer_if_not_exists,
)
from verp_staffing.stock.doctype.uom.test_uom import create_uom_if_not_exists


class TestSalesInvoice(FrappeTestCase):
    pass


def make_sales_invoice(company=None, customer=None, amount=1000, do_not_submit=False):
    company = company or create_company_if_not_exists("vrugle").name
    currency = get_company_currency(company)
    debit_to = get_default_company_account(company, "Receivable")
    customer = customer or create_customer_if_not_exists(f"_Test Customer {company}")
    uom = create_uom_if_not_exists("NOS")  # must match Item's stock_uom

    # Items Table requires: item (Link), qty, rate, amount, uom, type
    # income_account is mandatory when type == "Sales"
    income_account = create_account_if_not_exists("Sales", company).name
    item = create_item_if_not_exists("_Test Sales Item", "Item Category 1", "NOS")

    si = frappe.new_doc("Sales Invoice")
    si.company = company
    si.customer = customer
    si.posting_date = nowdate()
    si.due_date = add_days(nowdate(), 30)
    si.currency = currency
    si.conversion_rate = 1
    si.debit_to = debit_to

    si.append(
        "items",
        {
            "item": item,  # Link to Item (required)
            "qty": 1,
            "rate": flt(amount),
            "amount": flt(amount),  # qty × rate (required)
            "uom": uom,
            "type": "Sales",  # required — was missing, caused MandatoryError
            "income_account": income_account,  # mandatory when type == "Sales"
        },
    )

    si.insert(ignore_permissions=True)
    if not do_not_submit:
        si.submit()
    return si