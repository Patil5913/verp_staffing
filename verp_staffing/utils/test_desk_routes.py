from unittest import mock

from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import desk_routes as dr

SLUGS = {"sales-order": "Sales Order", "account": "Account"}


class TestDeskRoutes(FrappeTestCase):
    def setUp(self):
        p = mock.patch.object(dr, "get_doctype_slugs", return_value=SLUGS)
        p.start()
        self.addCleanup(p.stop)

    def test_slug(self):
        self.assertEqual(dr._slug("Sales Order"), "sales-order")

    def test_spa_path(self):
        self.assertEqual(dr.spa_path("Sales Order"), "/verp/Sales%20Order")
        self.assertEqual(dr.spa_path("Sales Order", "SO/1"), "/verp/Sales%20Order/SO%2F1")

    def test_link_to_form_escapes_label(self):
        self.assertEqual(dr.link_to_form("Lead", "L-1", "<b>x</b>"), '<a href="/verp/Lead/L-1">&lt;b&gt;x&lt;/b&gt;</a>')

    def test_desk_path_to_spa(self):
        f = dr.desk_path_to_spa
        self.assertEqual(f("/app/sales-order/SO-1"), "/verp/Sales%20Order/SO-1")
        self.assertEqual(f("/app/sales-order"), "/verp/Sales%20Order")
        self.assertEqual(f("/app/sales-order/view/list"), "/verp/Sales%20Order")
        self.assertEqual(f("/app/account/view/tree"), "/verp/Account/view/tree")
        self.assertEqual(f("/app/sales-order/new-sales-order-1"), "/verp/Sales%20Order")
        self.assertEqual(f("/app/sales-order/SO-1?x=1#h"), "/verp/Sales%20Order/SO-1")
        self.assertEqual(f("/app"), "/verp")
        self.assertEqual(f("/app/setup"), "/verp/setup")
        self.assertEqual(f("/app/query-report/My Report"), "/verp/report/My%20Report")
        self.assertEqual(f("/app/erp-configuration"), "/verp/settings/ERP%20Configuration")
        self.assertIsNone(f("/app/e-sign/ES-1"))
        self.assertEqual(f("/app/unknown-thing"), "/verp")
