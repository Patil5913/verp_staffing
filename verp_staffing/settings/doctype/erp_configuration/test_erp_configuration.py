# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.settings.doctype.erp_configuration import erp_configuration as mod
from verp_staffing.settings.doctype.erp_configuration.erp_configuration import ERPConfiguration


def cfg(**kw):
	kw.setdefault("expiry_hours_of_agreement", "02:30")
	return ERPConfiguration({"doctype": "ERP Configuration", **kw})


class TestValidate(FrappeTestCase):
	def test_valid_defaults(self):
		cfg().validate()

	def test_expiry_required_format_and_range(self):
		for bad in ("", None, "2:30", "0230", "ab:cd", "02:30:00", "00:00", "23:60", "99:99"):
			with self.assertRaises(frappe.ValidationError, msg=repr(bad)):
				cfg(expiry_hours_of_agreement=bad).validate()
		for ok in ("00:01", "23:59", "01:00", "72:00", "99:59"):
			cfg(expiry_hours_of_agreement=ok).validate()

	def test_social_urls_must_belong_to_their_site(self):
		cases = {
			"linkedin": ("https://www.linkedin.com/in/x", "https://evil.com/linkedin.com/x"),
			"facebook": ("http://facebook.com/page", "ftp://facebook.com/page"),
			"twitter_x": ("https://x.com/me", "https://twitter.com/me"),
			"youtube": ("https://www.youtube.com/c/me", "https://youtu.be/me"),
		}
		for field, (good, bad) in cases.items():
			cfg(**{field: good}).validate()
			with self.assertRaises(frappe.ValidationError, msg=field):
				cfg(**{field: bad}).validate()

	def test_blank_social_urls_are_fine(self):
		cfg(linkedin="", facebook="", twitter_x="", youtube="").validate()


class TestSystemSettingsEndpoints(FrappeTestCase):
	def as_manager(self):
		return mock.patch.object(mod.frappe, "only_for")

	def test_requires_system_manager(self):
		with mock.patch.object(mod.frappe, "only_for", side_effect=frappe.PermissionError):
			for fn, args in (
				(mod.get_system_settings_fields, ()),
				(mod.update_system_settings_fields, ({"country": "X"},)),
				(mod.get_sample_data_summary, ()),
				(mod.remove_sample_data, ()),
				(mod.add_candidate_form_field, ("L", "Data")),
			):
				with self.assertRaises(frappe.PermissionError, msg=fn.__name__):
					fn(*args)

	def test_unmanaged_field_is_refused(self):
		with self.as_manager():
			with self.assertRaises(frappe.ValidationError):
				mod.update_system_settings_fields({"enable_onboarding": 1})

	def test_empty_or_wrong_shape_is_refused(self):
		with self.as_manager():
			for v in ({}, "[]", "null", []):
				with self.assertRaises(frappe.ValidationError, msg=repr(v)):
					mod.update_system_settings_fields(v)

	def test_extensions_are_validated_and_normalised(self):
		with self.as_manager():
			for bad in ("pdf, bad ext", "pdf,PDF", "toolongext1", "p-df"):
				with self.assertRaises(frappe.ValidationError, msg=bad):
					mod.update_system_settings_fields({"allowed_file_extensions": bad})
			doc = mock.MagicMock()
			doc.get.side_effect = lambda f: "x"
			with mock.patch.object(mod.frappe, "get_single", return_value=doc):
				mod.update_system_settings_fields('{"allowed_file_extensions": "pdf, png\\njpg"}')
			doc.set.assert_called_with("allowed_file_extensions", "pdf\npng\njpg")
			doc.save.assert_called_once()

	def test_only_given_fields_are_set_in_one_save(self):
		with self.as_manager():
			doc = mock.MagicMock()
			doc.get.side_effect = lambda f: {"country": "India", "language": "en"}[f]
			with mock.patch.object(mod.frappe, "get_single", return_value=doc):
				out = mod.update_system_settings_fields({"country": "India", "language": "en"})
			self.assertEqual(doc.save.call_count, 1)
			self.assertEqual(out, {"values": {"country": "India", "language": "en"}})


class TestWebsiteSettings(FrappeTestCase):
	def test_update_needs_write_permission(self):
		with mock.patch.object(mod.frappe, "has_permission", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				mod.update_website_app_settings("X")

	def test_unchanged_values_do_not_save(self):
		doc = mock.MagicMock(app_name="A", app_logo="/files/l.png")
		with mock.patch.object(mod.frappe, "has_permission", return_value=True), \
			mock.patch.object(mod.frappe, "get_doc", return_value=doc):
			out = mod.update_website_app_settings("A", "/files/l.png")
		doc.save.assert_not_called()
		self.assertEqual(out, {"app_name": "A", "app_logo": "/files/l.png"})

	def test_changed_name_saves(self):
		doc = mock.MagicMock(app_name="A", app_logo="")
		with mock.patch.object(mod.frappe, "has_permission", return_value=True), \
			mock.patch.object(mod.frappe, "get_doc", return_value=doc):
			mod.update_website_app_settings("B")
		self.assertEqual(doc.app_name, "B")
		doc.save.assert_called_once()

	def test_public_files_are_left_alone(self):
		self.assertEqual(mod._ensure_public_file("/files/a.png"), "/files/a.png")
		self.assertEqual(mod._ensure_public_file(""), "")
		self.assertIsNone(mod._ensure_public_file(None))

	def test_private_logo_is_made_public(self):
		f = mock.MagicMock(is_private=1, file_url="/files/a.png")
		with mock.patch.object(mod.frappe, "get_doc", return_value=f):
			self.assertEqual(mod._ensure_public_file("/private/files/a.png"), "/files/a.png")
		self.assertEqual(f.is_private, 0)
		f.save.assert_called_once_with(ignore_permissions=True)


class TestSampleDataEndpoints(FrappeTestCase):
	def test_delete_conflicts_flag_is_parsed(self):
		with mock.patch.object(mod.frappe, "only_for"), \
			mock.patch.object(mod.sample_data_removal, "execute_removal", return_value={}) as ex:
			mod.remove_sample_data("0")
			ex.assert_called_with(False)
			mod.remove_sample_data("1")
			ex.assert_called_with(True)
			mod.remove_sample_data(1)
			ex.assert_called_with(True)
			mod.remove_sample_data()
			ex.assert_called_with(False)


class TestAddCandidateFormField(FrappeTestCase):
	def run_it(self, *a, **k):
		with mock.patch.object(mod.frappe, "only_for"):
			return mod.add_candidate_form_field(*a, **k)

	def test_validation(self):
		for args in (("", "Data"), ("  ", "Data"), ("X", "Attach"), ("X", "Select"), ("X", "Select", " \n ")):
			with self.assertRaises(frappe.ValidationError, msg=repr(args)):
				self.run_it(*args)

	def test_existing_field_name_and_bad_anchor_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_it("Email", "Data")  # 'email' exists on Lead Detail Form
		with self.assertRaises(frappe.ValidationError):
			self.run_it("Brand New Zzz", "Data", insert_after="no_such_field")

	def test_creates_a_custom_field(self):
		created = {}

		class Fake:
			def __init__(self, d): created.update(d)
			def insert(self): return self

		with mock.patch.object(mod.frappe, "get_doc", side_effect=lambda d: Fake(d)):
			out = self.run_it("Brand New Zzz", "Phone")
		self.assertEqual(out["fieldname"], "brand_new_zzz")
		self.assertEqual((created["fieldtype"], created["options"]), ("Data", "Phone"))
		self.assertEqual(created["dt"], "Lead Detail Form")
