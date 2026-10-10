"""Every dotted path this app registers in hooks.py must import, so a moved or renamed function fails here
rather than silently when its event fires."""

import re

import frappe
from frappe.tests.utils import FrappeTestCase

APP = "verp_staffing"
DOTTED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
# hook keys whose values are not python paths
NON_CODE = {
    "app_name", "app_title", "app_publisher", "app_description", "app_email", "app_license", "app_logo_url",
    "required_apps", "fixtures", "app_include_js", "app_include_css", "web_include_js", "web_include_css",
    "page_js", "doctype_js", "doctype_list_js", "doctype_tree_js", "doctype_calendar_js", "website_route_rules",
    "website_redirects", "after_migrate_message", "add_to_apps_screen", "export_python_type_annotations",
    "ignore_links_on_delete", "treeviews", "standard_queries", "sounds", "home_page", "role_home_page",
    "email_brand_image", "default_log_clearing_doctypes", "override_whitelisted_methods_note",
}


def _walk(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _walk(v)


def our_hook_paths():
    hooks = frappe.get_hooks(app_name=APP)
    for key, value in hooks.items():
        if key in NON_CODE:
            continue
        for path in _walk(value):
            if path.startswith(APP + ".") and DOTTED.match(path):
                yield key, path


class TestHooksResolve(FrappeTestCase):
    def test_every_hook_path_imports(self):
        broken = []
        for key, path in sorted(set(our_hook_paths())):
            try:
                frappe.get_attr(path)
            except Exception as e:  # ImportError, AttributeError, ...
                broken.append(f"{key}: {path} ({type(e).__name__}: {e})")
        self.assertFalse(broken, "hooks point at code that does not exist:\n" + "\n".join(broken))

    def test_some_hooks_were_checked(self):
        self.assertGreater(len(set(our_hook_paths())), 20)
