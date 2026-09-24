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


_guard_errprint()
_guard_std_streams()
