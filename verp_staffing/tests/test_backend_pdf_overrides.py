"""PDF field placement (real PDFs built in memory), the Kanban retry wrapper, the maintenance page
and the User override."""

import io
import os
import tempfile
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject, RectangleObject
from reportlab.pdfgen import canvas

from verp_staffing.esign import pdf_render as pr
from verp_staffing.overrides import kanban_board as kb
from verp_staffing.overrides import override_user as ou
from verp_staffing.utils import maintenance_page as mp


def make_pdf(pages=1, size=(200, 100), rotate=0, crop=None):
	buf = io.BytesIO()
	c = canvas.Canvas(buf, pagesize=size)
	for _ in range(pages):
		c.drawString(5, 5, "base")
		c.showPage()
	c.save()
	reader = PdfReader(io.BytesIO(buf.getvalue()))
	writer = PdfWriter()
	for page in reader.pages:
		if rotate:
			page[NameObject("/Rotate")] = NumberObject(rotate)
		if crop:
			page.cropbox = RectangleObject(crop)
		writer.add_page(page)
	out = io.BytesIO()
	writer.write(out)
	return out.getvalue()


def geo(**kw):
	return pr.PageGeometry(PdfReader(io.BytesIO(make_pdf(**kw))).pages[0])


class TestPageGeometry(FrappeTestCase):
	def test_plain_page(self):
		g = geo(size=(200, 100))
		self.assertEqual((g.width, g.height, g.rotation), (200, 100, 0))

	def test_rotated_pages_swap_the_visual_size(self):
		for rotation in (90, 270):
			g = geo(size=(200, 100), rotate=rotation)
			self.assertEqual((g.width, g.height, g.rotation), (100, 200, rotation))
		g = geo(size=(200, 100), rotate=180)
		self.assertEqual((g.width, g.height), (200, 100))

	def test_odd_rotation_is_ignored(self):
		self.assertEqual(geo(rotate=45).rotation, 0)
		self.assertEqual(geo(rotate=450).rotation, 90)

	def test_crop_box_defines_the_visible_page_and_is_clipped_to_the_media_box(self):
		g = geo(size=(200, 100), crop=[10, 10, 110, 60])
		self.assertEqual((g.x0, g.y0, g.width, g.height), (10, 10, 100, 50))
		g = geo(size=(200, 100), crop=[-50, -50, 500, 500])
		self.assertEqual((g.width, g.height), (200, 100))

	def test_rect_converts_top_left_fractions_to_bottom_left_points(self):
		g = geo(size=(200, 100))
		self.assertEqual(g.rect(0, 0, 0.5, 0.5), (0, 50, 100, 50))
		self.assertEqual(g.rect(0.25, 0.8, 0.5, 0.2), (50, 0, 100, 20))

	def test_overlay_transform_per_rotation(self):
		for rotation in (0, 90, 180, 270):
			self.assertIsNotNone(geo(rotate=rotation).overlay_transform())


class TestTextHelpers(FrappeTestCase):
	def test_wrap_keeps_explicit_newlines_and_wraps_long_lines(self):
		self.assertEqual(pr.wrap_lines("a\r\nb\n\nc", 500, 12), ["a", "b", "", "c"])
		lines = pr.wrap_lines("the quick brown fox jumps over the lazy dog", 60, 12)
		self.assertGreater(len(lines), 2)
		self.assertTrue(all(pr.stringWidth(l, pr.FONT_NAME, 12) <= 60 for l in lines))
		self.assertEqual(" ".join(lines), "the quick brown fox jumps over the lazy dog")

	def test_a_word_wider_than_the_box_is_broken_by_characters(self):
		lines = pr.wrap_lines("x" * 100, 30, 12)
		self.assertGreater(len(lines), 1)
		self.assertEqual("".join(lines), "x" * 100)
		self.assertTrue(all(pr.stringWidth(l, pr.FONT_NAME, 12) <= 30 for l in lines))

	def test_is_checked(self):
		for yes in ("1", "TRUE", " yes ", "Checked", "on", 1, True):
			self.assertTrue(pr.is_checked(yes), yes)
		for no in ("0", "", "no", "off", None, 0, False):
			self.assertFalse(pr.is_checked(no), no)

	def test_blank_values_draw_nothing(self):
		c = mock.Mock()
		pr.draw_text(c, "", 0, 0, 100, 20)
		pr.draw_text(c, None, 0, 0, 100, 20)
		c.drawString.assert_not_called()

	def test_lines_that_do_not_fit_the_box_are_dropped(self):
		c = mock.Mock()
		pr.draw_text(c, "one\ntwo\nthree\nfour", 0, 0, 100, 25, font_size=10)
		self.assertEqual([call.args[2] for call in c.drawString.call_args_list], ["one", "two"])

	def test_text_starts_below_the_top_edge_of_the_box(self):
		c = mock.Mock()
		pr.draw_text(c, "hi", 5, 10, 100, 20, font_size=10)
		x, y, text = c.drawString.call_args.args
		self.assertEqual((x, text), (5, "hi"))
		self.assertAlmostEqual(y, 30 - 10 * pr.BASELINE_FROM_TOP)

	def test_checkbox_draws_a_tick_only_when_checked(self):
		c = mock.Mock(); pr.draw_checkbox(c, False, 0, 0, 20, 20)
		self.assertEqual((c.rect.call_count, c.line.call_count), (1, 0))
		c = mock.Mock(); pr.draw_checkbox(c, True, 0, 0, 20, 20)
		self.assertEqual((c.rect.call_count, c.line.call_count), (1, 2))


class TestFilesAndStamping(FrappeTestCase):
	def test_resolve_file_path(self):
		self.assertIsNone(pr.resolve_file_path(""))
		self.assertIsNone(pr.resolve_file_path("relative/file.pdf"))
		self.assertIsNone(pr.resolve_file_path("/files/definitely-missing.pdf"))
		self.assertIsNone(pr.resolve_file_path("/private/files/definitely-missing.pdf"))
		with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
			self.assertEqual(pr.resolve_file_path(f.name), f.name)

	def test_public_and_private_urls_map_into_the_site_folder(self):
		with mock.patch.object(pr.os.path, "exists", return_value=True):
			self.assertTrue(pr.resolve_file_path("/files/a.pdf").endswith("public/files/a.pdf"))
			self.assertTrue(pr.resolve_file_path("/private/files/a.pdf").endswith("private/files/a.pdf"))

	def test_draw_image_ignores_missing_files(self):
		c = mock.Mock()
		pr.draw_image_fit(c, "/nope/missing.png", 0, 0, 10, 10)
		c.drawImage.assert_not_called()

	def test_draw_image_fits_and_centres(self):
		from PIL import Image
		c = mock.Mock()
		pr.draw_image_fit(c, Image.new("RGB", (100, 50)), 0, 0, 40, 40)
		args = c.drawImage.call_args.args
		self.assertEqual(args[1:], (0, 10, 40, 20))

	def test_stamp_adds_text_to_every_page_and_keeps_the_originals(self):
		with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
			f.write(make_pdf(pages=2)); path = f.name
		try:
			seen = []
			def draw(c, n, g):
				seen.append((n, g.width, g.height))
				x, y, w, h = g.rect(0.1, 0.1, 0.8, 0.3)
				pr.draw_text(c, f"STAMP{n}", x, y, w, h)
			out = pr.stamp_pdf(path, draw)
		finally:
			os.unlink(path)
		self.assertEqual(seen, [(1, 200, 100), (2, 200, 100)])
		pages = PdfReader(io.BytesIO(out)).pages
		self.assertEqual(len(pages), 2)
		for i, page in enumerate(pages, 1):
			text = page.extract_text()
			self.assertIn(f"STAMP{i}", text)
			self.assertIn("base", text)

	def test_stamping_a_rotated_page_still_lands_on_the_page(self):
		with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
			f.write(make_pdf(rotate=90)); path = f.name
		try:
			out = pr.stamp_pdf(path, lambda c, n, g: pr.draw_text(c, "ROT", *g.rect(0.1, 0.1, 0.5, 0.2)))
		finally:
			os.unlink(path)
		self.assertIn("ROT", PdfReader(io.BytesIO(out)).pages[0].extract_text())


class TestKanbanRetry(FrappeTestCase):
	def test_returns_the_first_success_without_touching_the_db(self):
		fn = mock.Mock(return_value="ok", __name__="fn")
		with mock.patch.object(kb.frappe.db, "rollback") as rb:
			self.assertEqual(kb._retry_on_deadlock(fn, 1, a=2), "ok")
		fn.assert_called_once_with(1, a=2)
		rb.assert_not_called()

	def test_retries_after_a_deadlock_with_a_rollback_and_backoff(self):
		fn = mock.Mock(side_effect=[frappe.QueryDeadlockError("x"), "ok"], __name__="fn")
		with mock.patch.object(kb.frappe.db, "rollback") as rb, mock.patch.object(kb.frappe, "log_error"), mock.patch.object(kb.time, "sleep") as sl:
			self.assertEqual(kb._retry_on_deadlock(fn), "ok")
		rb.assert_called_once()
		sl.assert_called_once_with(kb.RETRY_BACKOFF_SECONDS)

	def test_gives_up_after_the_maximum_attempts(self):
		fn = mock.Mock(side_effect=frappe.QueryDeadlockError("still"), __name__="fn")
		with mock.patch.object(kb.frappe.db, "rollback"), mock.patch.object(kb.frappe, "log_error"), mock.patch.object(kb.time, "sleep") as sl:
			with self.assertRaises(frappe.QueryDeadlockError):
				kb._retry_on_deadlock(fn)
		self.assertEqual(fn.call_count, kb.MAX_RETRIES)
		self.assertEqual([c.args[0] for c in sl.call_args_list], [0.3, 0.6][: kb.MAX_RETRIES - 1])

	def test_other_errors_are_not_retried(self):
		fn = mock.Mock(side_effect=ValueError("bad"), __name__="fn")
		with self.assertRaises(ValueError):
			kb._retry_on_deadlock(fn)
		fn.assert_called_once()

	def test_dispatch_only_kwargs_are_removed_before_calling_core(self):
		with mock.patch.object(kb, "_retry_on_deadlock") as retry:
			kb.update_order("a", cmd="x.y", board_name="B")
			kb.update_order_for_single_card(cmd="x.y", docname="D")
		self.assertEqual(retry.call_args_list[0].args[1:], ("a",))
		self.assertEqual(retry.call_args_list[0].kwargs, {"board_name": "B"})
		self.assertEqual(retry.call_args_list[1].kwargs, {"docname": "D"})
		self.assertIs(retry.call_args_list[0].args[0], kb._core.update_order)
		self.assertIs(retry.call_args_list[1].args[0], kb._core.update_order_for_single_card)


class TestMaintenancePage(FrappeTestCase):
	def renderer(self, path):
		r = mp.MaintenancePageRenderer.__new__(mp.MaintenancePageRenderer)
		r.path = path
		return r

	def test_only_takes_over_the_message_page_during_maintenance(self):
		with mock.patch.object(mp.frappe, "conf", frappe._dict(maintenance_mode=1)):
			self.assertTrue(self.renderer("message").can_render())
			self.assertFalse(self.renderer("login").can_render())
		with mock.patch.object(mp.frappe, "conf", frappe._dict(maintenance_mode=0)):
			self.assertFalse(self.renderer("message").can_render())

	def test_response_is_a_503_that_refreshes_and_is_not_cached(self):
		r = self.renderer("message")
		with mock.patch.object(r, "build_response", create=True) as build:
			r.render()
		html = build.call_args.args[0]
		self.assertIn(mp.LOGO, html)
		self.assertIn(mp.FAVICON, html)
		self.assertIn('http-equiv="refresh"', html)
		self.assertNotIn("{logo}", html)
		self.assertEqual(build.call_args.kwargs["http_status_code"], 503)
		self.assertEqual(build.call_args.kwargs["headers"]["Retry-After"], "30")
		self.assertEqual(build.call_args.kwargs["headers"]["Cache-Control"], "no-store")


class TestUserOverride(FrappeTestCase):
	def user(self, **kw):
		u = mock.MagicMock(spec=ou.CustomUser)
		u.flags = frappe._dict(kw.pop("flags", {}))
		for k, v in {"name": "a@x.com", "user_type": "System User", **kw}.items():
			setattr(u, k, v)
		return u

	def test_quick_entry_hides_role_profile(self):
		fields = [{"fieldname": "email"}, {"fieldname": "role_profile_name"}]
		with mock.patch.object(ou.User, "get_quick_entry_fields", classmethod(lambda cls: fields), create=True):
			self.assertEqual(ou.CustomUser.get_quick_entry_fields(), [{"fieldname": "email"}])

	def test_role_check_is_disabled(self):
		self.assertIsNone(ou.CustomUser.check_roles_added(self.user()))

	def run_on_update(self, user, exists=False, sample=False):
		with mock.patch.object(ou.User, "on_update"), mock.patch.object(ou.frappe.db, "exists", return_value=exists), mock.patch.object(
			ou.frappe, "flags", frappe._dict(in_sample_data_import=sample)
		), mock.patch.object(ou.frappe, "msgprint") as mp_:
			ou.CustomUser.on_update(user)
		return mp_

	def test_new_staff_user_without_employee_gets_a_reminder(self):
		self.assertTrue(self.run_on_update(self.user(flags={"in_insert": True})).called)

	def test_no_reminder_for_customers_updates_admin_sample_data_or_existing_employees(self):
		self.assertFalse(self.run_on_update(self.user(flags={"in_insert": True}, user_type="Website User")).called)
		self.assertFalse(self.run_on_update(self.user(flags={})).called)
		self.assertFalse(self.run_on_update(self.user(flags={"in_insert": True}, name="Administrator")).called)
		self.assertFalse(self.run_on_update(self.user(flags={"in_insert": True}), sample=True).called)
		self.assertFalse(self.run_on_update(self.user(flags={"in_insert": True}), exists=True).called)

	def run_after_insert(self, user, has_role=False):
		with mock.patch.object(ou.User, "after_insert"), mock.patch.object(ou.frappe.db, "exists", return_value=has_role):
			ou.CustomUser.after_insert(user)

	def test_staff_get_the_inbox_user_role_once(self):
		u = self.user(); self.run_after_insert(u)
		u.append.assert_called_once_with("roles", {"role": "Inbox User"})
		u.save.assert_called_once_with(ignore_permissions=True)

	def test_inbox_role_is_skipped_for_system_accounts_customers_and_holders(self):
		for u, has in ((self.user(name="Administrator"), False), (self.user(name="Guest"), False), (self.user(user_type="Website User"), False), (self.user(), True)):
			self.run_after_insert(u, has)
			u.append.assert_not_called()

	def test_mail_is_sent_with_the_default_sender_only_when_vrugledm_is_installed(self):
		captured = {}
		def fake_super_send(self_, subject, template, add_args, now=None, custom_template=None):
			captured["sendmail_is_patched"] = ou.frappe.sendmail is not real
		real = ou.frappe.sendmail
		u = self.user()
		with mock.patch.object(ou.frappe, "get_installed_apps", return_value=["frappe"]), mock.patch.object(ou.User, "send_login_mail", fake_super_send):
			ou.CustomUser.send_login_mail(u, "s", "t", {})
		self.assertFalse(captured["sendmail_is_patched"])
		with mock.patch.object(ou.frappe, "get_installed_apps", return_value=["frappe", "vrugledm"]), mock.patch.object(ou.User, "send_login_mail", fake_super_send):
			ou.CustomUser.send_login_mail(u, "s", "t", {})
		self.assertTrue(captured["sendmail_is_patched"])
		self.assertIs(ou.frappe.sendmail, real)

	def test_pending_email_passwords_are_published_as_a_default(self):
		with mock.patch.object(ou.frappe, "get_all", return_value=["a@x.com", "b@x.com"]) as ga, mock.patch("frappe.utils.set_default") as sd:
			ou.ask_pass_update()
		self.assertEqual(ga.call_args.kwargs["filters"], {"awaiting_password": 1, "used_oauth": 0})
		sd.assert_called_once_with("email_user_password", "a@x.com,b@x.com")
