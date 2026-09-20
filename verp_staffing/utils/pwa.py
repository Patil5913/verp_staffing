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
