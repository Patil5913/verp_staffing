import io
import json
import os
import uuid
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from PIL import Image

from verp_staffing.crm.doctype.lead_detail_form import lead_detail_form as ldf

AUDIT = {
	"form visit logs": [{"event": "form_opened", "timestamp": "02-10-2026, 08:15:30 UTC", "ip": "1.2.3.4", "user_agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}],
	"signature update logs": [{"event": "signature_updated", "method": "Draw", "timestamp": "02-10-2026, 08:16:00 UTC", "ip": "1.2.3.4"}],
	"authentication logs": [{"event": "otp_verified", "timestamp": "02-10-2026, 08:15:50 UTC", "ip": "1.2.3.4"}],
	"concern accepted": [{"event": "concern accepted", "label": "I agree", "timestamp": "02-10-2026, 08:16:10 UTC"}],
}
FIELD = {"type": "Signature", "page": 1, "x": 50, "y": 100, "width": 150, "height": 50, "page_width": 595, "page_height": 842}


def make_pdf(pages=2):
	from reportlab.pdfgen import canvas

	buf = io.BytesIO()
	c = canvas.Canvas(buf, pagesize=(595, 842))
	for i in range(pages):
		c.drawString(72, 700, f"Agreement page {i + 1}")
		c.showPage()
	c.save()
	return buf.getvalue()


def make_png():
	buf = io.BytesIO()
	Image.new("RGBA", (120, 40), (0, 0, 200, 255)).save(buf, "PNG")
	return buf.getvalue()


class TestSigningPdf(FrappeTestCase):
	def setUp(self):
		self.dir = frappe.get_site_path("private", "files")
		os.makedirs(self.dir, exist_ok=True)
		self.paths = []

	def tearDown(self):
		for p in self.paths:
			if os.path.exists(p):
				os.remove(p)

	def write(self, suffix, data):
		path = os.path.join(self.dir, f"zz_{uuid.uuid4().hex[:8]}{suffix}")
		with open(path, "wb") as f:
			f.write(data)
		self.paths.append(path)
		return path

	def sign(self, pages=2, fields=None, audit=AUDIT, signature=True, **kw):
		src = self.write(".pdf", make_pdf(pages))
		sig = self.write(".png", make_png()) if signature else None
		out = self.write(".pdf", b"")
		with self.agreement_stubs():
			ldf.apply_signature_and_audit_to_pdf(
				input_pdf_path=src, fields=fields if fields is not None else [FIELD],
				signature_image_path=os.path.basename(sig) if sig else None,
				audit_trail_text=json.dumps(audit), signer_name="Pat Doe", signer_email="pat@example.com",
				output_path=out, certificate_id="CERT-TEST-1", agreement=frappe._dict(name="AG-T", audit_trail=None), **kw,
			)
		return src, out

	def agreement_stubs(self):
		"""The PDF work is what is under test: the agreement record and the notification emails are stood in for."""
		from contextlib import ExitStack

		stack = ExitStack()
		stack.enter_context(mock.patch.object(ldf.frappe, "get_doc", return_value=frappe._dict(name="AG-T", sales_order=None)))
		stack.enter_context(mock.patch.object(ldf.frappe.db, "get_value", return_value=None))
		stack.enter_context(mock.patch.object(ldf.frappe.db, "set_value"))
		stack.enter_context(mock.patch.object(ldf.frappe.db, "sql"))
		return stack

	def page_count(self, path):
		from pdfrw import PdfReader

		return len(PdfReader(path).pages)

	def test_the_signed_document_keeps_its_pages_and_gains_a_certificate(self):
		src, out = self.sign(pages=2)
		self.assertGreater(self.page_count(out), 2)
		self.assertEqual(self.page_count(src), 2)  # the original is untouched when an output path is given

	def test_the_signature_is_drawn_only_on_its_page(self):
		_, with_sig = self.sign(pages=2)
		_, without = self.sign(pages=2, fields=[], signature=False)
		self.assertGreater(os.path.getsize(with_sig), os.path.getsize(without))

	def test_a_field_on_a_missing_page_is_ignored(self):
		_, out = self.sign(pages=1, fields=[{**FIELD, "page": 9}])
		self.assertGreaterEqual(self.page_count(out), 2)

	def test_non_signature_fields_are_not_drawn_as_signatures(self):
		_, a = self.sign(pages=1, fields=[{**FIELD, "type": "Text"}])
		_, b = self.sign(pages=1, fields=[FIELD])
		self.assertLess(os.path.getsize(a), os.path.getsize(b))

	def test_a_missing_signature_image_is_an_error(self):
		src = self.write(".pdf", make_pdf(1))
		with self.assertRaises(FileNotFoundError):
			ldf.apply_signature_and_audit_to_pdf(
				input_pdf_path=src, fields=[FIELD], signature_image_path="zz_does_not_exist.png",
				audit_trail_text=json.dumps(AUDIT), signer_name="P", signer_email="p@x.com", output_path=src + ".out", certificate_id="C",
			)

	def test_an_empty_audit_trail_fails_loudly_instead_of_skipping_the_certificate(self):
		src = self.write(".pdf", make_pdf(1))
		with self.assertRaises(frappe.ValidationError):
			ldf.apply_signature_and_audit_to_pdf(
				input_pdf_path=src, fields=[], signature_image_path=None, audit_trail_text="", signer_name="P",
				signer_email="p@x.com", output_path=src + ".out", certificate_id="C",
			)

	def test_the_audit_trail_can_come_from_the_agreement_record(self):
		src = self.write(".pdf", make_pdf(1))
		out = self.write(".pdf", b"")
		agreement = frappe._dict(name="AG-1", audit_trail=json.dumps(AUDIT))
		with self.agreement_stubs():
			ldf.apply_signature_and_audit_to_pdf(
				input_pdf_path=src, fields=[], signature_image_path=None, audit_trail_text="", signer_name="P",
				signer_email="p@x.com", output_path=out, agreement=agreement, certificate_id="C",
			)
		self.assertGreater(self.page_count(out), 1)

	def test_signature_box_helper_handles_no_image_and_tiny_boxes(self):
		from reportlab.pdfgen import canvas

		c = canvas.Canvas(io.BytesIO())
		self.assertIsNone(ldf.render_signature_box(c, None, 0, 0, 100, 40))
		from reportlab.lib.utils import ImageReader

		reader = ImageReader(io.BytesIO(make_png()))
		ldf.render_signature_box(c, reader, 0, 0, 3, 3)  # smaller than the padding: drawn at zero size, no error

	def test_apply_pdf_signature_validates_before_doing_any_work(self):
		with self.assertRaises(frappe.ValidationError):
			ldf.apply_pdf_signature(frappe._dict(signature_method="Draw"), "")
		with self.assertRaises(frappe.ValidationError):
			ldf.apply_pdf_signature(frappe._dict(signature_method="Other", form_token="bad"), "x.png")
