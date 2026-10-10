"""Unit tests for setup email creation, the Agreement Template -> E Sign flow and Marketing
Other Services validation. Everything touching the database or files is mocked."""

import json
from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.esign import template_flow as tf
from verp_staffing.marketing.doctype.marketing_other_services import marketing_other_services as mos
from verp_staffing.setup import email_utils as eu


class TestSetupEmail(FrappeTestCase):
	args = {"business_email": "Ann.Lee@Corp.com", "email_password": "pw", "email_server": "imap.corp.com", "smtp_server": "smtp.corp.com", "incoming_port": "993", "smtp_port": "587", "use_imap": "1", "use_ssl": 1}

	def test_nothing_to_do_without_email_and_password(self):
		with mock.patch.object(eu, "create_email_domain") as d:
			self.assertEqual(eu.setup_email({"business_email": "a@b.c"}), {"status": "ok"})
			self.assertEqual(eu.setup_email(json.dumps({"email_password": "x"})), {"status": "ok"})
			self.assertEqual(eu.setup_email(None), {"status": "ok"})
		d.assert_not_called()

	def test_setup_creates_domain_then_account(self):
		with mock.patch.object(eu, "create_email_domain", return_value="DOM") as d, mock.patch.object(eu, "create_email_account") as a:
			self.assertEqual(eu.setup_email(json.dumps(self.args)), {"status": "ok"})
		a.assert_called_once()
		self.assertEqual(a.call_args[0][1], "DOM")
		self.assertEqual(d.call_args[0][0].business_email, "Ann.Lee@Corp.com")

	def test_existing_domain_is_reused(self):
		with mock.patch.object(eu.frappe.db, "exists", return_value="corp.com") as ex:
			self.assertEqual(eu.create_email_domain(frappe._dict(self.args)), "corp.com")
		self.assertEqual(ex.call_args[0][1], {"domain_name": "corp.com"})

	def test_new_domain_needs_server_settings(self):
		for missing in ("email_server", "smtp_server", "incoming_port", "smtp_port"):
			args = frappe._dict({**self.args, missing: ""})
			with mock.patch.object(eu.frappe.db, "exists", return_value=None):
				with self.assertRaises(frappe.ValidationError, msg=missing):
					eu.create_email_domain(args)

	def test_new_domain_is_inserted_with_integer_flags(self):
		doc = mock.Mock()
		with mock.patch.object(eu.frappe.db, "exists", return_value=None), mock.patch.object(eu.frappe, "get_doc", return_value=doc) as gd:
			self.assertIs(eu.create_email_domain(frappe._dict(self.args)), doc)
		d = gd.call_args[0][0]
		self.assertEqual((d["domain_name"], d["incoming_port"], d["smtp_port"], d["use_imap"], d["use_ssl"], d["use_tls"]), ("corp.com", 993, 587, 1, 1, 0))
		doc.insert.assert_called_once_with(ignore_permissions=True)

	def test_existing_account_is_reused(self):
		with mock.patch.object(eu.frappe.db, "exists", return_value="ACC"):
			self.assertEqual(eu.create_email_account(frappe._dict(self.args), SimpleNamespace(name="corp.com")), "ACC")

	def test_account_name_is_derived_from_the_address(self):
		doc = mock.Mock(); doc.name = "ACC-1"
		domain = SimpleNamespace(name="corp.com", use_imap=1, email_server="imap", incoming_port=993, use_ssl=1, use_starttls=0, smtp_server="smtp", smtp_port=587, use_tls=1, use_ssl_for_outgoing=0)
		with mock.patch.object(eu.frappe.db, "exists", return_value=None), mock.patch.object(eu.frappe, "get_doc", return_value=doc) as gd:
			self.assertEqual(eu.create_email_account(frappe._dict({**self.args, "business_email": "ann_lee.x@corp.com"}), domain), "ACC-1")
		spec = gd.call_args[0][0]
		self.assertEqual(spec["email_account_name"], "Ann Lee X")
		self.assertEqual((spec["domain"], spec["auth_method"], spec["default_outgoing"]), ("corp.com", "Basic", 1))
		doc.insert.assert_called_once_with(ignore_permissions=True)


def tpl(fields, pdf="/files/t.pdf", title="Tpl"):
	return SimpleNamespace(fields_json=json.dumps(fields) if fields is not None else None, upload_pdf_template=pdf, title=title)


SIG = {"type": "Signature", "name": "Sign here", "page": 2, "x": 100, "y": 50, "width": 200, "height": 40, "page_width": 1000, "page_height": 500}


class TestTemplateFlowHelpers(FrappeTestCase):
	def test_template_fields_tolerates_bad_json(self):
		self.assertEqual(tf._template_fields(tpl([SIG])), [SIG])
		self.assertEqual(tf._template_fields(tpl(None)), [])
		self.assertEqual(tf._template_fields(SimpleNamespace(fields_json="{bad")), [])

	def test_signature_rows_are_percent_of_the_page(self):
		(row,) = tf._signature_rows([SIG], "a@b.c")
		self.assertEqual(row, {
			"page_number": 2, "x_percent": 10, "y_percent": 10, "width_percent": 20, "height_percent": 8,
			"signer_email": "a@b.c", "field_type": "signature", "field_label": "Sign here", "placeholder_text": "", "font_size": "12",
		})

	def test_customer_fields_map_to_signer_field_types(self):
		fields = [SIG] + [{**SIG, "type": t, "name": t} for t in ("Customer_Text", "Customer_Rich_Text", "Customer_Number", "Customer_Date", "Text", "Number")]
		types = [r["field_type"] for r in tf._signature_rows(fields, "a@b.c")]
		self.assertEqual(types, ["signature", "text", "text", "number", "date"])

	def test_defaults_for_missing_geometry(self):
		(row,) = tf._signature_rows([{"type": "Signature", "page_width": 100, "page_height": 100}], "a@b.c")
		self.assertEqual((row["page_number"], row["width_percent"], row["height_percent"], row["field_label"]), (1, 150, 30, "Signature"))

	def test_a_template_without_a_signature_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			tf._signature_rows([{**SIG, "type": "Customer_Text"}], "a@b.c")
		with self.assertRaises(frappe.ValidationError):
			tf._signature_rows([], "a@b.c")

	def test_missing_page_size_asks_to_resave(self):
		with self.assertRaises(frappe.ValidationError):
			tf._signature_rows([{**SIG, "page_width": 0}], "a@b.c")

	def test_fill_pdf_needs_a_file_that_exists(self):
		with self.assertRaises(frappe.ValidationError):
			tf._fill_pdf(tpl([SIG], pdf=""), {})
		with mock.patch.object(tf, "resolve_file_path", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				tf._fill_pdf(tpl([SIG]), {})

	def test_fill_pdf_hands_fields_and_data_to_the_renderer(self):
		with mock.patch.object(tf, "resolve_file_path", return_value="/p.pdf"), mock.patch.object(tf, "generate_pdf", return_value=b"PDF") as g:
			self.assertEqual(tf._fill_pdf(tpl([SIG]), {"a": 1}), b"PDF")
		g.assert_called_once_with("/p.pdf", [SIG], {"a": 1})


class TestApplyTemplate(FrappeTestCase):
	def run_apply(self, status="Draft", signer=" Signer@X.com ", data='{"a": 1}', tpl_obj=None):
		esign = mock.MagicMock(); esign.name = "ES-1"; esign.status = status; esign.title = ""; esign.original_pdf = "/f/ES-1.pdf"
		template = tpl_obj or tpl([SIG])
		with mock.patch.object(tf.frappe, "get_doc", side_effect=lambda dt, n: esign if dt == "E Sign" else template), mock.patch.object(
			tf, "_fill_pdf", return_value=b"PDF"
		), mock.patch.object(tf, "save_file", return_value=SimpleNamespace(file_url="/f/ES-1.pdf")) as save:
			res = tf.apply_template("ES-1", "TPL", data, signer)
		return res, esign, save

	def test_only_drafts_can_change(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_apply(status="Sent")

	def test_signer_email_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_apply(signer="  ")

	def test_replaces_signature_fields_and_stores_the_data(self):
		res, esign, save = self.run_apply()
		self.assertEqual(res, {"esign": "ES-1", "file_url": "/f/ES-1.pdf"})
		esign.check_permission.assert_called_once_with("write")
		esign.set.assert_called_once_with("signature_fields", [])
		self.assertEqual(esign.append.call_args[0][1]["signer_email"], "signer@x.com")
		self.assertEqual(esign.template_data, json.dumps({"a": 1}))
		self.assertEqual((esign.agreement_template, esign.title), ("TPL", "Tpl"))
		esign.db_set.assert_called_once_with("original_pdf", "/f/ES-1.pdf", update_modified=False)
		esign.save.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(save.call_args.kwargs["df"], "original_pdf")

	def test_a_template_without_signature_changes_nothing(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_apply(tpl_obj=tpl([{**SIG, "type": "Text"}]))


class TestCreateFromTemplate(FrappeTestCase):
	def test_portal_access_already_active(self):
		with mock.patch.object(tf.frappe.db, "get_value", return_value="Active"):
			self.assertEqual(tf._ensure_portal_access("C1"), ("already", ""))

	def test_portal_access_is_granted(self):
		with mock.patch.object(tf.frappe.db, "get_value", return_value=""), mock.patch.object(tf.frappe.db, "savepoint"), mock.patch(
			"verp_staffing.crm.api.customer_chat.send_portal_access"
		) as send:
			self.assertEqual(tf._ensure_portal_access("C1"), ("granted", ""))
		send.assert_called_once_with("C1")

	def test_portal_access_failure_never_blocks(self):
		with mock.patch.object(tf.frappe.db, "get_value", return_value=""), mock.patch.object(tf.frappe.db, "savepoint"), mock.patch.object(
			tf.frappe.db, "rollback"
		) as rb, mock.patch("verp_staffing.crm.api.customer_chat.send_portal_access", side_effect=Exception("<b>no chat</b>")):
			status, reason = tf._ensure_portal_access("C1")
		self.assertEqual((status, reason), ("failed", "no chat"))
		rb.assert_called_once_with(save_point="portal_access")

	def test_signer_defaults_to_the_customer_email(self):
		with mock.patch.object(tf.frappe, "has_permission"), mock.patch.object(tf.frappe.db, "get_value", return_value="C1"), mock.patch.object(
			tf, "get_customer_email", return_value=""
		), mock.patch.object(tf.frappe, "get_cached_value", return_value="LDF-1"):
			with self.assertRaises(frappe.ValidationError):
				tf.create_from_template("TPL", "{}", sales_order="SO-1")

	def run_create(self, apply_side_effect=None, send=0, sales_order="SO-1", title=None):
		doc = mock.Mock(); doc.name = "ES-9"; doc.flags = SimpleNamespace()
		def get_value(dt, name, field=None, *a, **k):
			return {"Sales Order": "C1", "Pdf Agreement Template": "Master"}.get(dt)
		with mock.patch.object(tf.frappe, "has_permission"), mock.patch.object(tf.frappe.db, "get_value", side_effect=get_value), mock.patch.object(
			tf, "get_customer_email", return_value="c@x.com"
		), mock.patch.object(tf, "_ensure_portal_access", return_value=("granted", "")), mock.patch.object(
			tf.frappe, "get_doc", return_value=doc
		) as gd, mock.patch.object(tf, "apply_template", side_effect=apply_side_effect, return_value={"esign": "ES-9", "file_url": "/f"}) as ap, mock.patch.object(
			tf.frappe, "delete_doc"
		) as dd, mock.patch.object(tf.frappe.db, "rollback"), mock.patch.object(tf.frappe.db, "commit"), mock.patch(
			"verp_staffing.esign.doctype.e_sign.e_sign.send_all_signers"
		) as send_all:
			try:
				res = tf.create_from_template("TPL", "{}", sales_order=sales_order, send=send, title=title)
			except Exception as e:
				res = e
		return res, gd, ap, dd, send_all, doc

	def test_creates_a_draft_titled_after_template_and_order(self):
		res, gd, ap, _, send_all, doc = self.run_create()
		self.assertEqual(gd.call_args[0][0]["title"], "Master - SO-1")
		self.assertEqual((gd.call_args[0][0]["customer"], gd.call_args[0][0]["status"]), ("C1", "Draft"))
		self.assertTrue(doc.flags.ignore_mandatory)
		self.assertEqual(ap.call_args[0][3], "c@x.com")
		self.assertEqual((res["portal_access"], res["esign"]), ("granted", "ES-9"))
		send_all.assert_not_called()

	def test_explicit_title_wins_and_send_emails_the_signers(self):
		res, gd, _, _, send_all, _ = self.run_create(send="1", title="  Custom ")
		self.assertEqual(gd.call_args[0][0]["title"], "Custom")
		send_all.assert_called_once_with("ES-9")

	def test_failure_leaves_no_draft_behind(self):
		res, _, _, dd, send_all, _ = self.run_create(apply_side_effect=ValueError("no signature"))
		self.assertIsInstance(res, ValueError)
		dd.assert_called_once()
		self.assertEqual(dd.call_args[0], ("E Sign", "ES-9"))
		send_all.assert_not_called()


class TestSalesOrderAgreements(FrappeTestCase):
	def test_cards_list_esigns_then_legacy_agreements(self):
		esign = frappe._dict(name="ES-1", agreement_template="T", status="Sent", original_pdf="/o.pdf", signed_pdf="", creation="c")
		signers = [frappe._dict(signer_email="b@x", signed=1), frappe._dict(signer_email="a@x", signed=1), frappe._dict(signer_email="a@x", signed=0)]
		with mock.patch.object(tf.frappe, "has_permission"), mock.patch.object(tf.frappe, "get_all", side_effect=[[esign], signers]), mock.patch.object(
			tf, "get_email_state", return_value={"email_sent": 1}
		), mock.patch.object(tf, "get_agreement_cards", return_value=[{"name": "AG-1"}]):
			cards = tf.get_sales_order_agreements("SO-1")
		self.assertEqual([c["kind"] for c in cards], ["E Sign", "Agreement"])
		self.assertEqual(cards[0]["pdf"], "/o.pdf")
		self.assertEqual(cards[0]["signers"], [{"email": "a@x", "signed": False}, {"email": "b@x", "signed": True}])
		self.assertEqual(cards[0]["email_sent"], 1)


def service(**kw):
	s = mock.MagicMock(spec=mos.MarketingOtherServices)
	for k, v in kw.items():
		setattr(s, k, v)
	return s


class TestMarketingOtherServices(FrappeTestCase):
	def test_autoname_needs_a_customer(self):
		with self.assertRaises(frappe.ValidationError):
			mos.MarketingOtherServices.autoname(service(customer=""))

	def test_autoname_uses_the_customer_name(self):
		s = service(customer="C1")
		with mock.patch.object(mos.frappe.db, "get_value", return_value="Acme"), mock.patch.object(mos, "generate_name_series", return_value="MOS-Acme-1") as g:
			mos.MarketingOtherServices.autoname(s)
		g.assert_called_once_with("Marketing Other Services", "Acme")
		self.assertEqual(s.name, "MOS-Acme-1")

	def test_completed_services_are_locked_for_non_admins(self):
		s = service(); s.is_new.return_value = False; s.db_get.return_value = "Completed"
		with mock.patch.object(mos, "is_admin", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				mos.MarketingOtherServices.validate_completed_lock(s)
		with mock.patch.object(mos, "is_admin", return_value=True):
			mos.MarketingOtherServices.validate_completed_lock(s)

	def test_lock_ignores_new_and_open_services(self):
		s = service(); s.is_new.return_value = True
		with mock.patch.object(mos, "is_admin", return_value=False):
			mos.MarketingOtherServices.validate_completed_lock(s)
			s.is_new.return_value = False; s.db_get.return_value = "Pending"
			mos.MarketingOtherServices.validate_completed_lock(s)

	def test_every_proof_row_needs_a_document(self):
		ok = service(proof_of_work=[SimpleNamespace(document="D", idx=1)])
		mos.MarketingOtherServices.validate_documents(ok)
		bad = service(proof_of_work=[SimpleNamespace(document="D", idx=1), SimpleNamespace(document="", idx=2)])
		with self.assertRaisesRegex(frappe.ValidationError, "row 2"):
			mos.MarketingOtherServices.validate_documents(bad)
		mos.MarketingOtherServices.validate_documents(service(proof_of_work=None))

	def test_edited_rows_get_a_fresh_date_new_and_untouched_rows_do_not(self):
		class R(dict):
			__getattr__ = dict.get
			def __setattr__(self, k, v): self[k] = v
		old = [R(name="r1", note="a", date="old1"), R(name="r2", note="b", date="old2")]
		new = [R(name="r1", note="CHANGED", date="old1"), R(name="r2", note="b", date="old2"), R(name="r3", note="x", date="new3")]
		s = service(proof_of_work=new); s.is_new.return_value = False
		s.get_doc_before_save.return_value = SimpleNamespace(proof_of_work=old)
		s.meta.get_field.return_value = SimpleNamespace(options="Child")
		child_meta = mock.Mock(fields=[SimpleNamespace(fieldname="note"), SimpleNamespace(fieldname="date"), SimpleNamespace(fieldname="idx")])
		child_meta.get_field.return_value = SimpleNamespace(fieldtype="Date")
		with mock.patch.object(mos.frappe, "get_meta", return_value=child_meta), mock.patch.object(mos.frappe.utils, "nowdate", return_value="2026-10-10"):
			mos.MarketingOtherServices.stamp_updated_document_rows(s)
		self.assertEqual([r.date for r in new], ["2026-10-10", "old2", "new3"])

	def test_stamping_is_skipped_for_new_documents(self):
		s = service(); s.is_new.return_value = True
		mos.MarketingOtherServices.stamp_updated_document_rows(s)
		s.get_doc_before_save.assert_not_called()

	def test_after_insert_advances_the_customer_stage(self):
		with mock.patch.object(mos, "update_customer_stage") as u:
			mos.MarketingOtherServices.after_insert(service(customer="C1", service="Resume"))
		u.assert_called_once_with(customer="C1", service="Resume")
