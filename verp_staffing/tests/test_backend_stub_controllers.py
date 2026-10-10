"""Doctypes whose controller has no logic of its own (and no dedicated test file): check each one still imports,
exposes a Document subclass and loads its schema. Plus Call Details' duration-unit rule."""

import importlib
import inspect
import os

import frappe
from frappe.model.document import Document
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.doctype.call_details.call_details import CallDetails, unit_for_seconds

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stub_doctypes():
	found = []
	for root, dirs, files in os.walk(APP_DIR):
		if os.path.basename(os.path.dirname(root)) != "doctype" or "charts_of_accounts" in root:
			continue
		name = os.path.basename(root)
		if f"{name}.py" in files and f"test_{name}.py" not in files and f"{name}.json" in files:
			found.append(root)
	return sorted(found)


class TestStubControllers(FrappeTestCase):
	def test_stub_doctypes_found(self):
		self.assertGreater(len(stub_doctypes()), 20)

	def test_each_controller_imports_and_schema_loads(self):
		for root in stub_doctypes():
			name = os.path.basename(root)
			rel = os.path.relpath(root, os.path.dirname(APP_DIR)).replace(os.sep, ".")
			with self.subTest(doctype=name):
				mod = importlib.import_module(f"{rel}.{name}")
				classes = [
					c for _, c in inspect.getmembers(mod, inspect.isclass)
					if issubclass(c, Document) and c is not Document and c.__module__ == mod.__name__
				]
				self.assertEqual(len(classes), 1, f"{name}: expected one Document subclass")
				title = frappe.get_file_json(os.path.join(root, f"{name}.json"))["name"]
				self.assertTrue(frappe.get_meta(title).fields)


class TestCallDetails(FrappeTestCase):
	def test_unit_for_seconds(self):
		self.assertEqual(unit_for_seconds(7200), "Hours")
		self.assertEqual(unit_for_seconds(5400), "Minutes")
		self.assertEqual(unit_for_seconds(0), "Minutes")
		self.assertEqual(unit_for_seconds(None), "Minutes")

	def test_validate_sets_unit_only_when_invalid(self):
		d = CallDetails.__new__(CallDetails)
		d.duration, d.duration_unit = 3600, None
		d.validate()
		self.assertEqual(d.duration_unit, "Hours")
		d.duration_unit = "Minutes"
		d.validate()
		self.assertEqual(d.duration_unit, "Minutes")
