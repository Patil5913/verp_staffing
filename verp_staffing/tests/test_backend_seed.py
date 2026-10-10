"""Seed generators: the pure helpers, the data tables and the "run once" guards. The seeds themselves
write a lot of data and commit, so nothing here runs them against the database."""

import random
from datetime import date, timedelta
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import seed_demo_journeys as journeys
from verp_staffing.utils import seed_documentation_data as seed
from verp_staffing.utils import seed_refund_data as refunds


class TestSeedTables(FrappeTestCase):
	def test_plan_has_one_entry_per_customer(self):
		self.assertEqual(len(seed.PLAN), seed.CUSTOMERS)

	def test_plan_stages_and_payment_plans_are_known(self):
		stages = {"new", "sales", "resume", "marketing", "jdc", "technical", "cr", "onboarding", "placed"}
		plans = {"none", "advance", "pending", "partial", "full", "overdue", "rejected"}
		for stage, _status, plan in seed.PLAN:
			self.assertIn(stage, stages)
			self.assertIn(plan, plans)

	def test_every_region_prices_every_service(self):
		self.assertEqual(set(seed.RATES), {"usa", "india"})
		self.assertEqual(set(seed.RATES["usa"]), set(seed.RATES["india"]))
		for prices in seed.RATES.values():
			for service, options in prices.items():
				self.assertTrue(options and all(p > 0 for p in options), service)

	def test_modes_and_banks_line_up_per_region(self):
		self.assertEqual(set(seed.MODES), set(seed.COMPANIES))
		for region, weights in seed.BANK_WEIGHTS.items():
			self.assertEqual(len(weights), len(seed.BANKS[region]), region)

	def test_staff_keys_used_by_the_teams_exist(self):
		keys = {s[0] if isinstance(s, (tuple, list)) else s.get("key") for s in seed.STAFF}
		for team in (seed.LEAD_TEAM, seed.SALES_TEAM, seed.MARKETING_TEAM):
			self.assertTrue(set(team) <= keys, set(team) - keys)

	def test_markers_are_distinct(self):
		self.assertEqual(len({seed.MARKER, refunds.MARKER, journeys.MARKER, journeys.JOURNEY_MARKER}), 4)


class TestSeedHelpers(FrappeTestCase):
	def setUp(self):
		random.seed(7)

	def test_people_are_unique_and_the_requested_count(self):
		people = seed._people(60)
		self.assertEqual(len(people), 60)
		self.assertEqual(len({p["name"] for p in people}), 60)
		self.assertEqual(sum(1 for p in people if p["indian"]), int(60 * 0.7))

	def test_fill_person_for_usa_and_india(self):
		us = seed._fill_person({"first": "Ann", "last": "O'Neil Lee"}, "usa")
		self.assertTrue(us["phone"].startswith("+1 ("))
		self.assertEqual(us["country"], "United States")
		self.assertRegex(us["email"], r"^ann\.oneillee\d*@")
		self.assertTrue(us["visa"])
		inn = seed._fill_person({"first": "Ravi", "last": "Kumar"}, "india")
		self.assertTrue(inn["phone"].startswith("+91 "))
		self.assertEqual((inn["country"], inn["visa"]), ("India", ""))
		for p in (us, inn):
			self.assertTrue(p["google_voice"].startswith("+1 ("))
			self.assertTrue(p["tech"] and p["target_role"] and p["address"])

	def test_dates_are_relative_to_today(self):
		self.assertEqual(seed._today(), frappe.utils.getdate(frappe.utils.nowdate()))
		self.assertEqual(seed._ago(10), seed._today() - timedelta(days=10))

	def test_reference_formats_per_payment_mode(self):
		day = date(2026, 3, 9)
		for mode in sum(seed.MODES.values(), []):
			ref = seed._reference("x", mode, day)
			self.assertTrue(ref and ref.isalnum() or "-" in ref, mode)
		self.assertTrue(seed._reference("usa", "ACH Transfer", day).startswith("ACH20260309"))
		self.assertTrue(seed._reference("india", "NEFT", day).startswith("NEFT20260309"))
		self.assertTrue(seed._reference("india", "UPI", day).isdigit())

	def test_sales_order_items_follow_the_stage(self):
		names = lambda items: [n for n, _ in items]
		self.assertEqual(names(seed._sales_order_items("new", 0, "usa", 0)), [])
		self.assertEqual(names(seed._sales_order_items("resume", 0, "usa", 0)), ["Resume", "Cover Letter"])
		self.assertEqual(names(seed._sales_order_items("marketing", 0, "usa", 1)), ["Marketing", "Resume"])
		self.assertEqual(names(seed._sales_order_items("marketing", 0, "usa", 2)), ["Marketing"])
		for n, price in seed._sales_order_items("onboarding", 0, "india", 0):
			self.assertIn(price, seed.RATES["india"][n])

	def test_later_orders_are_follow_on_services(self):
		for _ in range(20):
			items = seed._sales_order_items("placed", 1, "usa", 0)
			self.assertTrue(items and all(n in seed.RATES["usa"] for n, _ in items))

	def test_unknown_stage_is_rejected(self):
		with self.assertRaises(KeyError):
			seed._sales_order_items("bogus", 0, "usa", 0)

	def test_wanted_status_only_if_the_doctype_offers_it(self):
		meta = mock.Mock(); meta.get_field.return_value = mock.Mock(options="Open\nClosed")
		with mock.patch.object(seed.frappe, "get_meta", return_value=meta):
			self.assertEqual(seed._wanted_status("X", "Open"), "Open")
			self.assertIsNone(seed._wanted_status("X", "Nope"))


class TestSeedPlumbing(FrappeTestCase):
	def setUp(self):
		seed._tracks.clear(); seed._errors.clear()

	def tearDown(self):
		seed._tracks.clear(); seed._errors.clear()

	def test_track_ignores_blank_names(self):
		seed._track("Lead", ""); seed._track("Lead", "L-1")
		self.assertEqual(seed._tracks, [("Lead", "L-1")])

	def test_flush_tracks_merges_without_duplicates(self):
		seed._track("Lead", "L-1"); seed._track("Lead", "L-2")
		with mock.patch.object(seed.tracking, "_read_log", return_value={"Lead": ["L-1"]}), mock.patch.object(seed.tracking, "_write_log") as w:
			seed._flush_tracks()
		w.assert_called_once_with({"Lead": ["L-1", "L-2"]})
		self.assertEqual(seed._tracks, [])

	def test_flush_with_nothing_tracked_writes_nothing(self):
		with mock.patch.object(seed.tracking, "_write_log") as w:
			seed._flush_tracks()
		w.assert_not_called()

	def test_attempt_returns_the_result(self):
		with mock.patch.object(seed.frappe.db, "savepoint"):
			self.assertEqual(seed._attempt("ok", lambda: 42), 42)
		self.assertEqual(seed._errors, [])

	def test_failed_attempt_rolls_back_forgets_its_tracks_and_records_the_error(self):
		seed._track("Lead", "KEEP")
		def boom():
			seed._track("Lead", "LOST")
			raise ValueError("first line\nsecond line")
		with mock.patch.object(seed.frappe.db, "savepoint"), mock.patch.object(seed.frappe.db, "rollback") as rb, mock.patch.object(seed.frappe, "log_error"):
			self.assertIsNone(seed._attempt("step", boom))
		rb.assert_called_once()
		self.assertEqual(seed._tracks, [("Lead", "KEEP")])
		self.assertEqual(seed._errors, ["step: first line"])

	def test_rollback_failure_falls_back_to_a_full_rollback(self):
		with mock.patch.object(seed.frappe.db, "savepoint"), mock.patch.object(seed.frappe.db, "rollback", side_effect=[Exception("no savepoint"), None]) as rb, mock.patch.object(
			seed.frappe, "log_error"
		):
			seed._attempt("x", lambda: 1 / 0)
		self.assertEqual(rb.call_count, 2)

	def test_insert_untracked_and_tracked(self):
		doc = mock.Mock(doctype="Lead"); doc.name = "L-1"
		self.assertIs(seed._insert(doc), doc)
		doc.insert.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(seed._tracks, [("Lead", "L-1")])
		with mock.patch.object(seed.tracking, "insert_tracked") as ins:
			seed._insert(doc, tracked=True)
		ins.assert_called_once_with(doc)

	def test_set_owner_skips_blank_users(self):
		with mock.patch.object(seed.frappe.db, "set_value") as sv:
			seed._set_owner("Lead", "L-1", "")
			seed._set_owner("Lead", "L-1", "a@x.com")
		sv.assert_called_once_with("Lead", "L-1", "owner", "a@x.com", update_modified=False)

	def test_stamp_backdates_creation_and_modified_together(self):
		with mock.patch.object(seed.frappe.db, "set_value") as sv:
			seed._stamp("Lead", "L-1", date(2026, 1, 2), hour=9)
		vals = sv.call_args[0][2]
		self.assertEqual(vals["creation"], vals["modified"])
		self.assertTrue(vals["creation"].startswith("2026-01-02 09:"))
		self.assertFalse(sv.call_args.kwargs["update_modified"])


class TestSeedRunGuards(FrappeTestCase):
	def test_documentation_seed_runs_once_unless_forced(self):
		with mock.patch.object(seed.frappe.db, "get_global", return_value="1"), mock.patch.object(seed, "_ensure_config") as step:
			self.assertEqual(seed.run(), {})
		step.assert_not_called()

	def test_documentation_seed_needs_departments_and_roles(self):
		with mock.patch.object(seed.frappe.db, "get_global", return_value=None), mock.patch.object(seed.frappe.db, "count", return_value=0), mock.patch.object(
			seed, "_ensure_config"
		) as step:
			self.assertEqual(seed.run(), {})
		step.assert_not_called()

	def test_after_migrate_is_opt_in_and_once(self):
		with mock.patch.object(seed, "run") as run:
			with mock.patch.object(seed.frappe, "conf", frappe._dict()):
				seed.after_migrate()
			with mock.patch.object(seed.frappe, "conf", frappe._dict(seed_documentation_data=1)), mock.patch.object(seed.frappe.db, "get_global", return_value="1"):
				seed.after_migrate()
			with mock.patch.object(seed.frappe, "conf", frappe._dict(seed_documentation_data=1)), mock.patch.object(
				seed.frappe.db, "get_global", return_value=None
			), mock.patch.object(seed.frappe.db, "count", return_value=0):
				seed.after_migrate()
		run.assert_not_called()

	def test_a_failing_seed_never_blocks_migrate(self):
		with mock.patch.object(seed.frappe, "conf", frappe._dict(seed_documentation_data=1)), mock.patch.object(
			seed.frappe.db, "get_global", return_value=None
		), mock.patch.object(seed.frappe.db, "count", return_value=3), mock.patch.object(seed, "run", side_effect=RuntimeError), mock.patch.object(
			seed.frappe.db, "rollback"
		) as rb, mock.patch.object(seed.frappe, "log_error") as log:
			seed.after_migrate()
		rb.assert_called_once()
		log.assert_called_once()

	def test_refund_seed_runs_once_unless_forced(self):
		with mock.patch.object(refunds.frappe.db, "get_global", return_value="1"), mock.patch.object(refunds.base, "_create_staff") as step:
			self.assertEqual(refunds.run(), {})
		step.assert_not_called()

	def test_demo_journeys_after_migrate_conditions(self):
		def run_with(conf, globals_):
			with mock.patch.object(journeys.frappe, "conf", frappe._dict(conf)), mock.patch.object(
				journeys.frappe.db, "get_global", side_effect=lambda k: globals_.get(k)
			), mock.patch.object(journeys, "seed_demo_journeys") as s, mock.patch.object(journeys.frappe.db, "set_global"), mock.patch.object(
				journeys.frappe.db, "commit"
			):
				journeys.demo_journeys_after_migrate()
			return s.called
		ready = {journeys.MARKER: "1", journeys.PORTAL_MARKER: "1"}
		self.assertTrue(run_with({}, ready))
		self.assertFalse(run_with({"skip_demo_seed": 1}, ready))
		self.assertFalse(run_with({"developer_mode": 1}, ready))
		self.assertTrue(run_with({"developer_mode": 1, "force_demo_seed": 1}, ready))
		self.assertFalse(run_with({}, {**ready, journeys.JOURNEY_MARKER: "1"}))
		self.assertFalse(run_with({}, {journeys.MARKER: "1"}))
		self.assertFalse(run_with({}, {journeys.PORTAL_MARKER: "1"}))
