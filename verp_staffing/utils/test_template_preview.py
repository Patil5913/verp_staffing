from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import template_preview as tp


def as_admin():
	class Ctx:
		def __enter__(s):
			s.old = frappe.session.user
			frappe.session.user = "Administrator"
		def __exit__(s, *a):
			frappe.session.user = s.old
	return Ctx()


class TestAccess(FrappeTestCase):
	def test_only_the_administrator_may_preview(self):
		old = frappe.session.user
		frappe.session.user = "test@example.com"
		try:
			for fn, args in ((tp.get_preview_doctypes, ()), (tp.preview_email_template, ("s", "b")), (tp.preview_print_format, ("Lead", "<p/>"))):
				with self.assertRaises(frappe.PermissionError, msg=fn.__name__):
					fn(*args)
		finally:
			frappe.session.user = old

	def test_only_this_apps_doctypes_can_be_previewed(self):
		doctypes = tp._app_doctypes()
		self.assertIn("Lead", doctypes)
		self.assertNotIn("User", doctypes)
		self.assertNotIn("ToDo", doctypes)
		tp._check_app_doctype("Lead")
		tp._check_app_doctype("")
		with self.assertRaises(frappe.ValidationError):
			tp._check_app_doctype("User")


class TestEmailPreview(FrappeTestCase):
	def test_variables_stay_as_their_own_names(self):
		with as_admin():
			out = tp.preview_email_template("Hi {{ customer_name }}", "<p>{{ message }} from {{ doc.owner }}</p>")
		self.assertEqual(out["subject"], "Hi {{ customer_name }}")

		self.assertIn("{{ message }}", out["html"])
		self.assertIsNone(out["reference"])

	def test_the_html_body_is_used_only_when_html_mode_is_on(self):
		with as_admin():
			self.assertIn("plain", tp.preview_email_template("s", "plain", "<b>html</b>", 0)["html"])
			self.assertIn("<b>html</b>", tp.preview_email_template("s", "plain", "<b>html</b>", 1)["html"])

	def test_template_logic_still_runs(self):
		with as_admin():
			out = tp.preview_email_template("s", "{% for i in [1, 2, 3] %}{{ i }}{% endfor %}{{ 2 + 3 }}")
		self.assertEqual(out["html"], "123" + "5")

	def test_blank_templates_render_blank(self):
		with as_admin():
			out = tp.preview_email_template(None, None)
		self.assertEqual((out["subject"], out["html"]), ("", ""))

	def test_a_broken_template_is_reported_not_crashed(self):
		with as_admin():
			with self.assertRaises(frappe.ValidationError) as cm:
				tp.preview_email_template("s", "{% if %}")
		self.assertIn("Body", str(cm.exception))


class TestPrintPreview(FrappeTestCase):
	def test_placeholder_mode_shows_every_field_as_its_name(self):
		with as_admin():
			out = tp.preview_print_format("Lead", "<h1>{{ doc.first_name }}</h1>{{ doc.get_formatted('status') }}", mode="placeholders")
		self.assertIn("<h1>{{ first_name }}</h1>", out["html"])
		self.assertIn("{{ status }}", out["html"])
		self.assertIsNone(out["reference"])
		self.assertTrue(out["html"].startswith("<div class='print-format'>"))

	def test_placeholder_mode_survives_formatting_helpers_and_empty_tables(self):
		with as_admin():
			out = tp.preview_print_format("Sales Invoice", "{{ frappe.utils.formatdate(doc.posting_date) }}|{{ frappe.utils.fmt_money(doc.grand_total) }}|{% for r in doc.items %}ROW{% endfor %}", mode="placeholders")
		self.assertIn("{{ posting_date }}|{{ grand_total }}|", out["html"])
		self.assertNotIn("ROW", out["html"])

	def test_sample_mode_builds_an_unsaved_record_with_child_rows(self):
		with as_admin():
			out = tp.preview_print_format("Sales Invoice", "{{ doc.name }}|{{ doc.items | length }}|{{ doc.grand_total }}", mode="sample")
		self.assertTrue(out["html"].count("SAMPLE-0001") == 1)
		self.assertIn("|1|1234.5", out["html"])
		self.assertEqual(out["reference"], "SAMPLE-0001")
		self.assertFalse(frappe.db.exists("Sales Invoice", "SAMPLE-0001"))

	def test_latest_mode_needs_a_record(self):
		with as_admin(), mock.patch.object(tp.frappe.db, "get_value", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				tp.preview_print_format("Lead", "x", mode="latest")

	def test_latest_mode_renders_a_real_record(self):
		doc = mock.Mock(); doc.name = "LEAD-1"
		with as_admin(), mock.patch.object(tp.frappe, "get_doc", return_value=frappe._dict(name="LEAD-1", first_name="Pat")) as gd:
			out = tp.preview_print_format("Lead", "{{ doc.first_name }}", mode="latest", reference_name="LEAD-1")
		self.assertIn("Pat", out["html"])
		self.assertEqual(out["reference"], "LEAD-1")

	def test_css_is_wrapped_and_a_saved_format_is_the_fallback_body(self):
		with as_admin(), mock.patch.object(tp.frappe.db, "get_value", return_value="<p>saved</p>"):
			out = tp.preview_print_format("Lead", "", css="p{color:red}", name="PF", mode="placeholders")
		self.assertTrue(out["html"].startswith("<style>p{color:red}</style>"))
		self.assertIn("<p>saved</p>", out["html"])

	def test_other_apps_doctypes_are_refused(self):
		with as_admin():
			with self.assertRaises(frappe.ValidationError):
				tp.preview_print_format("User", "x", mode="placeholders")

	def test_a_broken_print_format_is_reported(self):
		with as_admin():
			with self.assertRaises(frappe.ValidationError) as cm:
				tp.preview_print_format("Lead", "{{ doc.", mode="placeholders")
		self.assertIn("Print format", str(cm.exception))


class TestSampleValues(FrappeTestCase):
	def test_values_by_field_type(self):
		df = lambda ft, **k: frappe._dict(fieldtype=ft, fieldname=k.pop("fieldname", "f"), label=k.pop("label", "Label"), **k)
		self.assertEqual(tp._sample_value(df("Currency")), 1234.5)
		self.assertEqual(tp._sample_value(df("Int")), 10)
		self.assertEqual(tp._sample_value(df("Check")), 1)
		self.assertEqual(tp._sample_value(df("Date")), "2026-01-15")
		self.assertEqual(tp._sample_value(df("Time")), "10:30:00")
		self.assertEqual(tp._sample_value(df("Link", options="Customer")), "Sample Customer")
		self.assertEqual(tp._sample_value(df("Link", fieldname="currency", options="Currency")), "INR")
		self.assertEqual(tp._sample_value(df("Select", options="\nFirst\nSecond")), "First")
		self.assertEqual(tp._sample_value(df("Select", options="")), "")
		self.assertEqual(tp._sample_value(df("Data")), "Label")
		self.assertEqual(tp._sample_value(frappe._dict(fieldtype="Data", fieldname="f", label=None)), "f")
