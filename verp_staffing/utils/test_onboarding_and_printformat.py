import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import onboarding_setup_helper as osh
from verp_staffing.utils import printformat as pf


class TestHelpers(FrappeTestCase):
	def test_non_empty_array_detection(self):
		self.assertTrue(osh._has_non_empty_array_value({"a": [], "b": ["x"]}))
		self.assertFalse(osh._has_non_empty_array_value({"a": [], "b": "x", "c": None}))
		self.assertFalse(osh._has_non_empty_array_value({}))
		self.assertFalse(osh._has_non_empty_array_value([1]))
		self.assertFalse(osh._has_non_empty_array_value(None))

	def test_json_loading_never_raises(self):
		self.assertEqual(osh._safe_json_load('{"a": 1}'), {"a": 1})
		for bad in (None, "", "{oops", 0):
			self.assertEqual(osh._safe_json_load(bad), {})


def config(**kw):
	base = dict(
		default_interview_status="Scheduled", expiry_hours_of_agreement="02:00",
		candidate_details_form_fields=json.dumps({"Marketing": {"fields": [{"field_name": "x"}]}}),
		department_display_form_fields=json.dumps({"Marketing": ["x"]}),
		department_access_form_fields=json.dumps({"Marketing": ["x"]}),
	)
	base.update(kw)
	return frappe._dict(base)


class TestConfigurationComplete(FrappeTestCase):
	def check(self, **kw):
		with mock.patch.object(osh.frappe, "get_cached_doc", return_value=config(**kw)):
			return osh.is_erp_configuration_complete()

	def test_a_full_configuration_is_complete(self):
		self.assertTrue(self.check())

	def test_each_missing_piece_makes_it_incomplete(self):
		self.assertFalse(self.check(default_interview_status=""))
		self.assertFalse(self.check(expiry_hours_of_agreement=""))
		self.assertFalse(self.check(candidate_details_form_fields="{}"))
		self.assertFalse(self.check(candidate_details_form_fields=json.dumps({"Marketing": {"fields": []}})))
		self.assertFalse(self.check(candidate_details_form_fields=json.dumps({"Marketing": ["old-style"]})))
		self.assertFalse(self.check(department_display_form_fields=json.dumps({"M": []})))
		self.assertFalse(self.check(department_access_form_fields="not json"))

	def test_a_missing_configuration_record_is_incomplete(self):
		with mock.patch.object(osh.frappe, "get_cached_doc", side_effect=frappe.DoesNotExistError):
			self.assertFalse(osh.is_erp_configuration_complete())


class TestProgress(FrappeTestCase):
	def progress(self, employee=True, erp=True, pdf=True):
		with mock.patch.object(osh, "has_employee_setup", return_value=employee), \
			mock.patch.object(osh, "is_erp_configuration_complete", return_value=erp), \
			mock.patch.object(osh, "has_pdf_agreement_template", return_value=pdf):
			return osh.get_setup_progress()

	def test_everything_done(self):
		p = self.progress()
		self.assertEqual((p["is_completed"], p["current_step"], p["progress_percentage"], p["completed_steps"]), (True, "completed", 100, 5))
		self.assertEqual(p["next_action"]["route"], "/verp")

	def test_the_first_missing_step_is_next(self):
		p = self.progress(employee=False, erp=False, pdf=False)
		self.assertEqual((p["current_step"], p["progress_percentage"]), ("employee", 40))
		self.assertEqual(p["next_action"]["doctype"], "Employee")
		p = self.progress(erp=False, pdf=False)
		self.assertEqual((p["current_step"], p["current_step_label"]), ("erp_configuration", "Configure ERP Settings"))
		p = self.progress(pdf=False)
		self.assertEqual((p["current_step"], p["progress_percentage"]), ("pdf_agreement_template", 80))
		self.assertFalse(p["is_completed"])


class TestPrintFormat(FrappeTestCase):
	def test_only_sales_invoice_formats_are_cleaned_up(self):
		with mock.patch.object(pf.frappe, "get_all", return_value=[frappe._dict(name="Old", standard="No")]) as ga, \
			mock.patch.object(pf.frappe, "delete_doc") as dd:
			pf.remove_other_sales_invoice_print_formats()
		filters = ga.call_args.kwargs["filters"]
		self.assertEqual(filters["doc_type"], "Sales Invoice")
		self.assertEqual(filters["name"], ["!=", pf.SALES_INVOICE_PRINT_FORMAT])
		dd.assert_called_once()
		self.assertEqual(dd.call_args[0][:2], ("Print Format", "Old"))

	def test_other_doctypes_print_formats_survive_a_real_cleanup(self):
		frappe.db.savepoint("pf_test")
		try:
			doc = frappe.get_doc({"doctype": "Print Format", "name": "zz test lead format", "doc_type": "Lead", "custom_format": 1, "print_format_type": "Jinja", "html": "<p>x</p>"}).insert(ignore_permissions=True)
			pf.remove_other_sales_invoice_print_formats()
			self.assertTrue(frappe.db.exists("Print Format", doc.name))
		finally:
			frappe.db.rollback(save_point="pf_test")

	def test_seed_swallows_errors_unless_asked(self):
		with mock.patch.object(pf, "get_email_branding", side_effect=RuntimeError("x")), mock.patch.object(pf.frappe, "log_error") as err:
			pf.seed_sales_invoice_print_format()
			err.assert_called_once()
			with self.assertRaises(RuntimeError):
				pf.seed_sales_invoice_print_format(raise_on_error=True)

	def test_seed_escapes_branding_into_the_template(self):
		branding = {"logo_url": 'x" onerror="1', "company_name": "<b>Acme</b>", "social_links_html": "<a>s</a>"}
		with mock.patch.object(pf, "get_email_branding", return_value=branding), \
			mock.patch.object(pf, "upsert_print_format", return_value=True) as up, \
			mock.patch.object(pf, "remove_other_sales_invoice_print_formats"):
			self.assertTrue(pf.seed_sales_invoice_print_format())
		name, doc_type, html = up.call_args[0][:3]
		self.assertEqual((name, doc_type), (pf.SALES_INVOICE_PRINT_FORMAT, "Sales Invoice"))
		self.assertNotIn('onerror="1"', html)
		self.assertNotIn("<b>Acme</b>", html)
		self.assertNotIn("__LOGO_BLOCK__", html)
		self.assertNotIn("__COMPANY_NAME__", html)
		self.assertNotIn("__BANK_DETAILS__", html)
		self.assertIn("<a>s</a>", html)
