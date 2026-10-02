import frappe
from verp_staffing.utils.sample_data_tracking import DEMO_COMPANY_NAME


def setup_complete(args=None):
	args = frappe._dict(args or {})

	company = create_company(args)
	fiscal_year = create_fiscal_year(args, company)

	if args.get("add_sample_data"):
		# This function is one stage among several run by core
		# frappe.desk.page.setup_wizard.setup_wizard.process_setup_
		# stages() inside a SINGLE request/transaction - core commits
		# once, at the very end, only if every stage succeeds. Any
		# uncaught exception here fails that whole request, the "setup
		# complete" flag never gets set, and every subsequent page load
		# bounces back into the wizard - which is exactly what was
		# showing up as the /app <-> /app/setup-wizard <-> 
		# /app/setup-wizard/0 loop.
		#
		# Everything optional (Demo Company + linking it into the
		# Fiscal Year + sample data seeding) is wrapped so it can never
		# take the whole stage - and therefore the whole wizard - down
		# with it.
		#
		# NOTE: deliberately no frappe.db.commit() here anymore (there
		# used to be one), and no retry-on-deadlock wrapper either.
		# A mid-request commit splits one transaction into two+ sharing
		# a connection, which is what exposed the LATER, unrelated
		# update_global_settings core stage to a genuine concurrent-
		# write race (the "(1020, Record has changed since last
		# read...)" error). A retry wrapped only around this function
		# can't protect a failure in a *different* stage anyway - and
		# retrying after a partial commit had already landed would
		# re-run create_company()/create_fiscal_year() against rows
		# that already exist, guaranteeing a second failure. Removed
		# both rather than patched further.
		try:
			from verp_staffing.setup.sample_data import create_sample_data

			# Sample data is never seeded against the org's real
			# Company - it always gets its own standing "Demo Company"
			# instead, so it can be wiped later (remove_sample_data.py)
			# in one shot by company, with zero risk of taking any
			# real record with it.
			demo_company = create_demo_company(args)

			# Sales/Purchase Orders, Invoices, Payment Entries, Journal
			# Entries, Subscriptions etc. below all post against
			# `demo_company` and need a Fiscal Year that covers it -
			# reuse the one just created for the real company (same
			# date range) instead of minting a second Fiscal Year doc,
			# which would collide on name.
			_add_company_to_fiscal_year(fiscal_year, demo_company)

			# While sample data exists, the app should default to
			# showing the Demo Company so the seeded records are
			# actually visible without the user having to switch
			# companies first. remove_sample_data.py repoints this
			# back once sample data is removed.
			frappe.db.set_single_value(
				"ERP Configuration", "default_company", demo_company.name
			)

			create_sample_data(demo_company)
		except Exception:
			frappe.log_error(
				title="Sample Data: seeding failed during setup wizard",
				message=frappe.get_traceback(),
			)
			# Fall through on purpose. Core setup (Company, Fiscal
			# Year, everything else in the stage chain) must complete
			# regardless of whether this optional step did.


def create_company(args):
	company_name = args.get("company_name")
	currency = args.get("currency")
	country = args.get("country")

	abbr = "".join([word[0] for word in company_name.split() if word])[:10].upper()
	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": company_name,
			"abbr": abbr,
			"default_currency": currency,
			"country": country,
		}
	)

	company.insert(ignore_permissions=True)
	frappe.db.set_single_value(
		"ERP Configuration",
		"default_company",
		company.name,
	)
	return company


def create_demo_company(args):
	existing = frappe.db.exists("Company", {"company_name": DEMO_COMPANY_NAME})
	if existing:
		return frappe.get_doc("Company", existing)

	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": DEMO_COMPANY_NAME,
			"abbr": _unique_demo_abbr(),
			"default_currency": args.get("currency"),
			"country": args.get("country"),
		}
	)
	company.insert(ignore_permissions=True)
	return company


def _unique_demo_abbr():
	abbr = "DEMO"
	i = 1
	while frappe.db.exists("Company", {"abbr": abbr}):
		i += 1
		abbr = f"DEMO{i}"
	return abbr


def _add_company_to_fiscal_year(fiscal_year, company):
	if not fiscal_year or not company:
		return
	already_included = any(
		row.company == company.name for row in (fiscal_year.get("included_companies") or [])
	)
	if not already_included:
		fiscal_year.append("included_companies", {"company": company.name})
		fiscal_year.save(ignore_permissions=True)


def create_fiscal_year(args, company):
	start_date = args.get("fy_start_date")
	end_date = args.get("fy_end_date")

	start_year = str(start_date)[:4]
	end_year = str(end_date)[:4]

	fy = frappe.get_doc(
		{
			"doctype": "Fiscal Year",
			"year": f"{start_year}-{end_year}",
			"year_start_date": start_date,
			"year_end_date": end_date,
			"included_companies": [{"company": company.name}],
		}
	)

	fy.insert(ignore_permissions=True)

	return fy