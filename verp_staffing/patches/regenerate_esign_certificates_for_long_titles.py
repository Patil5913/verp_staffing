"""The certificate's Document field used to overflow into Status when the document name was long; it now
wraps. Re-issue the certificate of already fully signed E Signs with a long title so they get the new layout.
The signed PDF is rebuilt first (the certificate is appended to it in place), same as the E Sign
"regenerate certificate" action. One failure never stops the rest."""

import frappe

LONG_TITLE = 30


def execute():
	from verp_staffing.esign.doctype.e_sign.e_sign import generate_certificate_page, save_rebuilt_pdf

	names = frappe.get_all(
		"E Sign",
		filters={"status": "Fully Signed", "certificate_pdf": ["is", "set"]},
		fields=["name", "title"],
	)
	for row in names:
		if len(row.title or "") <= LONG_TITLE:
			continue
		try:
			doc = frappe.get_doc("E Sign", row.name)
			save_rebuilt_pdf(doc)
			generate_certificate_page(doc.name)
			frappe.db.commit()
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Certificate re-issue failed: {row.name}")
	frappe.db.commit()
