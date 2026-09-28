from verp_staffing.core.license.service import register_site


def after_install():
	"""Hooked from hooks.after_install: create `site_license`, generate this site's ids and
	register it with the subscription dashboard."""
	register_site()
