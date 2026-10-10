import io
import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from PIL import Image

from verp_staffing.utils import email_widget as ew
from verp_staffing.utils import pwa


def png(size=(40, 20), color=(255, 0, 0, 0)):
	buf = io.BytesIO()
	Image.new("RGBA", size, color).save(buf, "PNG")
	return buf.getvalue()


class TestRenderers(FrappeTestCase):
	def test_each_renderer_claims_only_its_own_path(self):
		self.assertTrue(pwa.ServiceWorkerRenderer("verp-sw.js").can_render())
		self.assertFalse(pwa.ServiceWorkerRenderer("verp-sw.js.map").can_render())
		self.assertTrue(pwa.ManifestRenderer("verp-manifest.webmanifest").can_render())
		self.assertFalse(pwa.ManifestRenderer("manifest.json").can_render())

	def test_icon_paths_are_limited_to_known_sizes(self):
		for path, ok in (("verp-icon-192.png", True), ("verp-icon-512.png", True), ("verp-icon-180.png", True), ("verp-icon-maskable-512.png", True),
			("verp-icon-64.png", False), ("verp-icon-512.jpg", False), ("../verp-icon-512.png", False), ("verp-icon-.png", False)):
			self.assertEqual(pwa.InstallIconRenderer(path).can_render(), ok, path)

	def test_the_service_worker_is_served_with_root_scope_headers(self):
		resp = pwa.ServiceWorkerRenderer("verp-sw.js").render()
		self.assertEqual(resp.headers["Service-Worker-Allowed"], "/verp")
		self.assertEqual(resp.headers["Cache-Control"], "no-cache")
		self.assertIn("javascript", resp.headers["Content-Type"])
		self.assertTrue(resp.get_data())

	def test_the_manifest_uses_the_branding(self):
		with mock.patch.object(pwa, "get_branding", return_value=("Acme ERP", "/logo.png")):
			resp = pwa.ManifestRenderer("verp-manifest.webmanifest").render()
		m = json.loads(resp.get_data())
		self.assertEqual((m["name"], m["short_name"], m["scope"], m["start_url"], m["display"]), ("Acme ERP", "Acme ERP", "/verp", "/verp", "standalone"))
		self.assertEqual({i["purpose"] for i in m["icons"]}, {"any", "maskable"})
		self.assertTrue(all(i["src"].startswith("/verp-icon-") for i in m["icons"]))

	def test_branding_falls_back_to_defaults(self):
		with mock.patch.object(pwa.frappe, "get_cached_doc", return_value=frappe._dict(app_name="", app_logo="")):
			self.assertEqual(pwa.get_branding(), (pwa.DEFAULT_NAME, pwa.DEFAULT_LOGO))
		with mock.patch.object(pwa.frappe, "get_cached_doc", return_value=frappe._dict(app_name="X", app_logo="/l.png")):
			self.assertEqual(pwa.get_branding(), ("X", "/l.png"))


class TestIcons(FrappeTestCase):
	def test_a_transparent_logo_is_flattened_onto_opaque_white_at_the_right_size(self):
		out = Image.open(io.BytesIO(pwa._flatten(png(color=(255, 0, 0, 0)), 192, False)))
		self.assertEqual((out.size, out.mode), ((192, 192), "RGB"))
		self.assertEqual(out.getpixel((0, 0)), (255, 255, 255))
		self.assertEqual(out.getpixel((96, 96)), (255, 255, 255))  # fully transparent logo shows only the white

	def test_an_opaque_logo_is_centred_and_maskable_icons_keep_a_wider_margin(self):
		raw = png((100, 100), (0, 0, 255, 255))
		plain = Image.open(io.BytesIO(pwa._flatten(raw, 200, False)))
		mask = Image.open(io.BytesIO(pwa._flatten(raw, 200, True)))
		self.assertEqual(plain.getpixel((100, 100)), (0, 0, 255))
		self.assertEqual(plain.getpixel((30, 100)), (0, 0, 255))     # 80% of 200 = 160 wide: spans x 20..180
		self.assertEqual(mask.getpixel((30, 100)), (255, 255, 255))  # 60% = 120 wide: spans x 40..160
		self.assertEqual(plain.getpixel((5, 5)), (255, 255, 255))

	def test_non_images_fall_back_to_the_bundled_icons(self):
		with mock.patch.object(pwa, "_logo_bytes", return_value=b"<svg/>"):
			data = pwa._icon_png(192, False)
		self.assertTrue(data.startswith(b"\x89PNG"))

	def test_no_logo_uses_the_bundled_icon_for_each_size(self):
		with mock.patch.object(pwa, "_logo_bytes", return_value=None):
			for size, maskable in ((180, False), (192, False), (512, False), (512, True)):
				self.assertTrue(pwa._icon_png(size, maskable).startswith(b"\x89PNG"), (size, maskable))

	def test_logo_bytes_ignores_remote_missing_and_broken_logos(self):
		def logo(url):
			return mock.patch.object(pwa.frappe, "get_cached_doc", return_value=frappe._dict(app_logo=url))
		with logo(""):
			self.assertIsNone(pwa._logo_bytes())
		with logo("https://cdn.example/l.png"):
			self.assertIsNone(pwa._logo_bytes())
		with logo("/files/l.png"), mock.patch.object(pwa.frappe, "get_doc", side_effect=frappe.DoesNotExistError):
			self.assertIsNone(pwa._logo_bytes())
		with logo("/files/l.png"), mock.patch.object(pwa.frappe, "get_doc") as gd:
			gd.return_value.get_content.return_value = b"x"
			self.assertEqual(pwa._logo_bytes(), b"x")

	def test_icon_renderer_serves_png_with_a_cache_header(self):
		with mock.patch.object(pwa, "_logo_bytes", return_value=png((50, 50), (0, 0, 0, 255))):
			resp = pwa.InstallIconRenderer("verp-icon-maskable-512.png").render()
		self.assertEqual(resp.headers["Content-Type"], "image/png")
		self.assertEqual(Image.open(io.BytesIO(resp.get_data())).size, (512, 512))
		self.assertIn("max-age", resp.headers["Cache-Control"])


class TestEmailWidget(FrappeTestCase):
	def test_guests_are_refused(self):
		old = frappe.session.user
		frappe.session.user = "Guest"
		try:
			with self.assertRaises(frappe.PermissionError):
				ew.get_email_widget_data()
		finally:
			frappe.session.user = old

	def test_no_email_account_means_an_empty_widget(self):
		with mock.patch.object(ew, "_get_my_email_account", return_value={}):
			out = ew.get_email_widget_data()
		self.assertEqual((out["email_account"], out["inbox"], out["sent"], out["last_synced_at"]), (None, [], [], None))

	def test_my_account_uses_the_first_linked_account_and_falls_back_to_the_user(self):
		with mock.patch.object(ew.frappe.db, "get_value", side_effect=[frappe._dict(email_account="Acct"), frappe._dict(email_id="me@corp.com"), "Pat Doe"]):
			self.assertEqual(ew._get_my_email_account(), {"email_account": "Acct", "sender_email": "me@corp.com", "sender_name": "Pat Doe"})
		with mock.patch.object(ew.frappe.db, "get_value", side_effect=[frappe._dict(email_account="Acct"), None, ""]):
			info = ew._get_my_email_account()
			self.assertEqual((info["sender_email"], info["sender_name"]), (frappe.session.user, frappe.session.user))
		with mock.patch.object(ew.frappe.db, "get_value", return_value=None):
			self.assertEqual(ew._get_my_email_account(), {})
		with mock.patch.object(ew.frappe.db, "get_value", return_value=frappe._dict(email_account="")):
			self.assertEqual(ew._get_my_email_account(), {})

	def test_inbox_and_sent_are_scoped_to_the_account_and_sender(self):
		info = {"email_account": "Acct", "sender_email": "me@corp.com", "sender_name": "Pat"}
		with mock.patch.object(ew, "_get_my_email_account", return_value=info), \
			mock.patch.object(ew.frappe, "get_list", side_effect=[[{"name": "C1"}], [{"name": "C2"}]]) as gl, \
			mock.patch.object(ew.frappe, "get_meta", return_value=frappe._dict(fields=[])):
			out = ew.get_email_widget_data()
		inbox_f, sent_f = gl.call_args_list[0].kwargs["filters"], gl.call_args_list[1].kwargs["filters"]
		self.assertEqual((inbox_f["email_account"], inbox_f["sent_or_received"]), ("Acct", "Received"))
		self.assertEqual((sent_f["sender"], sent_f["sent_or_received"]), ("me@corp.com", "Sent"))
		self.assertEqual((gl.call_args_list[0].kwargs["limit"], gl.call_args_list[1].kwargs["limit"]), (10, 5))
		self.assertEqual((out["inbox"], out["sent"], out["sender_name"]), ([{"name": "C1"}], [{"name": "C2"}], "Pat"))

	def test_last_sync_time_is_optional(self):
		info = {"email_account": "Acct", "sender_email": "a", "sender_name": "b"}
		with mock.patch.object(ew, "_get_my_email_account", return_value=info), mock.patch.object(ew.frappe, "get_list", return_value=[]):
			with mock.patch.object(ew.frappe, "get_meta", return_value=frappe._dict(fields=[frappe._dict(fieldname="last_synced_at")])), \
				mock.patch.object(ew.frappe.db, "get_value", return_value="2026-05-01 10:00:00"):
				self.assertEqual(ew.get_email_widget_data()["last_synced_at"], "2026-05-01 10:00:00")
			with mock.patch.object(ew.frappe, "get_meta", side_effect=Exception):
				self.assertIsNone(ew.get_email_widget_data()["last_synced_at"])
