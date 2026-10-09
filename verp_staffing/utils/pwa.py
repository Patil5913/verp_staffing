from pathlib import Path

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
			"background_color": "#f6f8fb",
			"theme_color": "#0057e5",
			"icons": [
				{"src": logo, "sizes": "192x192", "type": "image/png", "purpose": "any"},
				{"src": logo, "sizes": "512x512", "type": "image/png", "purpose": "any"},
			],
		}
		return self.build_response(
			json.dumps(manifest),
			headers={"Content-Type": "application/manifest+json; charset=utf-8", "Cache-Control": "no-cache"},
		)
