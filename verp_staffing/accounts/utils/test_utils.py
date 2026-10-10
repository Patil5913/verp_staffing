import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.utils import utils
from verp_staffing.accounts.utils.sales_order_status import (
    _are_all_payments_completed,
    _is_order_services_completed,
)


class TestAccountUtils(FrappeTestCase):
    def test_get_autoname_with_number(self):
        with unittest_patch(frappe, "get_cached_value", "TC"):
            self.assertEqual(utils.get_autoname_with_number("1000", " Cash ", "Co"), "1000 - Cash - TC")
            self.assertEqual(utils.get_autoname_with_number("  ", "Cash", "Co"), "Cash - TC")
            self.assertEqual(utils.get_autoname_with_number(None, "Cash", "Co"), "Cash - TC")

    def test_sort_accounts_numbered_and_plain(self):
        accs = [frappe._dict(name="2000 - B"), frappe._dict(name="1000 - A")]
        utils.sort_accounts(accs)
        self.assertEqual([a.name for a in accs], ["1000 - A", "2000 - B"])
        plain = [frappe._dict(name="Zed"), frappe._dict(name="Alpha")]
        utils.sort_accounts(plain)
        self.assertEqual([a.name for a in plain], ["Alpha", "Zed"])

    def test_sort_accounts_root_types(self):
        roots = [
            frappe._dict(name="Expenses", root_type="Expense", report_type="Profit and Loss"),
            frappe._dict(name="Income", root_type="Income", report_type="Profit and Loss"),
            frappe._dict(name="Equity", root_type="Equity", report_type="Balance Sheet"),
            frappe._dict(name="Liabilities", root_type="Liability", report_type="Balance Sheet"),
            frappe._dict(name="Assets", root_type="Asset", report_type="Balance Sheet"),
        ]
        utils.sort_accounts(roots, is_root=True)
        self.assertEqual([r.root_type for r in roots], ["Asset", "Liability", "Equity", "Income", "Expense"])


class TestSalesOrderStatusHelpers(FrappeTestCase):
    def test_is_order_services_completed(self):
        f = _is_order_services_completed
        self.assertTrue(f("SO", {}, {}, {}))
        self.assertTrue(f("SO", {"SO": [("S", "Marketing")]}, {"Marketing": True}, {}))
        self.assertFalse(f("SO", {"SO": [("S", "Marketing")]}, {"Marketing": False}, {}))
        self.assertFalse(f("SO", {"SO": [("S", "Marketing"), ("T", "Marketing")]}, {}, {}))

    def test_all_payments_completed(self):
        def so(*statuses):
            return frappe._dict(payment_terms=[frappe._dict(payment_status=s) for s in statuses])

        self.assertFalse(_are_all_payments_completed(so()))
        self.assertTrue(_are_all_payments_completed(so("Verified", " Verified ")))
        self.assertFalse(_are_all_payments_completed(so("Verified", "Pending Verification")))
        self.assertFalse(_are_all_payments_completed(so(None)))


def unittest_patch(obj, name, value):
    from unittest import mock

    return mock.patch.object(obj, name, return_value=value)
