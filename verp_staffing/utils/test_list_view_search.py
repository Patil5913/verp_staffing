from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import list_view as lv


def df(fieldname, fieldtype="Data", label=None, options=None, hidden=0, in_list_view=0):
    return SimpleNamespace(fieldname=fieldname, fieldtype=fieldtype, label=label or fieldname.replace("_", " ").title(),
                           options=options, hidden=hidden, in_list_view=in_list_view)


FIELDS = [
    df("status", "Select", options="Open\nIn Progress\nClosed"),
    df("lead_owner", "Data", label="Lead Owner"),
    df("amount", "Currency"),
    df("qty", "Int"),
    df("is_vip", "Check", label="VIP"),
    df("due", "Date"),
    df("secret", "Data", hidden=1),
]
META = SimpleNamespace(fields=FIELDS, title_field="lead_owner")
INDEX = lv._field_key_index(META)
ALT = lv._key_alternation(INDEX)


def fd(fieldtype, options=None):
    return {"fieldname": "f", "fieldtype": fieldtype, "options": options}


class TestKeyIndex(FrappeTestCase):
    def test_aliases_and_builtins(self):
        for key in ("status", "lead owner", "lead_owner", "name", "modified"):
            self.assertIn(lv._normalize_key(key), INDEX)
        self.assertEqual(INDEX["lead owner"]["fieldname"], "lead_owner")
        self.assertIn(lv._normalize_key(lv.LAST_UPDATED_FIELD["label"]), INDEX)

    def test_hidden_excluded_unless_in_list_view(self):
        self.assertNotIn("secret", INDEX)
        idx = lv._field_key_index(SimpleNamespace(fields=[df("secret", hidden=1, in_list_view=1)]))
        self.assertIn("secret", idx)

    def test_normalize_key(self):
        self.assertEqual(lv._normalize_key("  Lead__Owner  "), "lead owner")

    def test_alternation_longest_first(self):
        idx = {"last": {}, "last updated": {}}
        alt = lv._key_alternation(idx)
        self.assertLess(alt.index("updated"), alt.index("|"))


class TestCoerce(FrappeTestCase):
    def test_check(self):
        for v in ("1", "Yes", "TRUE", "y"):
            self.assertEqual(lv._coerce_value(fd("Check"), v), 1)
        for v in ("0", "no", "False", "n"):
            self.assertEqual(lv._coerce_value(fd("Check"), v), 0)
        self.assertIsNone(lv._coerce_value(fd("Check"), "maybe"))

    def test_select_case_insensitive(self):
        f = fd("Select", "Open\nIn Progress")
        self.assertEqual(lv._coerce_value(f, "in progress"), "In Progress")
        self.assertIsNone(lv._coerce_value(f, "nope"))

    def test_numbers(self):
        self.assertEqual(lv._coerce_value(fd("Int"), "3.9"), 3)
        self.assertEqual(lv._coerce_value(fd("Currency"), "3.5"), 3.5)
        self.assertIsNone(lv._coerce_value(fd("Float"), "abc"))

    def test_dates(self):
        self.assertEqual(lv._coerce_value(fd("Date"), "17 Sept 2026"), "2026-09-17")
        self.assertEqual(lv._coerce_value(fd("Datetime"), "17 Sept 2026, 15:45"), "2026-09-17 15:45:00")
        self.assertEqual(lv._coerce_value(fd("Datetime"), "17 Sept 2026"), "2026-09-17 00:00:00")
        self.assertEqual(lv._coerce_value(fd("Datetime"), "17 Sept 2026", end_of_day=True), "2026-09-17 23:59:59")
        self.assertEqual(lv._coerce_value(fd("Datetime"), "17 Sept 2026 10:00", end_of_day=True), "2026-09-17 10:00:00")
        self.assertIsNone(lv._coerce_value(fd("Date"), "zzzz qqqq"))

    def test_text_unchanged(self):
        self.assertEqual(lv._coerce_value(fd("Data"), "abc"), "abc")


class TestFieldCondition(FrappeTestCase):
    def test_blank(self):
        self.assertIsNone(lv._field_condition(fd("Data"), "=", "  "))

    def test_equals_defaults(self):
        self.assertEqual(lv._field_condition(fd("Data"), "=", "bob"), ("like", "%bob%"))
        self.assertEqual(lv._field_condition(fd("Select", "Open"), "=", "open"), ("=", "Open"))
        self.assertEqual(lv._field_condition(fd("Select", "Open"), "=", "op"), ("like", "%op%"))
        self.assertEqual(lv._field_condition(fd("Int"), "=", "5"), ("=", 5))
        self.assertEqual(lv._field_condition(fd("Int"), "=", "x"), ("like", "%x%"))
        self.assertEqual(lv._field_condition(fd("Check"), "=", "yes"), ("=", 1))
        self.assertIsNone(lv._field_condition(fd("Check"), "=", "maybe"))

    def test_date_equals(self):
        self.assertEqual(lv._field_condition(fd("Date"), "=", "17 Sept 2026"), ("=", "2026-09-17"))
        self.assertEqual(lv._field_condition(fd("Datetime"), "=", "17 Sept 2026"), ("like", "2026-09-17%"))
        self.assertEqual(lv._field_condition(fd("Datetime"), "=", "17 Sept 2026, 15:45"), ("like", "2026-09-17 15:45%"))

    def test_other_operators_need_typed_value(self):
        self.assertEqual(lv._field_condition(fd("Int"), ">", "5"), (">", 5))
        self.assertIsNone(lv._field_condition(fd("Int"), ">", "x"))
        self.assertEqual(lv._field_condition(fd("Data"), "!=", "x"), ("!=", "x"))


class TestClauseExtraction(FrappeTestCase):
    def test_unquote_and_tokens(self):
        self.assertEqual(lv._unquote('"a b"'), "a b")
        self.assertEqual(lv._unquote("'x'"), "x")
        self.assertEqual(lv._unquote('"x'), '"x')
        self.assertEqual(lv._free_text_tokens('foo "bar baz" \'q\' ""'), ["foo", "bar baz", "q"])

    def test_comparisons(self):
        conds, rest = lv._extract_comparison_clauses('status=open amount>=10 widget lead owner="Ann Lee"', INDEX, ALT)
        self.assertEqual(
            sorted(conds),
            sorted([("status", "=", "Open"), ("amount", ">=", 10.0), ("lead_owner", "like", "%Ann Lee%")]),
        )
        self.assertEqual(rest.split(), ["widget"])

    def test_unusable_comparison_stays_as_text(self):
        conds, rest = lv._extract_comparison_clauses("amount>abc", INDEX, ALT)
        self.assertEqual(conds, [])
        self.assertEqual(rest, "amount>abc")

    def test_unknown_key_is_free_text(self):
        conds, rest = lv._extract_comparison_clauses("foo=bar", INDEX, ALT)
        self.assertEqual((conds, rest), ([], "foo=bar"))

    def test_between(self):
        conds, rest = lv._extract_between_clauses("due between 17 sept 2026 to 25 sept 2026 status=open", INDEX, ALT)
        self.assertEqual(conds, [("due", "2026-09-17", "2026-09-25")])
        self.assertEqual(rest.strip(), "status=open")

    def test_between_datetime_end_of_day(self):
        conds, _ = lv._extract_between_clauses("modified between 17 sept 2026 and 25 sept 2026", INDEX, ALT)
        self.assertEqual(conds, [("modified", "2026-09-17 00:00:00", "2026-09-25 23:59:59")])

    def test_between_without_separator_or_bad_values_is_kept(self):
        for txt in ("due between 17 sept 2026", "due between foo to bar"):
            conds, rest = lv._extract_between_clauses(txt, INDEX, ALT)
            self.assertEqual((conds, rest), ([], txt))


class TestResolveSearchFilter(FrappeTestCase):
    def setUp(self):
        for target, kw in (
            ("_check_read", {}),
            ("_matching_names", {"side_effect": lambda dt, fields, term: {"A", "B"} if term == "x" else {"B", "C"}}),
        ):
            p = mock.patch.object(lv, target, **kw)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(frappe, "get_meta", return_value=SimpleNamespace(fields=FIELDS, title_field=None))
        p.start()
        self.addCleanup(p.stop)

    def test_empty(self):
        self.assertEqual(lv.resolve_search_filter("Lead", None), {"filters": []})
        self.assertEqual(lv.resolve_search_filter("Lead", "  "), {"filters": []})
        self.assertEqual(lv.resolve_search_filter("Lead", "and"), {"filters": []})

    def test_and_mode_intersects(self):
        self.assertEqual(lv.resolve_search_filter("Lead", "x y"), {"filters": [["name", "in", ["B"]]]})

    def test_clause_filters(self):
        r = lv.resolve_search_filter("Lead", "status=open qty>2")
        self.assertEqual(sorted(r["filters"]), sorted([["status", "=", "Open"], ["qty", ">", 2]]))

    def test_range_becomes_two_filters(self):
        r = lv.resolve_search_filter("Lead", "due between 1 jan 2026 to 5 jan 2026")
        self.assertEqual(r["filters"], [["due", ">=", "2026-01-01"], ["due", "<=", "2026-01-05"]])

    def test_or_mode_unions(self):
        with mock.patch.object(frappe, "get_list", return_value=["Z"]):
            r = lv.resolve_search_filter("Lead", "x or status=open")
        self.assertEqual(r, {"filters": [["name", "in", ["A", "B", "Z"]]]})
