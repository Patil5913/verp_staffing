"""Every `verp_staffing.*` method the frontend calls by dotted path must exist and be whitelisted,
so a renamed or removed backend function fails here instead of at runtime in the browser."""

import importlib
import os
import re

import frappe
from frappe.tests.utils import FrappeTestCase

FRONTEND_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
PATH_RE = re.compile(r"""['"`](verp_staffing(?:\.[A-Za-z_][A-Za-z0-9_]*){2,})['"`]""")
# const API = 'verp_staffing.utils.mailbox' ... call(`${API}.get_mailbox`)
PREFIX_RE = re.compile(r"""const\s+(\w+)\s*=\s*['"`](verp_staffing(?:\.[A-Za-z_][A-Za-z0-9_]*)+)['"`]""")


def frontend_calls():
    found = {}
    for root, _dirs, files in os.walk(FRONTEND_SRC):
        for name in files:
            if not name.endswith((".js", ".vue")) or ".test." in name:
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for m in PATH_RE.finditer(text):
                found.setdefault(m.group(1), os.path.relpath(path, FRONTEND_SRC))
            for const, prefix in PREFIX_RE.findall(text):
                for m in re.finditer(r"\$\{" + const + r"\}\.([A-Za-z_][A-Za-z0-9_]*)", text):
                    found.setdefault(f"{prefix}.{m.group(1)}", os.path.relpath(path, FRONTEND_SRC))
    return found


def resolve(dotted):
    """The attribute `dotted` names, or None. A dotted path that is itself a module is a prefix, not a call."""
    try:
        importlib.import_module(dotted)
        return "module"
    except ImportError:
        pass
    module, _, attr = dotted.rpartition(".")
    try:
        return getattr(importlib.import_module(module), attr, None)
    except ImportError:
        return None


class TestFrontendApiContract(FrappeTestCase):
    def test_frontend_calls_exist_and_are_whitelisted(self):
        calls = frontend_calls()
        self.assertTrue(calls, "no frontend API calls found - is the scan path right?")
        missing, not_whitelisted = [], []
        for dotted, source in sorted(calls.items()):
            target = resolve(dotted)
            if target == "module":
                continue
            if target is None:
                missing.append(f"{dotted} (used in {source})")
            elif callable(target) and target not in frappe.whitelisted and not getattr(target, "__wrapped__", None):
                not_whitelisted.append(f"{dotted} (used in {source})")
        self.assertFalse(missing, "frontend calls methods that do not exist:\n" + "\n".join(missing))
        self.assertFalse(not_whitelisted, "frontend calls methods that are not whitelisted:\n" + "\n".join(not_whitelisted))


class TestFrontendDoctypeConfigs(FrappeTestCase):
    """Doctype names hard-coded in the frontend's per-doctype config must exist (matched case-insensitively,
    as the sidebar does), so a renamed doctype is caught here and not by a silently dead config entry."""

    def read(self, rel):
        with open(os.path.join(FRONTEND_SRC, rel), encoding="utf-8") as fh:
            return fh.read()

    def configured_doctypes(self):
        names = set(re.findall(r"'([A-Z][A-Za-z ]+)'", self.read("utils/layout/sidebarPlus.js")))
        options = self.read("configs/detail/listOptions.js")
        for block in re.findall(r"export const (?:NO_MANUAL_CREATE|PERSON_DOCTYPES) = new Set\(\[(.*?)\]\)", options, re.S):
            names |= set(re.findall(r"'([^']+)'", block))
        for block in re.findall(
            r"export const (?:STATUS_COLUMN_FIELDS_TO_HIDE|BULK_ACTIONS|ROW_ACTIONS|LIST_HEADERS|EXTRA_VIEWS|KANBAN) = \{(.*?)\n\}",
            options,
            re.S,
        ):
            names |= set(re.findall(r"^\s{2}'?([A-Z][A-Za-z ]+)'?:", block, re.M))
        return names

    def test_every_configured_doctype_exists(self):
        names = self.configured_doctypes()
        self.assertGreater(len(names), 20, "scan found too few doctype names - did the config files move?")
        known = {d.lower() for d in frappe.get_all("DocType", pluck="name")}
        missing = sorted(n for n in names if n.lower() not in known)
        self.assertFalse(missing, f"frontend config names doctypes that do not exist: {missing}")

    def test_report_presentation_configs_belong_to_real_reports(self):
        from verp_staffing.utils.reports import REPORT_INDEX

        text = self.read("configs/reports.js")
        block = text[text.index("export const REPORT_CONFIGS"):]
        names = set(re.findall(r"^  '([^']+)':", block, re.M))
        self.assertGreater(len(names), 5)
        known = {r["name"] for r in REPORT_INDEX} | set(frappe.get_all("Report", pluck="name"))
        missing = sorted(names - known)
        self.assertFalse(missing, f"reports.js configures reports that do not exist: {missing}")

    def test_detail_page_configs_name_real_doctypes(self):
        folder = os.path.join(FRONTEND_SRC, "configs", "detail")
        declared = {}
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".js") or ".test." in name:
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                for doctype in re.findall(r"^\s*doctype:\s*'([^']+)'", fh.read(), re.M):
                    declared[doctype] = name
        self.assertGreater(len(declared), 15)
        known = {d.lower() for d in frappe.get_all("DocType", pluck="name")}
        missing = {d: f for d, f in declared.items() if d.lower() not in known}
        self.assertFalse(missing, f"detail configs name doctypes that do not exist: {missing}")

    def all_sources(self):
        if not hasattr(self, "_sources"):
            self._sources = []
            for root, _dirs, files in os.walk(FRONTEND_SRC):
                for name in files:
                    if name.endswith((".js", ".vue")) and ".test." not in name:
                        with open(os.path.join(root, name), encoding="utf-8") as fh:
                            self._sources.append(fh.read())
        return self._sources

    def field_names_in(self, chunk):
        names = set()
        # a prompt's fields are arguments of the server method it calls, not doctype fields
        chunk = re.sub(r"prompt:\s*\[.*?\]\s*,", "", chunk, flags=re.S)
        for lst in re.findall(r"fieldnames:\s*\[(.*?)\]", chunk, re.S):
            names |= set(re.findall(r"'([a-z_0-9]+)'", lst))
        names |= set(re.findall(r"fieldname:\s*'([a-z_0-9]+)'", chunk))
        return names

    def test_detail_page_sections_use_fields_the_doctype_has(self):
        folder = os.path.join(FRONTEND_SRC, "configs", "detail")
        system = {"name", "owner", "creation", "modified", "docstatus"}
        problems, checked = [], 0
        for filename in sorted(os.listdir(folder)):
            if not filename.endswith(".js") or ".test." in filename:
                continue
            with open(os.path.join(folder, filename), encoding="utf-8") as fh:
                text = fh.read()
            # `export function xConfig({ doctype ... })` bodies are shared by every call that passes a doctype in
            factories = {m.group(1): m.start() for m in re.finditer(r"export function (\w+)\(\{ doctype", text)}
            body_ends = sorted([*factories.values(), len(text)])
            targets = []  # (doctype, chunk of config text)
            marks = [(m.start(), m.group(1)) for m in re.finditer(r"^\s*doctype:\s*'([^']+)'", text, re.M)]
            for i, (pos, doctype) in enumerate(marks):
                limit = min([e for e in [*(m[0] for m in marks[i + 1:]), *factories.values(), len(text)] if e > pos])
                targets.append((doctype, text[pos:limit]))
            for name, start in factories.items():
                end = next(e for e in body_ends if e > start)
                for source in self.all_sources():
                    for m in re.finditer(name + r"\(\{\s*doctype:\s*'([^']+)'", source):
                        targets.append((m.group(1), text[start:end]))
            shared = {}  # factory chunk -> the doctypes it serves: a field only one of them has is fine
            for doctype, chunk in targets:
                if frappe.db.exists("DocType", doctype):
                    shared.setdefault(chunk, []).append(doctype)
            for chunk, doctypes in shared.items():
                for field in self.field_names_in(chunk):
                    checked += 1
                    if field in system:
                        continue
                    if not any(frappe.get_meta(d).has_field(field) for d in doctypes):
                        problems.append(f"{filename}: {'/'.join(doctypes)}.{field}")
        self.assertGreater(checked, 40, "the scan found too few fields - did the config layout change?")
        self.assertFalse(problems, "detail configs use fields the doctype does not have:\n" + "\n".join(problems))
