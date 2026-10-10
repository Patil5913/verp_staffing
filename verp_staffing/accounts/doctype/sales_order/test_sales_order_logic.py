import json
import random
from types import SimpleNamespace as N
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.sales_order import sales_order as so


def single(**kw):
    base = dict(
        candidate_details_form_fields=None,
        send_candidate_form_immediatly_after_sales_order_creation=0,
        send_agreement_immediatly_after_sales_order_creation=1,
    )
    base.update(kw)
    return N(**base)


class TestErpConfig(FrappeTestCase):
    def config(self, fields=None, **kw):
        raw = json.dumps(fields) if isinstance(fields, (dict, list)) else fields
        with mock.patch.object(frappe, "get_single", return_value=single(candidate_details_form_fields=raw, **kw)):
            return so.get_erp_config()

    def test_flags(self):
        cfg = self.config()
        self.assertEqual((cfg["send_candidate_form_immediately"], cfg["send_agreement_immediately"]), (False, True))
        self.assertEqual(cfg["service_config"], {})

    def test_normalises_every_supported_shape(self):
        cfg = self.config({
            "resume": {"fields": ["a", {"field_name": "b", "is_required": 1}, {"field": "c"}, {"fieldname": "d"}, {"x": 1}, 5], "is_agreement_required": 1},
            "ruc": ["e", "f"],
            "jdc": "garbage",
            "cl": {"is_candidate_form_required": True},
        })["service_config"]
        self.assertEqual(cfg["resume"]["fields"], [
            {"field_name": "a", "is_required": False}, {"field_name": "b", "is_required": True},
            {"field_name": "c", "is_required": False}, {"field_name": "d", "is_required": False},
        ])
        self.assertTrue(cfg["resume"]["is_agreement_required"])
        self.assertFalse(cfg["resume"]["is_candidate_form_required"])
        self.assertEqual([f["field_name"] for f in cfg["ruc"]["fields"]], ["e", "f"])
        self.assertEqual(cfg["jdc"], {"fields": [], "is_agreement_required": False, "is_candidate_form_required": False})
        self.assertTrue(cfg["cl"]["is_candidate_form_required"])

    def test_broken_json_is_reported(self):
        with self.assertRaises(frappe.ValidationError):
            self.config("{not json")


class TestRequirements(FrappeTestCase):
    CONFIG = {"service_config": {
        "resume": {"is_agreement_required": True, "is_candidate_form_required": False},
        "ruc": {"is_agreement_required": False, "is_candidate_form_required": True},
        "plain": {},
    }}

    def req(self, *items):
        return so.get_requirements_from_config(N(items=[N(item=i) for i in items]), self.CONFIG)

    def test_each_service_contributes_its_own_requirement(self):
        self.assertEqual(self.req("resume"), {"agreement_required": True, "candidate_required": False})
        self.assertEqual(self.req("ruc"), {"agreement_required": False, "candidate_required": True})
        self.assertEqual(self.req("resume", "ruc"), {"agreement_required": True, "candidate_required": True})

    def test_unconfigured_services_and_blank_rows_require_nothing(self):
        self.assertEqual(self.req("plain", "unknown", "", None), {"agreement_required": False, "candidate_required": False})
        self.assertEqual(so.get_requirements_from_config(N(items=None), self.CONFIG), {"agreement_required": False, "candidate_required": False})

    def test_names_are_matched_without_surrounding_space(self):
        self.assertTrue(self.req("  resume ")["agreement_required"])


class TestForwardGate(FrappeTestCase):
    """Forwarding a candidate waits for the form and for signed agreements, when the services need them."""

    def gate(self, orders, reqs, signed=(), lock_form=0, user="u@x.com"):
        prev = frappe.session.user
        frappe.session.user = user
        try:
            with mock.patch.object(frappe, "has_permission"), \
                 mock.patch.object(so, "get_erp_config", return_value={}), \
                 mock.patch.object(frappe, "get_all", return_value=orders), \
                 mock.patch.object(frappe, "get_doc", side_effect=lambda dt, n: N(name=n)), \
                 mock.patch.object(so, "get_requirements_from_config", side_effect=lambda doc, cfg: reqs[doc.name]), \
                 mock.patch.object(frappe.db, "exists", side_effect=lambda dt, f: dt == "E Sign" and f["sales_order"] in signed), \
                 mock.patch.object(frappe.db, "get_value", return_value=lock_form):
                return so.get_forward_gate("C1")
        finally:
            frappe.session.user = prev

    NEEDS_NOTHING = {"agreement_required": False, "candidate_required": False}

    def test_administrator_is_never_blocked(self):
        self.assertEqual(self.gate([], {}, user="Administrator"), {"blocked": False, "reasons": [], "form_required": False, "agreement_required": False})

    def test_services_that_need_nothing_never_block(self):
        out = self.gate(["SO-1"], {"SO-1": self.NEEDS_NOTHING})
        self.assertFalse(out["blocked"])

    def test_waits_for_the_candidate_form(self):
        reqs = {"SO-1": {"agreement_required": False, "candidate_required": True}}
        out = self.gate(["SO-1"], reqs, lock_form=0)
        self.assertTrue(out["blocked"])
        self.assertIn("candidate details form", out["reasons"][0])
        self.assertFalse(self.gate(["SO-1"], reqs, lock_form=1)["blocked"])  # submitting the form locks it

    def test_waits_for_each_unsigned_agreement_and_names_them(self):
        reqs = {"SO-1": {"agreement_required": True, "candidate_required": False}, "SO-2": {"agreement_required": True, "candidate_required": False}}
        out = self.gate(["SO-1", "SO-2"], reqs, signed=["SO-1"])
        self.assertTrue(out["blocked"])
        self.assertEqual(out["reasons"], ["Agreement not signed yet for SO-2."])
        self.assertFalse(self.gate(["SO-1", "SO-2"], reqs, signed=["SO-1", "SO-2"])["blocked"])

    def test_form_and_agreements_can_both_hold_it_back(self):
        reqs = {"SO-1": {"agreement_required": True, "candidate_required": True}}
        out = self.gate(["SO-1"], reqs)
        self.assertEqual(len(out["reasons"]), 2)
        self.assertTrue(out["form_required"] and out["agreement_required"])

    def test_candidate_form_order_is_the_latest_one_that_needs_it(self):
        reqs = {"SO-3": {"candidate_required": False}, "SO-2": {"candidate_required": True}, "SO-1": {"candidate_required": True}}
        with mock.patch.object(frappe, "has_permission"), mock.patch.object(so, "get_erp_config", return_value={}), \
             mock.patch.object(frappe, "get_all", return_value=["SO-3", "SO-2", "SO-1"]), \
             mock.patch.object(frappe, "get_doc", side_effect=lambda dt, n: N(name=n)), \
             mock.patch.object(so, "get_requirements_from_config", side_effect=lambda d, c: reqs[d.name]):
            self.assertEqual(so.get_candidate_form_order("C1"), "SO-2")
        with mock.patch.object(frappe, "has_permission"), mock.patch.object(so, "get_erp_config", return_value={}), \
             mock.patch.object(frappe, "get_all", return_value=[]):
            self.assertIsNone(so.get_candidate_form_order("C1"))


class TestPlatformCharges(FrappeTestCase):
    def pe(self, paid=100, rows=()):
        pe = mock.MagicMock()
        pe.company, pe.paid_amount = "Acme", paid
        state = {"rows": list(rows)}
        pe.get.side_effect = lambda k: state["rows"]
        pe.set.side_effect = lambda k, v: state.__setitem__("rows", v)
        pe.append.side_effect = lambda k, v: state["rows"].append(N(**v))
        pe._state = state
        return pe

    def account(self, **kw):
        base = dict(company="Acme", is_group=0, disabled=0, account_type=sorted(so.CHARGE_ACCOUNT_TYPES)[0])
        base.update(kw)
        return mock.patch.object(frappe.db, "get_value", return_value=frappe._dict(base))

    def test_zero_charges_remove_an_earlier_row_and_add_nothing(self):
        old = N(description=so.PLATFORM_CHARGES_LABEL)
        other = N(description="Something else")
        pe = self.pe(rows=[old, other])
        so._apply_platform_charges(pe, 0, None)
        self.assertEqual(pe._state["rows"], [other])
        pe.append.assert_not_called()

    def test_a_charge_becomes_one_actual_row_replacing_the_previous_attempt(self):
        pe = self.pe(rows=[N(description=so.PLATFORM_CHARGES_LABEL)])
        with self.account():
            so._apply_platform_charges(pe, "-5", "Bank Charges - A")
        rows = pe._state["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].charge_type, rows[0].tax_amount, rows[0].account_head), ("Actual", -5, "Bank Charges - A"))

    def test_needs_an_account(self):
        with self.assertRaises(frappe.ValidationError):
            so._apply_platform_charges(self.pe(), 5, None)

    def test_the_account_must_be_a_usable_expense_account_of_the_same_company(self):
        for bad in (dict(company="Other"), dict(is_group=1), dict(disabled=1), dict(account_type="Bank")):
            with self.account(**bad), self.assertRaises(frappe.ValidationError):
                so._apply_platform_charges(self.pe(), 5, "X")
        with mock.patch.object(frappe.db, "get_value", return_value=None), self.assertRaises(frappe.ValidationError):
            so._apply_platform_charges(self.pe(), 5, "X")

    def test_charges_cannot_eat_the_whole_payment(self):
        with self.account():
            for charge in (-100, -150):
                with self.assertRaises(frappe.ValidationError):
                    so._apply_platform_charges(self.pe(paid=100), charge, "X")
            so._apply_platform_charges(self.pe(paid=100), -99.99, "X")


class TestProration(FrappeTestCase):
    """A payment term's invoice is cut from the order's items so its total is EXACTLY what was received."""

    def run_proration(self, amounts, target):
        si = mock.MagicMock()
        rows = []
        si.append.side_effect = lambda k, v: rows.append(v)
        order = N(items=[N(item=f"I{i}", amount=a, uom="Nos", type="Sales") for i, a in enumerate(amounts)])
        term = N(received_amount=target, company="Acme")
        with mock.patch("verp_staffing.accounts.api.get_defaults.get_default_company_account", return_value="Sales - A"):
            so._append_prorated_items(si, order, term)
        return rows

    def test_a_single_item_takes_the_whole_amount(self):
        rows = self.run_proration([500], 123.45)
        self.assertEqual([(r["item"], r["qty"], r["rate"]) for r in rows], [("I0", 1, 123.45)])
        self.assertEqual(rows[0]["income_account"], "Sales - A")

    def test_several_items_split_in_proportion_and_add_up_exactly(self):
        rows = self.run_proration([100, 300], 400)
        self.assertEqual([r["rate"] for r in rows], [100, 300])

    def test_the_last_row_absorbs_the_rounding_remainder(self):
        rows = self.run_proration([1, 1, 1], 100)
        self.assertEqual(sum(r["rate"] for r in rows), 100)
        self.assertEqual([r["rate"] for r in rows[:-1]], [33, 33])
        self.assertEqual(rows[-1]["rate"], 34)

    def test_the_total_is_always_exact(self):
        rng = random.Random(7)
        for _ in range(200):
            amounts = [rng.randint(1, 5000) for _ in range(rng.randint(2, 6))]
            target = rng.randint(1, 100000)
            rows = self.run_proration(amounts, target)
            self.assertEqual(sum(r["rate"] for r in rows), target, (amounts, target))
            self.assertTrue(all(r["qty"] == 1 for r in rows))

    def test_a_zero_value_order_falls_back_to_the_first_item(self):
        rows = self.run_proration([0, 0], 50)
        self.assertEqual([(r["item"], r["rate"]) for r in rows], [("I0", 50)])

    def test_no_items_is_an_error(self):
        with self.assertRaises(frappe.ValidationError):
            self.run_proration([], 10)


class TestSmallHelpers(FrappeTestCase):
    def test_verification_log_appends_timestamped_lines(self):
        doc = N(verification_log=None, save=mock.Mock())
        so._append_verification_log(doc, "first", "T1")
        so._append_verification_log(doc, "second", "T2")
        self.assertEqual(doc.verification_log, "[T1] first\n[T2] second")
        self.assertEqual(doc.save.call_count, 2)

    def test_sales_owner_recipient_prefers_the_customers_owner(self):
        order = N(customer="C1", owner="creator@x.com")
        with mock.patch.object(frappe.db, "get_value", return_value="EMP-1"), mock.patch.object(frappe, "get_cached_value", return_value="owner@x.com"):
            self.assertEqual(so._get_sales_owner_recipients(order), ["owner@x.com"])
        with mock.patch.object(frappe.db, "get_value", return_value=None):
            self.assertEqual(so._get_sales_owner_recipients(order), ["creator@x.com"])
        with mock.patch.object(frappe.db, "get_value", return_value="EMP-1"), mock.patch.object(frappe, "get_cached_value", return_value=None):
            self.assertEqual(so._get_sales_owner_recipients(order), ["creator@x.com"])
