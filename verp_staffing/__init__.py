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


_guard_errprint()
