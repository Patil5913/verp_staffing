# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.doctype.agreement import agreement as mod


def tpl(fields, url="/files/t.pdf"):
	return frappe._dict(fields_json=json.dumps(fields), upload_pdf_template=url)


class TestRender(FrappeTestCase):
	def test_values_are_escaped_and_placed(self):
		html = mod.render_html_from_pdf_template(
			tpl([{"page": 1, "fieldname": "name", "x": 10, "y": 20, "width": 100, "height": 25}]),
			{"name": "<script>alert(1)</script>"},
		)
		self.assertNotIn("<script>", html)
		self.assertIn("&lt;script&gt;", html)
		self.assertIn("left:10.0px", html)
		self.assertIn("top:20.0px", html)

	def test_one_page_per_highest_page_number(self):
		html = mod.render_html_from_pdf_template(tpl([{"page": 3, "fieldname": "a"}]), {"a": "x"})
		self.assertEqual(html.count('class="agreement-page"'), 3)
		self.assertIn("t.pdf#page=3", html)

	def test_no_fields_gives_a_single_page(self):
		html = mod.render_html_from_pdf_template(tpl([]), {})
		self.assertEqual(html.count('class="agreement-page"'), 1)
		self.assertEqual(mod.render_html_from_pdf_template(frappe._dict(fields_json=None, upload_pdf_template=""), {}).count("agreement-page\""), 1)

	def test_missing_value_renders_blank_and_defaults_apply(self):
		html = mod.render_html_from_pdf_template(tpl([{"page": 1, "fieldname": "nope"}]), {})
		self.assertIn("width:150px", html)
		self.assertIn("height:30px", html)

	def test_coordinates_cannot_inject_css_or_markup(self):
		evil = '10px; background:url(http://evil)'
		html = mod.render_html_from_pdf_template(
			tpl([{"page": 1, "fieldname": "a", "x": evil, "y": "1\"><img src=x onerror=1>"}]), {"a": "v"}
		)
		self.assertNotIn("evil", html)
		self.assertNotIn("onerror", html)

	def test_template_url_is_escaped(self):
		html = mod.render_html_from_pdf_template(tpl([], url='x"><script>1</script>'), {})
		self.assertNotIn("<script>1", html)

	def test_px_helper(self):
		self.assertEqual(mod._px("12.5", 0), 12.5)
		self.assertEqual(mod._px(None, 7), 7)
		self.assertEqual(mod._px("abc", 7), 7)
		self.assertEqual(mod._px(float("nan"), 7), 7)
		self.assertEqual(mod._px(float("inf"), 7), 7)


class TestEndpointsRequirePermission(FrappeTestCase):
	def test_render_preview_checks_template_read(self):
		doc = mock.Mock()
		doc.check_permission.side_effect = frappe.PermissionError
		with mock.patch.object(mod.frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.PermissionError):
				mod.render_preview("T", "{}")

	def test_load_template_fields_checks_read_then_returns_json(self):
		doc = mock.Mock(fields_json=None)
		with mock.patch.object(mod.frappe, "get_doc", return_value=doc):
			self.assertEqual(mod.load_template_fields("T"), "[]")
		doc.check_permission.assert_called_with("read")
		doc.check_permission.side_effect = frappe.PermissionError
		with mock.patch.object(mod.frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.PermissionError):
				mod.load_template_fields("T")

	def test_create_and_send_needs_create_and_sales_order_read(self):
		with mock.patch.object(mod.frappe, "has_permission", side_effect=frappe.PermissionError):
			with mock.patch.object(mod.frappe, "get_doc") as gd:
				with self.assertRaises(frappe.PermissionError):
					mod.create_and_send("SO-1", "T", "{}")
				gd.assert_not_called()

	def test_create_and_send_refuses_duplicates(self):
		with mock.patch.object(mod.frappe, "has_permission", return_value=True), \
			mock.patch.object(mod.frappe.db, "exists", return_value=True):
			with self.assertRaises(frappe.ValidationError):
				mod.create_and_send("SO-1", "T", {})
