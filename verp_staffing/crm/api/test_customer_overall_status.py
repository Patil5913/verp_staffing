import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import customer_overall_status as cos


def run(exists=(), stage=None, status=None, get_all=None):
    """compute_customer_status with the DB faked: `exists` is the set of (doctype, status) rows present,
    `status` maps a service doctype to its row status."""
    status = status or {}

    def fake_exists(doctype, filters=None):
        return (doctype, (filters or {}).get("status")) in set(exists)

    def fake_get_value(doctype, filters, field=None):
        if doctype == "Customer":
            return json.dumps(stage) if stage is not None else None
        return status.get(doctype)

    with mock.patch.object(frappe.db, "exists", side_effect=fake_exists), \
         mock.patch.object(frappe.db, "get_value", side_effect=fake_get_value), \
         mock.patch.object(frappe, "get_all", side_effect=get_all or (lambda *a, **k: [])):
        return cos.compute_customer_status("C-1")


def ts(minutes):
    return {"timestamp": f"2026-01-01T10:{minutes:02d}:00", "department": "Technical"}


class TestResolveStatus(FrappeTestCase):
    def test_resolve_status(self):
        row = lambda s: frappe._dict(status=s)
        self.assertIsNone(cos._resolve_status([]))
        self.assertEqual(cos._resolve_status([row("Completed")]), "Completed")
        self.assertEqual(cos._resolve_status([row("Completed"), row("Pending"), row("Started")]), "Pending")
        self.assertEqual(cos._resolve_status([row(None), row("Started")]), "Started")


class TestComputeCustomerStatus(FrappeTestCase):
    def test_hard_overrides_in_priority_order(self):
        self.assertEqual(run(exists={("Refund Request", "Pending Verification")}), "Refund Pending")
        self.assertEqual(run(exists={("CR", "Refund Pending"), ("CR", "Backout")}), "Refund Pending")
        self.assertEqual(run(exists={("CR", "Refund Rejected")}), "Refund Rejected")
        self.assertEqual(run(exists={("CR", "Dispute Pending")}), "Moved To CR")
        self.assertEqual(run(exists={("Onboardings", "Active"), ("CR", "Backout")}), "Moved To Onboarding")
        self.assertEqual(run(exists={("CR", "Refund")}), "Backout and Refund")
        self.assertEqual(run(exists={("CR", "Backout")}), "Backout")
        self.assertEqual(run(exists={("Onboardings", "Completed")}), "Customer Placed")

    def test_no_stage_is_ready(self):
        self.assertEqual(run(), "Ready")
        self.assertEqual(run(stage={}), "Ready")

    def test_bad_stage_json_is_ready(self):
        with mock.patch.object(frappe.db, "exists", return_value=False), \
             mock.patch.object(frappe.db, "get_value", return_value="{not json"):
            self.assertEqual(cos.compute_customer_status("C"), "Ready")

    def test_marketing_states(self):
        stage = {"marketing": []}
        cases = {
            None: "Marketing Pending", "Pending": "Marketing Pending", "Request for Update": "Marketing Rework",
            "Started": "Marketing In Progress", "Hold": "Marketing On Hold", "Completed": "Marketing Completed",
        }
        for st, expected in cases.items():
            self.assertEqual(run(stage=stage, status={"Marketing": st}), expected, st)

    def test_resume_and_ruc(self):
        self.assertEqual(run(stage={"resume": []}, status={}), "Resume Pending")
        self.assertEqual(run(stage={"resume": []}, status={"Resume": "Request for Update"}), "Resume Rework")
        self.assertEqual(run(stage={"resume": []}, status={"Resume": "Completed"}), "Ready")
        self.assertEqual(run(stage={"ruc": []}, status={}), "RUC Pending")
        self.assertEqual(run(stage={"ruc": []}, status={"RUC": "Request for Update"}), "RUC Rework")

    def test_marketing_completed_then_resume_pending_wins(self):
        self.assertEqual(run(stage={"marketing": [], "resume": []}, status={"Marketing": "Completed"}), "Resume Pending")

    def test_other_services_use_latest_open_one(self):
        stage = {"alpha": [ts(1)], "beta": [ts(5)]}

        def get_all(doctype, **kw):
            if doctype == "Technical Other Services":
                return [frappe._dict(service="alpha", status="In Progress"), frappe._dict(service="beta", status="Completed")]
            return []

        with mock.patch.dict(cos.SERVICE_DOCTYPE_MAP, {}, clear=False):
            self.assertEqual(run(stage=stage, get_all=get_all), "Alpha In Progress")

    def test_events_with_bad_timestamps_are_ignored(self):
        self.assertEqual(run(stage={"alpha": [{"timestamp": "garbage"}]}), "Ready")

    def test_mapped_service_uses_its_doctype(self):
        key, doctype = next((k, v) for k, v in cos.SERVICE_DOCTYPE_MAP.items() if k not in cos.PRIORITY_SERVICES)
        stage = {key: [ts(1)]}

        def get_all(dt, **kw):
            return [frappe._dict(status="Request for Update", modified=1)] if dt == doctype else []

        self.assertEqual(run(stage=stage, get_all=get_all), f"{key.title()} Rework")
