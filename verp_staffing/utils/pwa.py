import io
import re
from pathlib import Path

from PIL import Image, ImageOps

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

SW_PATH = "verp-sw.js"
SW_FILE = Path(frappe.get_app_path("verp_staffing", "public", "pwa", "sw.js"))


class ServiceWorkerRenderer(BaseRenderer):
	"""Serve the PWA service worker from the site root.

	A worker's scope is capped at the directory it is served from, and Frappe
	serves app assets under /assets/…, so it is delivered from /verp-sw.js
	instead (scope is then narrowed to /verp at registration time).
	"""

	def can_render(self):
		return self.path == SW_PATH

	def render(self):
		return self.build_response(
			SW_FILE.read_text(),
			headers={
				"Content-Type": "application/javascript; charset=utf-8",
				"Cache-Control": "no-cache",
				"Service-Worker-Allowed": "/verp",
			},
		)


DEFAULT_NAME = "Verp Placements"
DEFAULT_LOGO = "/assets/verp_staffing/images/Vrugle-icon-Logo-trimmed.png"


def get_branding():
	"""App name and logo from Website Settings (edited in ERP Configuration)."""
	doc = frappe.get_cached_doc("Website Settings")
	return doc.app_name or DEFAULT_NAME, doc.app_logo or DEFAULT_LOGO


class ManifestRenderer(BaseRenderer):
	"""Web app manifest built from Website Settings, served at /verp-manifest.webmanifest."""

	def can_render(self):
		return self.path == "verp-manifest.webmanifest"

	def render(self):
		import json

		name, logo = get_branding()
		manifest = {
			"name": name,
			"short_name": name,
			"description": name,
			"id": "/verp",
			"start_url": "/verp",
			"scope": "/verp",
			"display": "standalone",
			"orientation": "any",
			"background_color": "#ffffff",
			"theme_color": "#0057e5",
			"icons": [
				{"src": "/verp-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
				{"src": "/verp-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
				{"src": "/verp-icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
			],
		}
		return self.build_response(
			json.dumps(manifest),
			headers={"Content-Type": "application/manifest+json; charset=utf-8", "Cache-Control": "no-cache"},
		)


# --- Install icons / manifest built from the Website Settings logo ----------
#
# iOS paints transparent apple-touch-icon pixels black, and Android shows the
# raw upload on whatever the launcher uses. So the uploaded logo is always
# flattened onto an opaque white square before being served as an install icon.

ICON_RE = re.compile(r"^verp-icon-(maskable-)?(\d+)\.png$")
ICON_SIZES = (180, 192, 512)
STATIC_DIR = Path(frappe.get_app_path("verp_staffing", "public", "pwa"))


def _logo_bytes():
	url = frappe.get_cached_doc("Website Settings").app_logo
	if not url:
		return None
	try:
		if url.startswith(("http://", "https://")):
			return None
		return frappe.get_doc("File", {"file_url": url}).get_content()
	except Exception:
		return None


def _flatten(raw, size, maskable):
	"""Logo centred on opaque white. Maskable icons keep a 20% safe margin."""
	logo = Image.open(io.BytesIO(raw)).convert("RGBA")
	inner = int(size * (0.6 if maskable else 0.8))
	logo = ImageOps.contain(logo, (inner, inner), Image.LANCZOS)  # unlike thumbnail(), also enlarges a small logo
	canvas = Image.new("RGB", (size, size), (255, 255, 255))
	canvas.paste(logo, ((size - logo.width) // 2, (size - logo.height) // 2), logo)
	out = io.BytesIO()
	canvas.save(out, "PNG")
	return out.getvalue()


def _icon_png(size, maskable):
	raw = _logo_bytes()
	if raw:
		try:
			return _flatten(raw, size, maskable)
		except Exception:  # e.g. SVG, which PIL can't read
			pass
	name = "icon-maskable-512.png" if maskable else (
		"apple-touch-icon.png" if size == 180 else f"icon-{size}.png"
	)
	return (STATIC_DIR / name).read_bytes()


class InstallIconRenderer(BaseRenderer):
	"""/verp-icon-<size>.png: the Website Settings logo on opaque white."""

	def can_render(self):
		return bool(self._icon_match())

	def _icon_match(self):
		m = ICON_RE.match(self.path)
		return m if m and int(m.group(2)) in ICON_SIZES else None

	def render(self):
		m = self._icon_match()
		return self.build_response(
			_icon_png(int(m.group(2)), bool(m.group(1))),
			headers={"Content-Type": "image/png", "Cache-Control": "public, max-age=3600"},
		)
