"""Clean download addresses for the customer portal.

  /verp/portal/invoices/<invoice>/print              the printed invoice (PDF)
  /verp/portal/agreements/<agreement>/download       a signed agreement
  /verp/portal/documents/<field>/download            one of the customer's own documents
  /verp/portal/services/<service>/<record>/download  a service's latest document

These are pages, not API calls: the whitelisted /api/method endpoints they replace are gone. Each
route calls the same function as before, which takes the customer from the session and re-checks
that the record is theirs, so a guessed address gets the same refusal as a missing one.
"""

import mimetypes
import re

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

# name -> (address pattern, handler dotted path)
ROUTES = (
    (re.compile(r"^verp/portal/invoices/([^/]+)/print$"), "verp_staffing.crm.api.customer_portal.download_invoice"),
    (re.compile(r"^verp/portal/agreements/([^/]+)/download$"), "verp_staffing.crm.api.customer_portal.download_agreement"),
    (re.compile(r"^verp/portal/documents/([^/]+)/download$"), "verp_staffing.www.customer.download_lead_document"),
    (re.compile(r"^verp/portal/services/([^/]+)/([^/]+)/download$"), "verp_staffing.www.customer.download_document"),
)

HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


class PortalDownloadRenderer(BaseRenderer):
    def _request_path(self):
        request = getattr(frappe.local, "request", None)
        return (request.path if request else self.path) or ""

    def _match(self):
        # Frappe resolves route rules before picking a renderer, so for these addresses self.path is
        # already "verp" (the app's catch-all rule) and the address the browser asked for is on the
        # request. Anything else is Frappe routing internally (get_print renders the "printview"
        # page while this very request is still open); answering those would recurse forever.
        if (self.path or "").strip("/") != "verp":
            return None, ()
        path = self._request_path().strip("/")
        for pattern, handler in ROUTES:
            m = pattern.match(path)
            if m:
                return handler, m.groups()
        return None, ()

    def can_render(self):
        return self._match()[0] is not None

    def render(self):
        if frappe.session.user == "Guest":
            return self.build_response("", 302, {"Location": "/verp/login", **HEADERS})

        handler, args = self._match()
        try:
            frappe.get_attr(handler)(*args)
        except frappe.PermissionError:
            # a refusal is worth a trace: who asked, for what, and where it was refused
            frappe.log_error(frappe.get_traceback(), f"Portal download refused: {frappe.session.user} {self._request_path()}")
            return self.build_response("You don't have access to this file.", 403, {"Content-Type": "text/plain; charset=utf-8", **HEADERS})
        except Exception:
            # not signed yet, no file, print failure: never explain which to the customer
            frappe.log_error(frappe.get_traceback(), f"Portal download failed: {frappe.session.user} {self._request_path()}")
            return self.build_response("This file isn't available.", 404, {"Content-Type": "text/plain; charset=utf-8", **HEADERS})

        out = frappe.local.response
        filename = re.sub(r'[^A-Za-z0-9._ -]', "_", str(out.filename or "download"))
        is_pdf = out.type == "pdf" or filename.lower().endswith(".pdf")
        mimetype = "application/pdf" if is_pdf else (mimetypes.guess_type(filename)[0] or "application/octet-stream")
        disposition = "inline" if is_pdf else "attachment"
        return self.build_response(
            out.filecontent,
            200,
            {"Content-Type": mimetype, "Content-Disposition": f'{disposition}; filename="{filename}"', **HEADERS},
        )
