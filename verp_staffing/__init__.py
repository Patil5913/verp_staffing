__version__ = "0.0.1"


def _guard_errprint():
    """frappe.errprint print()s every server traceback to stdout. When the
    process's stdout is a dead pipe (server started from a closed terminal or
    piped log) that print raises BrokenPipeError inside Frappe's own error
    handler, so the request dies with no response and the UI can only say it
    couldn't reach the server. Swallow the write failure so the real error
    (validation message, etc.) is still returned to the client."""
    try:
        import frappe

        original = frappe.errprint
        if getattr(original, "_verp_guarded", False):
            return

        def errprint(msg):
            try:
                original(msg)
            except (BrokenPipeError, OSError, ValueError):
                pass

        errprint._verp_guarded = True
        frappe.errprint = errprint
    except Exception:
        pass


class _PipeSafe:
    """Wraps a std stream so a write to a dead pipe is dropped, not raised."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        try:
            return self._stream.write(data)
        except (BrokenPipeError, OSError, ValueError):
            return len(data) if data else 0

    def flush(self):
        try:
            return self._stream.flush()
        except (BrokenPipeError, OSError, ValueError):
            return None

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _guard_std_streams():
    """Same dead-stdout problem as above, but for any print()/logging/library
    output (e.g. PDF or mail libraries), not just frappe.errprint: without this
    the request fails with BrokenPipeError and hides the real result."""
    import sys

    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and not isinstance(stream, _PipeSafe):
            setattr(sys, name, _PipeSafe(stream))


def _honour_system_max_file_size():
    """frappe.utils.file_manager.save_file (what E Sign, agreements and company logos use) only
    reads `max_file_size` from site_config — a value changed in System Settings / ERP
    Configuration was ignored, so a 12 MB signed PDF still failed at the old 10 MB. Use the same
    limit the File doctype itself applies (System Settings, then site_config)."""
    try:
        from frappe.utils import file_manager

        def get_max_file_size():
            from frappe.core.api.file import get_max_file_size as configured

            return configured()

        file_manager.get_max_file_size = get_max_file_size
    except Exception:
        pass


def _prioritise_verp_home_page():
    """verp_staffing is this site's only real app (home_page = "verp", and "/" itself
    redirects here — see website_redirects in hooks.py); vruglechat is installed alongside
    it purely to power the chat inside the portal, not as a destination on its own.

    Frappe's own "which app do you land on after login" logic (frappe.apps.get_default_path)
    lists every installed app with an add_to_apps_screen hook whose has_permission passes, and
    picks the app when only one qualifies. verp_staffing's own hook denies website users (see
    vrugle_staffing_erp/api/permission.check_app_permission — customers only belong in the
    portal, not the desk app list), which left vruglechat's "/chat" as the only candidate for
    a customer, and login sent them there with no way back into /verp.

    get_default_path is imported by name (`from frappe.apps import get_default_path`) into
    several modules that call it during login — patching frappe.apps.get_default_path alone
    would leave those old references pointing at the original function, so each is patched too.
    A user's own explicit choice (User.default_app) is still respected.
    """
    import frappe.apps

    original = frappe.apps.get_default_path

    def get_default_path(apps=None):
        if frappe.db.get_value("User", frappe.session.user, "default_app"):
            return original(apps)
        if "verp_staffing" in frappe.get_installed_apps():
            return "/verp"
        return original(apps)

    frappe.apps.get_default_path = get_default_path
    for module_name in (
        "frappe.auth",
        "frappe.sessions",
        "frappe.www.login",
        "frappe.utils.oauth",
        "frappe.website.utils",
        "frappe.core.doctype.user.user",
    ):
        try:
            module = __import__(module_name, fromlist=["get_default_path"])
            module.get_default_path = get_default_path
        except Exception:
            pass


_guard_errprint()
_guard_std_streams()
_honour_system_max_file_size()
_prioritise_verp_home_page()
