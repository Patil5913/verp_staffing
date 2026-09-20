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

# Portal access for the demo customers (see portal_access_after_migrate)
PORTAL_MARKER = "verp_production_demo_portal_access_v1"
PORTAL_PASSWORD = "123"


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


def _login_label(i: int) -> str:
	"""0 -> a, 25 -> z, 26 -> aa, 27 -> ab ..."""
	label = ""
	i += 1
	while i:
		i, r = divmod(i - 1, 26)
		label = chr(ord("a") + r) + label
	return label


def grant_sample_customers_portal_access(password: str = PORTAL_PASSWORD) -> list[tuple[str, str]]:
	"""Give every demo customer a portal + chat login: a@vrugle.com, b@vrugle.com, ... and one shared password.

	Only customers the sample-data seeder created (the tracking log) are touched, never a real one.
	Customers whose service already ended are skipped, as are ones that already have access, so it is
	safe to run again. Nothing is emailed. The password is written straight to the password store, so
	the site's password-strength policy is deliberately not applied. Returns [(login, customer)].
	"""
	from frappe.utils.password import update_password

	from verp_staffing.crm.api.customer_chat import CHAT_ROLE, ENDED_STATUSES
	from verp_staffing.utils import sample_data_tracking as tracking

	sample = set(tracking._read_log().get("Customer", []))
	if not sample:
		return []

	customers = frappe.get_all(
		"Customer",
		{"name": ["in", list(sample)], "chat_user": ["is", "not set"]},
		["name", "name1", "lead_details", "overall_status"],
		order_by="creation asc",
	)
	granted, n = [], 0
	for c in customers:
		if c.overall_status in ENDED_STATUSES or not c.lead_details:
			continue
		while True:
			login = f"{_login_label(n)}@vrugle.com"
			n += 1
			if not frappe.db.exists("User", login):
				break
		frappe.db.set_value("Lead Detail Form", c.lead_details, "email", login, update_modified=False)
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": login,
				"first_name": c.name1 or c.name,
				"user_type": "Website User",
				"send_welcome_email": 0,
				"roles": [{"role": CHAT_ROLE}],
			}
		)
		user.flags.ignore_permissions = True
		user.insert()
		update_password(login, password)
		frappe.db.set_value("Customer", c.name, {"chat_user": login, "chat_access": "Active"}, update_modified=False)
		granted.append((login, c.name))
	return granted


def portal_access_after_migrate():
	"""Once per site, after the demo data exists: give the demo customers their portal logins.

	Same guards as the demo seed (never in developer mode without force_demo_seed, never with
	skip_demo_seed). It also runs on sites that were seeded before this existed, because it has
	its own marker. A site without the chat app is left for a later migrate.
	"""
	conf = frappe.conf
	if conf.get("skip_demo_seed"):
		return
	if conf.get("developer_mode") and not conf.get("force_demo_seed"):
		return
	if frappe.db.get_global(PORTAL_MARKER):
		return
	if "vruglechat" not in frappe.get_installed_apps() or not frappe.db.exists("Role", "Chat External"):
		return
	if not frappe.db.get_global(MARKER):
		return  # no demo data on this site (yet)

	try:
		granted = grant_sample_customers_portal_access()
		frappe.db.set_global(PORTAL_MARKER, "1")
		frappe.db.commit()
		if granted:
			frappe.logger().info(f"Portal access granted to {len(granted)} demo customers")
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Demo customer portal access failed", message=frappe.get_traceback())
