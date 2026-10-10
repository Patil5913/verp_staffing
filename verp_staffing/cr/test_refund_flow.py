# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

"""Backout refund flow: allocation and fee, the books at each step (request / verify / reject / cancel), and what the
hold and backout do to the candidate's services."""

import uuid
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, now_datetime

from verp_staffing.accounts.doctype.account.test_account import create_account_if_not_exists
from verp_staffing.accounts.doctype.payment_entry.test_payment_entry import make_payment_entry
from verp_staffing.accounts.doctype.sales_invoice.test_sales_invoice import (
    _resolved,
    _seed_all,
    make_sales_invoice,
)
from verp_staffing.accounts.doctype.sales_order.sales_order import (
    PLATFORM_CHARGES_LABEL,
    reject_payment_entry,
    verify_payment_entry,
)
from verp_staffing.cr import backout, refund
from verp_staffing.crm.doctype.customer.test_customer import make_customer

BANK = {"account_holder_name": "A Candidate", "bank_name": "Test Bank", "account_number": "123456789"}


def gl_totals(voucher_type, voucher_no):
    """{account: net debit} over all of a voucher's GL entries. A cancelled voucher keeps its entries and gains
    reversing ones, so after a cancel every account nets to zero."""
    out = {}
    for e in frappe.get_all(
        "GL Entry",
        filters={"voucher_type": voucher_type, "voucher_no": voucher_no},
        fields=["account", "debit", "credit"],
    ):
        out[e.account] = flt(out.get(e.account, 0) + flt(e.debit) - flt(e.credit), 2)
    return out


class RefundFlowTestCase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_all()
        cls.company = _resolved["company"]
        cls.income = _resolved["income_account"]
        cls.debtors = _resolved["receivable_account"]
        cls.bank = _resolved["cash_account"]
        cls.fee_account = create_account_if_not_exists(
            "Test Bank Charges", cls.company, root_type="Expense", account_type="Expense Account"
        ).name
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()
        super().tearDownClass()

    # -- builders ------------------------------------------------------------------------------------------

    def new_customer(self):
        return make_customer(f"_Test Refund {uuid.uuid4().hex[:8]}").name

    def paid_invoice(self, customer, amount, fee=0, posting_date=None, tax_rate=0):
        """A submitted invoice with a verified receipt; `fee` is what the platform kept (the negative
        'Platform / Other Charges' row on the receipt). With a tax_rate the customer pays the amount plus tax."""
        si = make_sales_invoice(
            amount=amount, submit=True, customer=customer,
            taxes=[{"charge_type": "On Net Total", "rate": tax_rate}] if tax_rate else None,
        )
        amount = flt(si.rounded_total) or flt(si.grand_total)
        taxes = []
        if fee:
            taxes = [
                {
                    "charge_type": "Actual", "account_head": self.fee_account, "description": PLATFORM_CHARGES_LABEL,
                    "tax_amount": -fee, "add_deduct_tax": "Add",
                }
            ]
        extra = {"posting_date": posting_date} if posting_date else {}
        pe = make_payment_entry(
            payment_type="Receive", company=self.company, party=customer, paid_from=self.debtors, paid_to=self.bank,
            paid_amount=amount, taxes=taxes, **extra,
            references=[{"reference_doctype": "Sales Invoice", "reference_name": si.name, "total_amount": amount,
                         "outstanding_amount": amount, "allocated_amount": amount}],
        )
        pe.submit()
        return si, pe

    def open_cr(self, customer):
        cr = frappe.get_doc(
            {
                "doctype": "CR", "customer": customer,
                "cr_history": [
                    {"reason_for_forwarding": "test", "forwarded_by": "Administrator", "forwarded_from_department": "Sales", "status": "Dispute Pending",
                     "forwarded_on": now_datetime()}
                ],
            }
        ).insert(ignore_permissions=True)
        return cr

    def request_refund(self, cr, amount, fee=None):
        return refund.create_refund_request(cr=cr.name, amount=amount, reason="candidate left", fee=fee, **BANK)

    def service(self, doctype, customer, status="Pending"):
        doc = frappe.new_doc(doctype)
        doc.customer = customer
        doc.status = status
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return doc


class TestRefundAllocation(RefundFlowTestCase):
    def test_newest_payment_is_refunded_first_and_each_touched_payments_fee_is_charged_flat(self):
        customer = self.new_customer()
        old_si, old_pe = self.paid_invoice(customer, 1000, fee=3, posting_date="2026-01-05")
        new_si, new_pe = self.paid_invoice(customer, 600, fee=2, posting_date="2026-03-05")

        cr = self.open_cr(customer)
        preview = refund.get_refund_preview(cr.name, amount=800)

        self.assertEqual(preview["refundable_total"], 1600)
        rows = preview["rows"]
        self.assertEqual([r["sales_invoice"] for r in rows], [new_si.name, old_si.name])
        self.assertEqual([r["refund_amount"] for r in rows], [600, 200])
        # fee is flat per payment the refund touches: all of the newer receipt's 2 and all of the older receipt's 3,
        # although only 200 of the older 1000 is refunded
        self.assertEqual([r["fee_share"] for r in rows], [2, 3])
        self.assertEqual(preview["fee_default"], 5)
        self.assertEqual(preview["net_payout"], 795)

    def test_fee_does_not_shrink_with_a_smaller_refund_and_skips_untouched_payments(self):
        customer = self.new_customer()
        self.paid_invoice(customer, 1000, fee=3, posting_date="2026-01-05")
        self.paid_invoice(customer, 600, fee=2, posting_date="2026-03-05")
        cr = self.open_cr(customer)

        # 10 out of the newest payment only: its whole fee, none of the older payment's
        small = refund.get_refund_preview(cr.name, amount=10)
        self.assertEqual((small["fee_default"], small["net_payout"]), (2, 8))
        # a payment with no recorded fee adds nothing
        customer2 = self.new_customer()
        self.paid_invoice(customer2, 1000)
        cr2 = self.open_cr(customer2)
        self.assertEqual(refund.get_refund_preview(cr2.name, amount=500)["fee_default"], 0)

    def test_fee_can_be_overridden_but_not_swallow_the_refund(self):
        customer = self.new_customer()
        self.paid_invoice(customer, 1000, fee=3)
        cr = self.open_cr(customer)

        self.assertEqual(refund.get_refund_preview(cr.name, amount=500, fee=0)["net_payout"], 500)
        self.assertEqual(refund.get_refund_preview(cr.name, amount=500, fee=3)["net_payout"], 497)
        with self.assertRaises(frappe.ValidationError):
            refund.get_refund_preview(cr.name, amount=500, fee=500)

    def test_cannot_refund_more_than_was_paid(self):
        customer = self.new_customer()
        self.paid_invoice(customer, 1000)
        cr = self.open_cr(customer)
        with self.assertRaises(frappe.ValidationError):
            refund.get_refund_preview(cr.name, amount=1000.01)


class TestRefundLedger(RefundFlowTestCase):
    def setUp(self):
        self.customer = self.new_customer()
        self.si, self.receipt = self.paid_invoice(self.customer, 1000, fee=3)
        self.cr = self.open_cr(self.customer)

    def test_request_books_nothing_and_asks_for_verification(self):
        res = self.request_refund(self.cr, 500, fee=3)

        rr = frappe.get_doc("Refund Request", res["refund_request"])
        cn = frappe.get_doc("Credit Note", res["credit_note"])
        pe = frappe.get_doc("Payment Entry", res["payment_entry"])
        self.assertEqual((rr.status, cn.docstatus, pe.docstatus), ("Pending Verification", 0, 0))
        self.assertEqual((pe.payment_type, pe.verification_status, pe.refund_request), ("Pay", "Pending Verification", rr.name))
        self.assertEqual((rr.refund_amount, rr.fee_recovered, rr.net_payout), (500, 3, 497))
        self.assertEqual(pe.paid_from, self.bank)
        self.assertFalse(frappe.db.exists("GL Entry", {"voucher_no": ["in", [cn.name, pe.name]]}))
        self.assertEqual(frappe.db.get_value("Customer", self.customer, "overall_status"), "Refund Pending")
        # the CR case itself says Refund Pending while the accountant verifies
        latest = frappe.get_doc("CR", self.cr.name)._get_latest_history_row()
        self.assertEqual(latest.status, "Refund Pending")
        self.assertEqual(frappe.db.get_value("CR", self.cr.name, "status"), "Refund Pending")
        # ...and the history row carries the refund: which request, its status, the amount and a note
        self.assertEqual((latest.refund_request, latest.refund_status, latest.refund_amount), (res["refund_request"], "Pending Verification", 500))
        self.assertEqual(latest.refund_remarks, "candidate left")  # the CR employee's reason, as typed

    def test_second_request_and_resolve_are_blocked_while_one_is_waiting(self):
        self.request_refund(self.cr, 500, fee=3)
        with self.assertRaises(frappe.ValidationError):
            self.request_refund(self.cr, 100, fee=0)
        from verp_staffing.cr.doctype.cr.cr import resolve_or_refund_cr

        with self.assertRaises(frappe.ValidationError):
            resolve_or_refund_cr(self.cr.name, "Dispute Resolved", "sorted")

    def test_verifying_posts_credit_note_and_payment_and_closes_the_case(self):
        res = self.request_refund(self.cr, 500, fee=3)
        verify_payment_entry(res["payment_entry"])

        cn_gl = gl_totals("Credit Note", res["credit_note"])
        self.assertEqual(cn_gl, {self.income: 500, self.debtors: -500})

        # payment: Dr receivable 500; bank pays 500 less the 3 fee it gets back; the absorbed fee is recovered
        pe_gl = gl_totals("Payment Entry", res["payment_entry"])
        self.assertEqual(pe_gl[self.debtors], 500)
        self.assertEqual(pe_gl[self.bank], -497)
        self.assertEqual(pe_gl[self.fee_account], -3)
        self.assertEqual(flt(sum(pe_gl.values()), 2), 0)

        # the customer's receivable nets to zero across both documents
        self.assertEqual(flt(cn_gl[self.debtors] + pe_gl[self.debtors], 2), 0)

        self.assertEqual(frappe.db.get_value("Refund Request", res["refund_request"], "status"), "Refunded")
        self.assertEqual(frappe.db.get_value("Credit Note", res["credit_note"], "docstatus"), 1)
        latest = frappe.get_doc("CR", self.cr.name)._get_latest_history_row()
        self.assertEqual(latest.status, "Refund")
        self.assertEqual(frappe.db.get_value("Customer", self.customer, "overall_status"), "Backout and Refund")

    def test_a_case_waiting_for_a_refund_cannot_be_resolved_or_backed_out(self):
        from verp_staffing.cr.doctype.cr.cr import backout_without_refund

        self.request_refund(self.cr, 500, fee=3)
        with self.assertRaises(frappe.ValidationError):
            backout_without_refund(self.cr.name, "leaving")
        # once the accountant rejects, the same options are open again
        pe = frappe.db.get_value("Refund Request", {"cr": self.cr.name}, "payment_entry")
        reject_payment_entry(pe, "wrong details")
        backout_without_refund(self.cr.name, "leaving")  # allowed from Refund Rejected
        self.assertEqual(frappe.get_doc("CR", self.cr.name)._get_latest_history_row().status, "Backout")

    def test_every_step_is_its_own_entry_in_the_case_log(self):
        """The history is a log: a rejection and a second request sit below the first, nothing is overwritten."""
        first = self.request_refund(self.cr, 500, fee=3)
        reject_payment_entry(first["payment_entry"], "bank details do not match")
        second = self.request_refund(self.cr, 400, fee=3)
        verify_payment_entry(second["payment_entry"])

        log = frappe.get_doc("CR", self.cr.name).cr_events
        self.assertEqual(
            [(e.event, e.status) for e in log],
            [("Refund requested", "Refund Pending"), ("Refund rejected", "Refund Rejected"),
             ("Refund requested", "Refund Pending"), ("Refunded", "Refund")],
        )
        self.assertEqual([e.refund_request for e in log], [first["refund_request"]] * 2 + [second["refund_request"]] * 2)
        self.assertEqual(log[0].remarks, "candidate left")  # the CR employee's reason, as typed
        self.assertEqual(log[1].remarks, "bank details do not match")  # the accountant's words, as typed
        self.assertEqual((log[0].refund_amount, log[2].refund_amount), (500, 400))
        self.assertTrue(all(e.by_user and e.event_on for e in log))

    def test_resolving_and_backing_out_are_logged_too(self):
        from verp_staffing.cr.doctype.cr.cr import resolve_or_refund_cr

        resolve_or_refund_cr(self.cr.name, "Dispute Resolved", "settled on a call")
        log = frappe.get_doc("CR", self.cr.name).cr_events
        self.assertEqual([(e.event, e.remarks) for e in log], [("Resolved", "settled on a call")])

    def test_a_rejected_refund_case_can_be_resolved(self):
        from verp_staffing.cr.doctype.cr.cr import resolve_or_refund_cr

        res = self.request_refund(self.cr, 500, fee=3)
        reject_payment_entry(res["payment_entry"], "wrong details")
        resolve_or_refund_cr(self.cr.name, "Dispute Resolved", "sorted out")
        self.assertEqual(frappe.get_doc("CR", self.cr.name)._get_latest_history_row().status, "Dispute Resolved")

    def test_credit_note_cannot_exceed_what_was_invoiced(self):
        self.request_refund(self.cr, 1000, fee=3)
        # everything is already spoken for by the waiting request
        with self.assertRaises(frappe.ValidationError):
            refund.get_refund_preview(self.cr.name, amount=1)

    def test_rejecting_discards_the_drafts_and_keeps_the_case_open(self):
        res = self.request_refund(self.cr, 500, fee=3)
        reject_payment_entry(res["payment_entry"], "wrong account")

        rr = frappe.get_doc("Refund Request", res["refund_request"])
        self.assertEqual(rr.status, "Rejected")
        self.assertFalse(frappe.db.exists("Credit Note", res["credit_note"]))
        # the case says so: Refund Rejected, with the accountant's remarks, and it stays open for CR to act on
        latest = frappe.get_doc("CR", self.cr.name)._get_latest_history_row()
        self.assertEqual(latest.status, "Refund Rejected")
        self.assertEqual((latest.refund_request, latest.refund_status), (res["refund_request"], "Rejected"))
        self.assertEqual(latest.refund_remarks, "wrong account")  # the accountant's words, as typed
        self.assertEqual(frappe.db.get_value("CR", self.cr.name, "status"), "Refund Rejected")
        self.assertEqual(frappe.db.get_value("Customer", self.customer, "overall_status"), "Refund Rejected")
        # and a fresh request can be raised
        self.assertTrue(self.request_refund(self.cr, 200, fee=0)["refund_request"])

    def test_cancelling_a_verified_refund_reverses_the_books_and_reopens_the_case(self):
        res = self.request_refund(self.cr, 500, fee=3)
        verify_payment_entry(res["payment_entry"])
        frappe.get_doc("Payment Entry", res["payment_entry"]).cancel()

        for voucher_type, name in (("Credit Note", res["credit_note"]), ("Payment Entry", res["payment_entry"])):
            totals = gl_totals(voucher_type, name)
            self.assertTrue(totals, f"{voucher_type} should still have its (reversed) entries")
            self.assertTrue(all(v == 0 for v in totals.values()), f"{voucher_type} not reversed: {totals}")
        self.assertEqual(frappe.db.get_value("Credit Note", res["credit_note"], "docstatus"), 2)
        self.assertEqual(frappe.db.get_value("Refund Request", res["refund_request"], "status"), "Cancelled")
        self.assertEqual(frappe.get_doc("CR", self.cr.name)._get_latest_history_row().status, "Dispute Pending")
        self.assertEqual(frappe.db.get_value("Customer", self.customer, "overall_status"), "Moved To CR")
        # what was refunded is available again
        self.assertEqual(refund.get_refund_preview(self.cr.name)["refundable_total"], 1000)

    def test_tax_is_reversed_incrementally_across_part_refunds(self):
        customer = self.new_customer()
        si, _receipt = self.paid_invoice(customer, 1000, tax_rate=18)  # 1180 = 1000 + 180 tax
        tax_account = _resolved["tax_account"]

        reversed_tax, reversed_income = [], 0.0
        for amount in (400, 400, 380):
            cn = frappe.get_doc(
                {"doctype": "Credit Note", "customer": customer, "company": self.company, "currency": si.currency,
                 "posting_date": si.posting_date, "debit_to": self.debtors, "invoices": [{"sales_invoice": si.name, "amount": amount}]}
            ).insert(ignore_permissions=True)
            cn.submit()
            gl = gl_totals("Credit Note", cn.name)
            self.assertEqual(flt(sum(gl.values()), 2), 0)
            self.assertEqual(gl[self.debtors], -amount)
            reversed_tax.append(gl[tax_account])
            reversed_income += gl[self.income]

        # 180 x 400/1180 = 61.02, then 180 x 800/1180 - 61.02 = 61.01, then the rest: the whole 180 and no drift
        self.assertEqual(reversed_tax, [61.02, 61.01, 57.97])
        self.assertEqual(flt(sum(reversed_tax), 2), 180)
        self.assertEqual(flt(reversed_income, 2), 1000)

    def test_refund_without_a_fee_pays_the_full_amount(self):
        res = self.request_refund(self.cr, 500, fee=0)
        verify_payment_entry(res["payment_entry"])
        pe_gl = gl_totals("Payment Entry", res["payment_entry"])
        self.assertEqual((pe_gl[self.debtors], pe_gl[self.bank]), (500, -500))
        self.assertNotIn(self.fee_account, pe_gl)


class TestHoldAndBackout(RefundFlowTestCase):
    def setUp(self):
        self.customer = self.new_customer()

    def test_hold_then_resolve_puts_the_service_back(self):
        svc = self.service("Training", self.customer, status="Pending")
        row = frappe._dict()
        values = backout.hold_service(row, self.customer, "Training", svc.name)

        self.assertEqual(frappe.db.get_value("Training", svc.name, ["status", "held_by_cr"]), ("Hold", 1))
        self.assertEqual(values["held_previous_status"], "Pending")

        backout.release_hold(frappe._dict(values))
        self.assertEqual(frappe.db.get_value("Training", svc.name, ["status", "held_by_cr"]), ("Pending", 0))

    def test_release_leaves_a_service_someone_moved_on(self):
        svc = self.service("Training", self.customer)
        values = backout.hold_service(frappe._dict(), self.customer, "Training", svc.name)
        frappe.db.set_value("Training", svc.name, "status", "Completed")
        backout.release_hold(frappe._dict(values))
        self.assertEqual(frappe.db.get_value("Training", svc.name, "status"), "Completed")

    def test_hold_rejects_another_customers_record(self):
        svc = self.service("Training", self.customer)
        with self.assertRaises(frappe.ValidationError):
            backout.hold_service(frappe._dict(), self.new_customer(), "Training", svc.name)

    def test_backout_marks_open_work_and_a_cancelled_refund_restores_it(self):
        open_svc = self.service("Training", self.customer, status="Pending")
        done_svc = self.service("Resume", self.customer, status="Completed")
        row = frappe._dict()

        backout.propagate_backout(row, self.customer)
        self.assertEqual(frappe.db.get_value("Training", open_svc.name, "status"), "Backout")
        self.assertEqual(frappe.db.get_value("Resume", done_svc.name, "status"), "Completed")

        backout.restore_backout(row)
        self.assertEqual(frappe.db.get_value("Training", open_svc.name, "status"), "Pending")
        self.assertIsNone(row.backout_snapshot)

    def test_restore_brings_back_a_cr_hold_too(self):
        svc = self.service("Training", self.customer, status="Pending")
        backout.hold_service(frappe._dict(), self.customer, "Training", svc.name)
        row = frappe._dict()
        backout.propagate_backout(row, self.customer)
        self.assertEqual(frappe.db.get_value("Training", svc.name, ["status", "held_by_cr"]), ("Backout", 0))

        backout.restore_backout(row)
        self.assertEqual(frappe.db.get_value("Training", svc.name, ["status", "held_by_cr"]), ("Hold", 1))

    def test_a_held_record_cannot_be_edited_by_a_normal_user(self):
        svc = self.service("Training", self.customer)
        backout.hold_service(frappe._dict(), self.customer, "Training", svc.name)

        doc = frappe.get_doc("Training", svc.name)
        doc.reload()
        with mock.patch("frappe.get_roles", return_value=["Recruiter"]):
            with self.assertRaises(frappe.PermissionError):
                backout.validate_status_change(self._edit(doc))

    def test_normal_users_cannot_pick_backout_or_hold_by_hand(self):
        svc = self.service("Training", self.customer)
        with mock.patch("frappe.get_roles", return_value=["Recruiter"]):
            for status in ("Backout", "Hold"):
                doc = frappe.get_doc("Training", svc.name)
                doc.status = status
                doc._doc_before_save = frappe.get_doc("Training", svc.name)
                with self.assertRaises(frappe.ValidationError):
                    backout.validate_status_change(doc)

    def test_marketing_hold_is_still_a_manual_choice(self):
        doc = frappe.new_doc("Marketing")
        before = frappe.new_doc("Marketing")
        before.status = "Started"
        doc.status = "Hold"
        doc.name = before.name = "TEST-MKT"
        doc.flags.in_insert = False
        doc._doc_before_save = before
        with mock.patch("frappe.get_roles", return_value=["Recruiter"]), mock.patch.object(type(doc), "is_new", lambda s: False):
            backout.validate_status_change(doc)  # no error

    def test_system_saves_are_not_blocked_by_a_hold(self):
        svc = self.service("Training", self.customer)
        backout.hold_service(frappe._dict(), self.customer, "Training", svc.name)
        doc = frappe.get_doc("Training", svc.name)
        doc.flags.ignore_permissions = True
        with mock.patch("frappe.get_roles", return_value=["Recruiter"]):
            backout.validate_status_change(self._edit(doc))  # no error

    @staticmethod
    def _edit(doc):
        doc._doc_before_save = frappe.get_doc(doc.doctype, doc.name)
        return doc


class TestPortalAfterBackout(RefundFlowTestCase):
    def test_backout_statuses_end_portal_access(self):
        from verp_staffing.crm.api.customer_chat import ENDED_STATUSES

        for status in ("Backout", "Backout and Refund", "Customer Placed"):
            self.assertIn(status, ENDED_STATUSES)
        self.assertNotIn("Refund Pending", ENDED_STATUSES)
        self.assertNotIn("Moved To CR", ENDED_STATUSES)
