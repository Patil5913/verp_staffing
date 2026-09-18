"""Seeds a production site with demo data on `bench migrate`.

Wired into hooks.after_migrate. It is deliberately hard to trigger by
accident, because it writes hundreds of documents (submitted invoices and
payments post real GL entries):

  - never on a site in developer mode, unless site_config has
    `"force_demo_seed": 1`
  - never if site_config has `"skip_demo_seed": 1`
  - never before the site has a company (i.e. the setup wizard hasn't run)
  - only once: a global marker is set when a run finishes, so later migrates
    do nothing. To top the data up or retry after a failure, run it by hand:

        bench --site <site> execute verp_staffing.utils.seed_test_data.run_production

What it creates, and why it is safe to put in front of real users, is in
seed_test_data.run_production's docstring: two dedicated demo companies (the
real companies' books are untouched), everything tracked in the sample-data
log so "Remove Sample Data" on ERP Configuration clears it.

A failure here is logged and swallowed — a demo-data problem must never block
a deploy's migrate.
"""

import frappe

MARKER = "verp_production_demo_seed_v1"
COUNT = 20


def after_migrate():
	conf = frappe.conf
	if conf.get("skip_demo_seed"):
		return
	if conf.get("developer_mode") and not conf.get("force_demo_seed"):
		return
	if frappe.db.get_global(MARKER):
		return
	if not frappe.db.count("Company"):
		return

	try:
		from verp_staffing.utils import sample_data_tracking as tracking
		from verp_staffing.utils.seed_test_data import run_production

		run_production(count=COUNT)
		# Sample data exists again, so the "Remove Sample Data" action and the
		# link-to-sample-record guard should be live even if a previous
		# removal had switched them off.
		frappe.db.set_single_value(tracking.SINGLE_DOCTYPE, tracking.REMOVED_FLAG_FIELD, 0)
		frappe.db.set_global(MARKER, "1")
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Production demo seed failed", message=frappe.get_traceback())
