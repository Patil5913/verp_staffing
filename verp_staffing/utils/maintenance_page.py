import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

LOGO = "/assets/verp_staffing/images/Vrugle-icon-Logo-without-bg.svg"
FAVICON = "/assets/verp_staffing/images/vrugle-icon_logo.ico"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="theme-color" content="#0057e5" />
<meta http-equiv="refresh" content="30" />
<link rel="icon" href="{favicon}" sizes="any" />
<title>Verp Placements - Updating</title>
<style>
  :root {{ --bg:#f8fafc; --card:#fff; --text:#0f172a; --muted:#64748b; --border:#e2e8f0; --brand:#0057e5; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0b1120; --card:#111a2e; --text:#e5e9f0; --muted:#94a3b8; --border:#1e293b; --brand:#4d8dff; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center; padding:16px;
         background:var(--bg); color:var(--text);
         font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  .card {{ width:100%; max-width:440px; text-align:center; padding:40px 28px; background:var(--card);
          border:1px solid var(--border); border-radius:14px; }}
  .card img {{ width:64px; height:64px; margin-bottom:20px; }}
  h1 {{ margin:0 0 8px; font-size:20px; font-weight:600; }}
  p {{ margin:0; font-size:14px; line-height:1.55; color:var(--muted); }}
  .bar {{ margin:24px auto 0; width:120px; height:4px; border-radius:4px; background:var(--border); overflow:hidden; }}
  .bar::after {{ content:""; display:block; width:40%; height:100%; background:var(--brand);
                animation:slide 1.4s ease-in-out infinite; }}
  @keyframes slide {{ 0% {{ transform:translateX(-100%); }} 100% {{ transform:translateX(300%); }} }}
</style>
</head>
<body>
  <main class="card">
    <img src="{logo}" alt="Verp Placements" />
    <h1>We're updating the system</h1>
    <p>Verp Placements is being updated and will be back in a few moments.<br />This page refreshes automatically.</p>
    <div class="bar"></div>
  </main>
</body>
</html>
"""


class MaintenancePageRenderer(BaseRenderer):
	"""Branded replacement for Frappe's stock "Updating" message page.

	While a site is in maintenance mode Frappe answers every request with its
	generic message page (handle_session_stopped renders the "message" route
	with a 503). Page renderers from hooks run before the built-in ones, so this
	takes over that one case and leaves the message page alone otherwise.
	"""

	def can_render(self):
		return self.path == "message" and bool(frappe.conf.get("maintenance_mode"))

	def render(self):
		return self.build_response(
			PAGE.format(logo=LOGO, favicon=FAVICON),
			http_status_code=503,
			headers={"Content-Type": "text/html; charset=utf-8", "Retry-After": "30", "Cache-Control": "no-store"},
		)
