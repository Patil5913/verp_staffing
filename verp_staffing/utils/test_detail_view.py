import uuid
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import detail_view as dv


def uid(prefix="DV"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestPrettify(FrappeTestCase):
    def test_prettify(self):
        self.assertEqual(dv._prettify("educational_details"), "Educational Details")
        self.assertEqual(dv._prettify(None), "")
        self.assertEqual(dv._prettify("_a_"), "A")


class TestSerializeField(FrappeTestCase):
    def test_serializes_with_label_fallback(self):
        df = frappe._dict(fieldname="past_experience_table", label=None, fieldtype="Table", options="X", reqd=1,
                          non_negative=0, length=0, in_list_view=0, fetch_from=None, read_only=0, depends_on=None,
                          description=None, default=None)
        out = dv._serialize_field(df)
        self.assertEqual(out["label"], "Past Experience Table")
        self.assertIs(out["reqd"], True)
        self.assertIs(out["read_only"], False)


class TestDocFieldsAndTables(FrappeTestCase):
    def test_layout_and_hidden_fields_excluded_and_sections_tracked(self):
        meta = frappe.get_meta("Lead Source")
        fields, tables = dv._doc_fields_and_tables(meta, None)
        names = [f["fieldname"] for f in fields]
        self.assertIn("name1", names)
        self.assertEqual(tables, [])
        for f in fields:
            self.assertNotIn(f["fieldtype"], dv.LAYOUT_FIELDTYPES)
            self.assertIn("section", f)

    def test_child_tables_become_descriptors_with_rows(self):
        meta = frappe.get_meta("Lead Detail Form")
        table_df = next(df for df in meta.fields if df.fieldtype == "Table" and not df.hidden)
        fields, tables = dv._doc_fields_and_tables(meta, None)
        t = next(t for t in tables if t["fieldname"] == table_df.fieldname)
        self.assertEqual(t["child_doctype"], table_df.options)
        self.assertEqual(t["rows"], [])
        self.assertTrue(t["columns"])
        self.assertNotIn(table_df.fieldname, [f["fieldname"] for f in fields])
        self.assertTrue(all(c["fieldtype"] != "Password" for c in t["columns"]))


class TestGetDocMeta(FrappeTestCase):
    def test_new_document_payload(self):
        out = dv.get_doc_meta("Lead Source")
        self.assertIsNone(out["name"])
        self.assertEqual(out["docstatus"], 0)
        self.assertTrue(out["perms"]["write"])
        self.assertFalse(out["perms"]["delete"])
        self.assertFalse(out["perms"]["submit"])

    def test_existing_document_payload(self):
        doc = frappe.get_doc({"doctype": "Lead Source", "name1": uid()}).insert()
        out = dv.get_doc_meta("Lead Source", doc.name)
        self.assertEqual(out["name"], doc.name)
        self.assertEqual(out["values"]["name1"], doc.name1)
        self.assertTrue(out["perms"]["read"] and out["perms"]["write"] and out["perms"]["delete"])
        self.assertEqual(out["title_field"], frappe.get_meta("Lead Source").title_field or "name")

    def test_single_doctype_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            dv.get_doc_meta("ERP Configuration")

    def test_permission_errors(self):
        with mock.patch.object(frappe, "has_permission", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                dv.get_doc_meta("Lead Source")  # create
            with self.assertRaises(frappe.PermissionError):
                dv.get_doc_meta("Lead Source", "x")  # read

    def test_quick_entry_flag(self):
        self.assertIsInstance(dv.get_quick_entry_flag("Lead Source"), bool)


class TestSaveDocFields(FrappeTestCase):
    def test_creates_then_updates(self):
        name = uid()
        out = dv.save_doc_fields("Lead Source", None, {"name1": name})
        self.assertEqual(out["name"], name)
        self.assertTrue(frappe.db.exists("Lead Source", name))

    def test_values_as_json_string(self):
        name = uid()
        out = dv.save_doc_fields("Lead Source", None, '{"name1": "%s"}' % name)
        self.assertEqual(out["values"]["name1"], name)

    def test_create_needs_permission(self):
        with mock.patch.object(frappe, "has_permission", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                dv.save_doc_fields("Lead Source", None, {"name1": uid()})

    def test_update_needs_permission(self):
        doc = frappe.get_doc({"doctype": "Lead Source", "name1": uid()}).insert()
        with mock.patch("frappe.model.document.Document.has_permission", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                dv.save_doc_fields("Lead Source", doc.name, {"name1": "x"})

    def test_missing_mandatory_field_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            dv.save_doc_fields("Lead Source", None, {})


class TestComments(FrappeTestCase):
    def setUp(self):
        self.doc = frappe.get_doc({"doctype": "Lead Source", "name1": uid()}).insert()

    def test_empty_comment_rejected(self):
        for text in ("", "   ", None):
            with self.assertRaises(frappe.ValidationError):
                dv.add_comment("Lead Source", self.doc.name, text)

    def test_note_is_stored_as_escaped_paragraphs(self):
        dv.add_comment("Lead Source", self.doc.name, "line one\n\n<b>two</b>")
        note = frappe.get_all("CRM Note", filters={"reference_name": self.doc.name}, fields=["note", "added_by"])[0]
        self.assertEqual(note.note, "<p>line one</p><p>&lt;b&gt;two&lt;/b&gt;</p>")
        self.assertEqual(note.added_by, frappe.session.user)

    def test_comments_require_read_permission(self):
        with mock.patch.object(frappe, "has_permission", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                dv.get_comments("Lead Source", self.doc.name)
            with self.assertRaises(frappe.PermissionError):
                dv.add_comment("Lead Source", self.doc.name, "hi")


class TestTransactionDefaults(FrappeTestCase):
    def doc(self, doctype="Sales Order", **kw):
        d = mock.MagicMock()
        d.doctype = doctype
        d.meta.has_field.return_value = False
        d.meta.get_field.return_value = None
        d.get.side_effect = lambda k, default=None: kw.get(k, default)
        return d

    def test_noop_for_plain_doc(self):
        dv._fill_transaction_defaults(self.doc("Lead Source"))

    def test_company_comes_from_erp_configuration_only_when_empty(self):
        d = self.doc()
        d.meta.has_field.side_effect = lambda f: f == "company"
        with mock.patch.object(frappe.db, "get_single_value", return_value="Acme"), mock.patch.object(frappe.db, "exists", return_value=False):
            dv._fill_transaction_defaults(d)
        self.assertEqual(d.company, "Acme")
        d2 = self.doc(company="Mine")
        d2.meta.has_field.side_effect = lambda f: f == "company"
        with mock.patch.object(frappe.db, "get_single_value", return_value="Acme"), mock.patch.object(frappe.db, "exists", return_value=False):
            d2.company = "Mine"
            dv._fill_transaction_defaults(d2)
        self.assertEqual(d2.company, "Mine")
