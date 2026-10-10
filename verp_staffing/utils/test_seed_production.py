from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import seed_production as sp

SEED = "verp_staffing.utils.seed_test_data.run_production"


class Conf(dict):
	pass


def with_conf(**kw):
	return mock.patch.object(frappe, "conf", frappe._dict(kw))


class TestLoginLabel(FrappeTestCase):
	def test_sequence(self):
		self.assertEqual(sp._login_label(0), "a")
		self.assertEqual(sp._login_label(25), "z")
		self.assertEqual(sp._login_label(26), "aa")
		self.assertEqual(sp._login_label(27), "ab")
		self.assertEqual(sp._login_label(51), "az")
		self.assertEqual(sp._login_label(52), "ba")
		self.assertEqual(sp._login_label(701), "zz")
		self.assertEqual(sp._login_label(702), "aaa")

	def test_unique(self):
		labels = {sp._login_label(i) for i in range(2000)}
		self.assertEqual(len(labels), 2000)


class TestAfterMigrate(FrappeTestCase):
	def run_it(self, conf, marker=None, companies=1, side_effect=None):
		with with_conf(**conf), mock.patch.object(frappe.db, "get_global", return_value=marker), \
			mock.patch.object(frappe.db, "count", return_value=companies), \
			mock.patch.object(frappe.db, "set_global") as sg, \
			mock.patch.object(frappe.db, "set_single_value") as ssv, \
			mock.patch.object(frappe.db, "commit"), mock.patch.object(frappe.db, "rollback") as rb, \
			mock.patch.object(frappe, "log_error") as le, \
			mock.patch(SEED, side_effect=side_effect) as seed:
			sp.after_migrate()
		return seed, sg, ssv, rb, le

	def test_skip_flag(self):
		seed, *_ = self.run_it({"skip_demo_seed": 1})
		seed.assert_not_called()

	def test_developer_mode_blocks_unless_forced(self):
		seed, *_ = self.run_it({"developer_mode": 1})
		seed.assert_not_called()
		seed, *_ = self.run_it({"developer_mode": 1, "force_demo_seed": 1})
		seed.assert_called_once_with(count=sp.COUNT)

	def test_only_once(self):
		seed, *_ = self.run_it({}, marker="1")
		seed.assert_not_called()

	def test_needs_company(self):
		seed, *_ = self.run_it({}, companies=0)
		seed.assert_not_called()

	def test_success_sets_marker_and_resets_removed_flag(self):
		seed, sg, ssv, *_ = self.run_it({})
		sg.assert_called_once_with(sp.MARKER, "1")
		args = ssv.call_args[0]
		self.assertEqual(args[2], 0)

	def test_failure_is_swallowed(self):
		seed, sg, ssv, rb, le = self.run_it({}, side_effect=RuntimeError("x"))
		rb.assert_called_once()
		le.assert_called_once()
		sg.assert_not_called()


class TestPortalAccess(FrappeTestCase):
	def run_it(self, conf, markers, apps=("vruglechat",), role=True):
		with with_conf(**conf), mock.patch.object(frappe.db, "get_global", side_effect=lambda k: markers.get(k)), \
			mock.patch.object(frappe, "get_installed_apps", return_value=list(apps)), \
			mock.patch.object(frappe.db, "exists", return_value=role), \
			mock.patch.object(frappe.db, "set_global") as sg, mock.patch.object(frappe.db, "commit"), \
			mock.patch.object(frappe.db, "rollback"), mock.patch.object(frappe, "log_error") as le, \
			mock.patch.object(sp, "grant_sample_customers_portal_access", return_value=[("a@vrugle.com", "C")]) as g:
			sp.portal_access_after_migrate()
		return g, sg, le

	def test_guards(self):
		seeded = {sp.MARKER: "1"}
		g, *_ = self.run_it({"skip_demo_seed": 1}, seeded)
		g.assert_not_called()
		g, *_ = self.run_it({"developer_mode": 1}, seeded)
		g.assert_not_called()
		g, *_ = self.run_it({}, {**seeded, sp.PORTAL_MARKER: "1"})
		g.assert_not_called()
		g, *_ = self.run_it({}, seeded, apps=())
		g.assert_not_called()
		g, *_ = self.run_it({}, seeded, role=False)
		g.assert_not_called()
		g, *_ = self.run_it({}, {})  # no demo data yet
		g.assert_not_called()

	def test_runs_and_marks(self):
		g, sg, _ = self.run_it({}, {sp.MARKER: "1"})
		g.assert_called_once()
		sg.assert_called_once_with(sp.PORTAL_MARKER, "1")


class TestGrant(FrappeTestCase):
	def test_nothing_tracked(self):
		with mock.patch("verp_staffing.utils.sample_data_tracking._read_log", return_value={}):
			self.assertEqual(sp.grant_sample_customers_portal_access(), [])
