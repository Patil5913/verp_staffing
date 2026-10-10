import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.doctype.lead_detail_form import lead_detail_form as ldf
from verp_staffing.crm.doctype.lead_detail_form.test_lead_detail_form_otp import (
	PAYLOAD,
	encryption_key,
	make_token,
)

EMPTY = {k: [] for k in ("form visit logs", "signature update logs", "authentication logs", "concern accepted")}


class TestAddAuditLog(FrappeTestCase):
	"""Pins the current guest behaviour: any valid token holder may append audit entries
	(and the Agreement is marked signed)."""

	def run_it(self, audit, existing=None, token=None):
		doc = mock.Mock()
		with encryption_key(), mock.patch.object(ldf.frappe.db, "get_value", return_value=existing), mock.patch.object(
			ldf.frappe.db, "sql"
		) as sql, mock.patch.object(ldf.frappe, "get_doc", return_value=doc):
			res = ldf.add_audit_log(token if token is not None else make_token(), audit)
		return res, sql, doc

	def saved(self, sql):
		return json.loads(sql.call_args[0][1][0])

	def test_bad_token_is_rejected_and_nothing_written(self):
		res, sql, doc = self.run_it({}, token="garbage")
		self.assertEqual(res, {"status": "error", "message": "Invalid token"})
		sql.assert_not_called()
		doc.db_set.assert_not_called()

	def test_token_signed_with_another_key_is_rejected(self):
		res, sql, _ = self.run_it({}, token=make_token(key="other"))
		self.assertEqual(res["message"], "Invalid token")
		sql.assert_not_called()

	def test_token_without_agreement(self):
		payload = {k: v for k, v in PAYLOAD.items() if k != "agr"}
		res, sql, _ = self.run_it({}, token=make_token(payload))
		self.assertEqual(res["message"], "Agreement not found")
		sql.assert_not_called()

	def test_invalid_audit_json_and_shape(self):
		self.assertEqual(self.run_it("{not json")[0]["message"], "Invalid audit JSON")
		self.assertEqual(self.run_it("[1]")[0]["message"], "Audit must be object")
		self.assertEqual(self.run_it(5)[0]["message"], "Audit must be object")

	def test_entries_are_appended_to_existing_trail(self):
		existing = json.dumps({**EMPTY, "form visit logs": [{"a": 1}]})
		res, sql, doc = self.run_it({"form visit logs": [{"b": 2}], "concern accepted": [{"c": 3}]}, existing)
		self.assertEqual(res, {"status": "success"})
		trail = self.saved(sql)
		self.assertEqual(trail["form visit logs"], [{"a": 1}, {"b": 2}])
		self.assertEqual(trail["concern accepted"], [{"c": 3}])
		self.assertEqual(sql.call_args[0][1][1], "AG-1")
		doc.db_set.assert_called_once_with("status", "Agreement signed")

	def test_json_string_audit_is_accepted(self):
		res, sql, _ = self.run_it(json.dumps({"authentication logs": [{"x": 1}]}))
		self.assertEqual(res["status"], "success")
		self.assertEqual(self.saved(sql)["authentication logs"], [{"x": 1}])

	def test_corrupt_stored_trail_is_replaced_and_unknown_keys_ignored(self):
		res, sql, _ = self.run_it({"evil": [1], "form visit logs": "notalist"}, existing="{broken")
		self.assertEqual(res["status"], "success")
		self.assertEqual(self.saved(sql), EMPTY)


class TestRequestNewAgreementLink(FrappeTestCase):
	def run_it(self, customer="C1", owner="EMP-1", user="owner@x.com", template=None):
		def get_value(doctype, name, field=None, **kw):
			if doctype == "Sales Order":
				return customer
			if doctype == "Customer":
				return owner
			if doctype == "Employee":
				return user
			return template
		with mock.patch.object(ldf.frappe.db, "get_value", side_effect=get_value), mock.patch.object(
			ldf.frappe, "sendmail"
		) as mail, mock.patch.object(ldf, "send_notification") as notify:
			res = ldf.request_new_agreement_link("SO-1", "signer@x.com", "AG-1")
		return res, mail, notify

	def test_unknown_sales_order_throws(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_it(customer=None)

	def test_customer_without_owner_throws(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_it(owner=None)

	def test_default_texts_go_to_signer_and_owner(self):
		res, mail, notify = self.run_it()
		self.assertEqual(res, {"status": "ok"})
		self.assertEqual(mail.call_args.kwargs["recipients"], ["signer@x.com"])
		self.assertEqual(mail.call_args.kwargs["subject"], "Agreement Link Request Received")
		kw = notify.call_args.kwargs
		self.assertEqual(kw["recipients"], ["owner@x.com"])
		self.assertEqual((kw["reference_doctype"], kw["reference_name"]), ("Sales Order", "SO-1"))
		self.assertIn("AG-1", kw["message"])

	def test_email_templates_are_rendered_when_present(self):
		tpl = frappe._dict(subject="Hi {{ customer_name|default('there') }}", response_html="<b>x</b>", response=None)
		res, mail, notify = self.run_it(template=tpl)
		self.assertEqual(res["status"], "ok")
		self.assertEqual(notify.call_args.kwargs["subject"], "Hi C1")
		self.assertEqual(notify.call_args.kwargs["message"], "<b>x</b>")
