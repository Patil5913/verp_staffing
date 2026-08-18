import frappe

def setup_complete(args=None):
	args = frappe._dict(args or {})

	company = create_company(args)
	create_fiscal_year(args, company)

	# Commit here, before sample data seeding starts. create_sample_data()
	# runs many _safe()-wrapped steps that roll back on failure - and
	# frappe.db.rollback() reverts the WHOLE current transaction, not
	# just the step that failed. Without this commit, a single failure
	# early in seeding (e.g. hitting a DB column that wasn't migrated
	# yet) would silently undo the Company and Fiscal Year created
	# above too, even though they succeeded - which is exactly what
	# caused setup to fail outright with no real error surfaced, and
	# the browser to keep flapping between /app and /setup-wizard
	# afterward (no Company existed for /app's boot check to find).
	# Core setup succeeding must never depend on sample data seeding
	# succeeding.
	frappe.db.commit()

	if args.get("add_sample_data"):
		from verp_staffing.setup.sample_data import create_sample_data

		create_sample_data(company)


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