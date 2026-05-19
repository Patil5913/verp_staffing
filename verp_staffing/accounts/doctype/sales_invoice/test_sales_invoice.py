# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate, add_days

from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
    get_default_company_account,
)
from verp_staffing.accounts.doctype.company.company import get_company_currency
from verp_staffing.accounts.doctype.account.test_account import (
    create_account_if_not_exists,
)
from verp_staffing.crm.doctype.customer.test_customer import (
    make_customer,
)
from verp_staffing.stock.doctype.uom.test_uom import create_uom_if_not_exists
# from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists

from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists


class TestSalesInvoice(FrappeTestCase):
    pass


def make_sales_invoice(
    company=None, customer=None, items=[], amount=1000, do_not_submit=False, **overrides
):
    company = company or create_company_if_not_exists("vrugle")
    currency = get_company_currency(company)
    debit_to = get_default_company_account(company, "Receivable")
    income_account = create_account_if_not_exists("Sales", company).name
    customer = customer or make_customer(f"_Test Customer {company}")
    uom = create_uom_if_not_exists("kg")
    item = create_item_if_not_exists("_Test Sales Item", "Item Category 1", "kg")
    items = items or [
        {
            "item": item,
            "description": "Test Item",
            "item_name": item,
            "qty": 1,
            "rate": flt(amount),
            "type": "Sales",
            "uom": uom,
            "income_account": income_account,
        }
    ]

    si = frappe.new_doc("Sales Invoice")
    si.company = company
    si.customer = customer  # ← mandatory on parent
    si.posting_date = nowdate()
    si.due_date = add_days(nowdate(), 30)
    si.currency = currency
    si.conversion_rate = 1
    si.debit_to = debit_to
    # this helps in dynamically adding items from arguements
    for item in items:
        si.append("items", item)

    si.update(overrides)
    si.insert(ignore_permissions=True)
    if not do_not_submit:
        si.submit()
    return si
