"""Bulk test data for the new frontend.

    bench --site <site> execute verp_staffing.utils.seed_test_data.run
    bench --site <site> execute verp_staffing.utils.seed_test_data.run --kwargs '{"count": 40}'
    bench --site <site> execute verp_staffing.utils.seed_test_data.report

Creates `count` (default 30) records of every doctype the sidebar exposes —
masters first, then CRM, department service records, and the accounting
documents built on them — so lists, kanban, trees and detail pages have
something real to render. Each record is inserted under its own savepoint
(one bad record never costs the rest) and tracked as sample data through the
same ERP Configuration log the setup wizard's sample data uses, so
"Remove Sample Data" can clear it again.

Idempotent: natural-keyed doctypes are get-or-create, and every section only
tops itself up to `count` rather than adding another `count`.

Production
----------
    bench --site <site> execute verp_staffing.utils.seed_test_data.run_production

`run_production` seeds a live site without touching what's already there: it
creates two dedicated demo companies (all accounting documents go into those,
so the real companies' books and reports are unaffected), and every section
only ever reads back records *it* created (the sample-data log), never the
site's real customers, items, employees or orders. Everything is tracked, so
"Remove Sample Data" clears it. Triggered on migrate by
`verp_staffing.utils.seed_production.after_migrate` (see that file for the
guards).
"""

import random
from datetime import date, timedelta

import frappe
from frappe.utils import add_days, getdate, nowdate

from verp_staffing.setup.sample_data import (
	DEPARTMENT_MAP,
	_account_currency,
	_ensure_account_currency,
	_get_company_default_account,
	_safe_tax_row,
	_service_items_table,
)
from verp_staffing.utils import sample_data_tracking as tracking

random.seed(20260918)

FIRST = [
	"Aarav", "Vivaan", "Aditya", "Sai", "Arjun", "Reyansh", "Krishna", "Ishaan", "Rohan", "Kabir", "Ananya", "Diya",
	"Isha", "Meera", "Priya", "Riya", "Saanvi", "Tara", "Zoya", "Nisha", "Liam", "Noah", "Emma", "Olivia", "Ethan",
	"Sophia", "Mason", "Ava", "Lucas", "Mia",
]
LAST = [
	"Sharma", "Patel", "Reddy", "Nair", "Iyer", "Gupta", "Mehta", "Rao", "Singh", "Kumar", "Verma", "Joshi", "Menon",
	"Das", "Bose", "Khan", "Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor", "Clark", "Lewis",
]
COMPANIES = [
	"Acme Corp", "Globex", "Initech", "Umbrella Systems", "Hooli", "Stark Industries", "Wayne Enterprises", "Wonka Labs",
	"Cyberdyne", "Soylent Tech", "Tyrell Data", "Vandelay Software", "Pied Piper", "Massive Dynamic", "Aperture Cloud",
	"Oscorp Digital", "Gringotts Fin", "Nakatomi Trading", "Monarch Systems", "Blue Sun Tech",
]
ROLES = [
	"Software Engineer", "Data Analyst", "QA Engineer", "DevOps Engineer", "Business Analyst", "Java Developer",
	"Python Developer", "Data Engineer", "Cloud Architect", "Scrum Master", "Full Stack Developer", "ML Engineer",
]
SKILLS = ["Python", "Java", "AWS", "React", "SQL", "Kubernetes", "Spark", "Node.js", "Azure", "Snowflake"]

_pending_tracks = []

# Which company the accounting sections post into, whether sections may read
# back only the records the seeder itself created (production), and where the
# posting-date window opens. The defaults are what the dev seeder always did.
_STATE = {"tracked_only": False, "company": "Vrugle", "fy_start": date(2026, 9, 1)}

# Config masters that come from the app's install, not the seeder: sections
# read them even in production.
_SHARED = {"Lead Source", "Sales Stage", "Interview Status", "Type Of Interview"}
# Doctypes whose "how many do we have" is per company in production, so each
# demo company gets its own full set.
_COMPANY_SCOPED = {"Account", "Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice", "Payment Entry", "Journal Entry", "Subscription"}


# ─── plumbing ─────────────────────────────────────────────────────────


def _person():
	return f"{random.choice(FIRST)} {random.choice(LAST)}"


def _flush_tracks():
	"""One read + one write of the sample-data log for a whole batch,
	instead of tracking.track()'s read/write per record."""
	if not _pending_tracks:
		return
	log = tracking._read_log()
	for doctype, name in _pending_tracks:
		names = log.setdefault(doctype, [])
		if name not in names:
			names.append(name)
	tracking._write_log(log)
	_pending_tracks.clear()


def _insert(doc, submit=False):
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	_pending_tracks.append((doc.doctype, doc.name))
	return doc


def _attempt(label, fn, errors):
	"""Run one record's creation under a savepoint; on failure roll back to
	it and remember the message (first few per section) instead of raising."""
	savepoint = f"seed_{frappe.generate_hash(length=8)}"
	frappe.db.savepoint(savepoint)
	try:
		return fn()
	except Exception as exc:
		frappe.db.rollback(save_point=savepoint)
		errors.append(f"{label}: {str(exc).splitlines()[0][:160] if str(exc) else type(exc).__name__}")
		return None


def _tracked(doctype):
	_flush_tracks()
	return tracking._read_log().get(doctype, [])


def _count(doctype, filters=None):
	"""Rows of `doctype` — in production, only the ones the seeder made."""
	if not _STATE["tracked_only"]:
		return frappe.db.count(doctype, filters or {})
	names = _tracked(doctype)
	return frappe.db.count(doctype, {**(filters or {}), "name": ["in", names]}) if names else 0


def _top_up(doctype, target, make, errors, filters=None, max_attempts_factor=3):
	"""Create records until `doctype` (optionally within `filters`) holds
	`target` of them. `make(i)` builds and inserts record i, returning its
	name. Gives up after target*factor attempts so a systematic failure
	can't spin forever."""
	scope = {"company": _STATE["company"]} if _STATE["tracked_only"] and doctype in _COMPANY_SCOPED else {}
	have = _count(doctype, {**scope, **(filters or {})})
	created, attempts = [], 0
	i = _count(doctype)  # numbering stays unique across companies
	while have + len(created) < target and attempts < target * max_attempts_factor:
		attempts += 1
		i += 1
		name = _attempt(f"{doctype} #{i}", lambda i=i: make(i), errors)
		if name:
			created.append(name)
	frappe.db.commit()
	_flush_tracks()
	return created


def _existing(doctype, **filters):
	if _STATE["tracked_only"] and doctype not in _SHARED:
		names = _tracked(doctype)
		if not names:
			return []
		filters["name"] = ["in", names]
	return frappe.get_all(doctype, filters=filters or None, pluck="name", order_by="creation asc")


def _date_in_fy():
	"""A posting date inside the open fiscal year (1 Sep 2026 onwards),
	never in the future."""
	today = getdate(nowdate())
	start = _STATE["fy_start"]
	days = max((today - start).days, 0)
	return str(start + timedelta(days=random.randint(0, days)))


# ─── sections ─────────────────────────────────────────────────────────
# Each returns (doctype, created_names). `ctx` carries what later sections
# need (employees by department, customers, items, ...).


def config(ctx, n, errors):
	if not frappe.db.get_single_value("ERP Configuration", "default_interview_status"):
		frappe.db.set_single_value("ERP Configuration", "default_interview_status", "Scheduled")
	return []


def sample_pdf(ctx, n, errors):
	"""A tiny valid PDF, for E Sign originals and proof-of-work rows."""
	name = frappe.db.get_value("File", {"file_name": "seed-sample.pdf"}, "file_url")
	if not name:
		import fitz  # PyMuPDF — already a dependency of E Sign's PDF rendering

		doc = fitz.open()
		page = doc.new_page(width=612, height=792)
		page.insert_text((72, 96), "Seed agreement - sign below", fontsize=18)
		page.insert_text((72, 200), "Name:", fontsize=12)
		page.insert_text((72, 300), "Signature:", fontsize=12)
		pdf = doc.tobytes()
		file = frappe.get_doc(
			{"doctype": "File", "file_name": "seed-sample.pdf", "content": pdf, "is_private": 0}
		).insert(ignore_permissions=True)
		name = file.file_url
	ctx["pdf"] = name
	return []


def users_and_employees(ctx, n, errors):
	ctx.setdefault("emp", {})
	depts = list(DEPARTMENT_MAP.items())
	# Reuse whoever already exists, then top up to n.
	mine = set(_tracked("Employee")) if _STATE["tracked_only"] else None
	for row in frappe.get_all("Employee Assignment Detail", fields=["parent", "department"]):
		if mine is not None and row.parent not in mine:
			continue  # production: never hand demo records to real staff
		ctx["emp"].setdefault(row.department, []).append(row.parent)
	admin = frappe.db.get_value("Employee", {"user": "Administrator"}, "name")
	ctx["admin_emp"] = admin

	def make(i):
		key, info = depts[(i - 1) % len(depts)]
		email = f"seed.user{i:02d}@example.com"
		if not frappe.db.exists("User", email):
			first, last = random.choice(FIRST), random.choice(LAST)
			user = frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": first, "last_name": last, "send_welcome_email": 0, "enabled": 1}
			)
			if frappe.db.exists("Role", info["role"]):
				user.append("roles", {"role": info["role"]})
			_insert(user)
		user_name = email
		emp = frappe.get_doc(
			{
				"doctype": "Employee",
				"user": user_name,
				"employee_name": frappe.db.get_value("User", user_name, "full_name") or _person(),
				"enabled": 1,
				"employee_assignment_details_table": [{"department": info["department"], "designation": info["role"]}]
				if frappe.db.exists("Role", info["role"])
				else [],
			}
		)
		_insert(emp)
		ctx["emp"].setdefault(info["department"], []).append(emp.name)
		return emp.name

	created = _top_up("Employee", n, make, errors)
	if not any(ctx["emp"].values()) and admin:
		ctx["emp"]["Sales"] = [admin]
	return created


def _emp(ctx, dept):
	pool = ctx["emp"].get(dept) or ctx["emp"].get("Sales") or [ctx.get("admin_emp")]
	return random.choice([p for p in pool if p]) if any(pool) else None


def item_categories(ctx, n, errors):
	names = ["Consulting", "Training", "Recruitment", "Support", "Marketing", "Cloud", "Security", "Data", "Design", "Legal"]

	def make(i):
		base = names[(i - 1) % len(names)]
		doc = frappe.get_doc(
			{
				"doctype": "Item Category",
				"item_category_name": f"Seed {base} {i:02d}",
				"parent_item_category": "ALL",
				"is_group": 0,
			}
		)
		return _insert(doc).name

	return _top_up("Item Category", n, make, errors)


def uoms(ctx, n, errors):
	units = ["Nos", "Hour", "Day", "Week", "Month", "Session", "Seat", "Licence", "Project", "Page"]

	def make(i):
		doc = frappe.get_doc(
			{"doctype": "UOM", "uom_name": f"Seed {units[(i - 1) % len(units)]} {i:02d}", "enabled": 1, "must_be_whole_number": i % 2}
		)
		return _insert(doc).name

	return _top_up("UOM", n, make, errors)


def items(ctx, n, errors):
	cats = _existing("Item Category", is_group=0) or ["ALL"]
	uoms_ = _existing("UOM") or [None]

	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_name": f"Seed Service {i:02d} - {random.choice(SKILLS)}",
				"item_category": random.choice(cats),
				"stock_uom": random.choice(uoms_),
				"is_service": 1,
			}
		)
		return _insert(doc).name

	return _top_up("Item", n, make, errors)


def supplier_groups(ctx, n, errors):
	def make(i):
		return _insert(frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": f"Seed Supplier Group {i:02d}"})).name

	return _top_up("Supplier Group", n, make, errors)


def suppliers(ctx, n, errors):
	groups = _existing("Supplier Group")

	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": f"Seed Supplier {i:02d} {random.choice(COMPANIES)}",
				"supplier_type": random.choice(["Company", "Individual"]),
				"supplier_group": random.choice(groups) if groups else None,
			}
		)
		return _insert(doc).name

	return _top_up("Supplier", n, make, errors)


def banks(ctx, n, errors):
	def make(i):
		return _insert(frappe.get_doc({"doctype": "Bank", "bank_name": f"Seed Bank {i:02d}", "swift_number": f"SEED{i:04d}XX"})).name

	return _top_up("Bank", n, make, errors)


def bank_account_types(ctx, n, errors):
	def make(i):
		return _insert(frappe.get_doc({"doctype": "Bank Account Type", "account_type": f"Seed Type {i:02d}"})).name

	return _top_up("Bank Account Type", 6, make, errors)


def bank_accounts(ctx, n, errors):
	bank_list = _existing("Bank")
	types = _existing("Bank Account Type")
	asset_group = frappe.db.get_value("Account", {"company": _STATE["company"], "is_group": 1, "root_type": "Asset"}, "name")

	def ledger(i):
		doc = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": f"Seed Bank Ledger {i:02d}",
				"company": _STATE["company"],
				"parent_account": asset_group,
				"is_group": 0,
				"account_type": "Bank",
				"root_type": "Asset",
				"report_type": "Balance Sheet",
				"account_currency": "INR",
			}
		)
		return _insert(doc).name

	def make(i):
		company_account = i % 3 == 0 and asset_group
		doc = frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": f"Seed Account {i:02d}",
				"bank": random.choice(bank_list),
				"account_type": random.choice(types) if types else None,
				"bank_account_no": f"{random.randint(10**9, 10**10 - 1)}",
				**(
					{"is_company_account": 1, "company": _STATE["company"], "account": ledger(i), "is_default": int(i == 3)}
					if company_account
					else {"party_type": "Supplier", "party": random.choice(_existing("Supplier") or [None])}
				),
			}
		)
		return _insert(doc).name

	return _top_up("Bank Account", n, make, errors)


def modes_of_payment(ctx, n, errors):
	kinds = ["Cash", "Bank", "General", "Phone"]

	def make(i):
		return _insert(
			frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": f"Seed Mode {i:02d}", "enabled": 1, "type": kinds[i % 4]})
		).name

	return _top_up("Mode of Payment", n, make, errors)


def tax_categories(ctx, n, errors):
	def make(i):
		return _insert(frappe.get_doc({"doctype": "Tax Category", "title": f"Seed Tax Category {i:02d}"})).name

	return _top_up("Tax Category", n, make, errors)


def fiscal_years(ctx, n, errors):
	def make(i):
		year = 2025 - i  # 2024, 2023, ... — clear of the open 2026-27 year
		doc = frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": f"{year}",
				"year_start_date": f"{year}-01-01",
				"year_end_date": f"{year}-12-31",
				# A company can sit in only one *active* year, so the history
				# is disabled (which also exercises the locked-year UI).
				"disabled": 1,
				"included_companies": [{"company": "Vrugle"}],
			}
		)
		return _insert(doc).name

	return _top_up("Fiscal Year", n, make, errors)


def companies(ctx, n, errors):
	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": f"Seed Company {i:02d}",
				"abbr": f"S{i:02d}",
				"default_currency": "INR",
				"country": "India",
			}
		)
		return _insert(doc).name

	# Companies each build a chart of accounts — keep the top-up modest.
	return _top_up("Company", min(n, 22), make, errors)


def accounts(ctx, n, errors):
	company = _STATE["company"]
	parent = frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Expense"}, "name")
	income_parent = frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Income"}, "name")
	topics = ["Travel", "Software", "Rent", "Utilities", "Training", "Legal", "Recruitment", "Insurance", "Courier", "Meals"]

	def make(i):
		expense = i % 4 != 0
		doc = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": f"Seed {topics[i % len(topics)]} {i:02d}",
				"company": company,
				"parent_account": parent if expense else income_parent,
				"is_group": 0,
				"account_type": "Expense Account" if expense else "Income Account",
				"root_type": "Expense" if expense else "Income",
				"report_type": "Profit and Loss",
				"account_currency": "INR",
			}
		)
		return _insert(doc).name

	if not parent:
		errors.append(f"Account: no expense group found on {company}")
		return []
	# Dev: top up to n *seed* accounts on top of the ~52 a chart already has.
	# Production counts only the seeder's own accounts, so the target is n.
	return _top_up("Account", n if _STATE["tracked_only"] else 52 + n, make, errors)


# ─── CRM / services ───────────────────────────────────────────────────


def customers(ctx, n, errors):
	leads = _existing("Lead")

	def make(i):
		from_lead = i % 3 == 0 and leads
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"name1": f"{_person()} {i:02d}",
				"customer_owner": _emp(ctx, "Sales"),
				**({"customer_from": "Lead", "party_name": random.choice(leads)} if from_lead else {}),
			}
		)
		return _insert(doc).name

	created = _top_up("Customer", n, make, errors)
	ctx["customers"] = _existing("Customer")
	return created


def opportunities(ctx, n, errors):
	leads = _existing("Lead")
	sources = _existing("Lead Source")
	stages = _existing("Sales Stage")

	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Opportunity",
				"name1": f"{_person()} — opportunity {i:02d}",
				"status": random.choice(["Open", "Replied", "Lost"]) if False else None,
				"source": random.choice(sources) if sources else None,
				"opportunity_owner": _emp(ctx, "Sales"),
				"sales_stage": random.choice(stages) if stages else None,
				"expected_closing_date": add_days(nowdate(), random.randint(10, 90)),
				"probability_": random.choice([10, 25, 50, 75, 90]),
				"currency": "INR",
				"opportunity_amount": random.choice([50000, 75000, 120000, 200000]),
				"opportunity_from_lead": random.choice(leads) if leads else None,
			}
		)
		return _insert(doc).name

	return _top_up("Opportunity", n, make, errors)


def call_details(ctx, n, errors):
	"""Logged calls on opportunities — what the Call Details report reads.
	Tops every opportunity's call log up to a few rows over the last weeks."""
	done = 0
	for name in _existing("Opportunity"):
		if frappe.db.count("Call Details", {"parent": name}):
			continue

		def go(name=name):
			doc = frappe.get_doc("Opportunity", name)
			for k in range(random.randint(1, 4)):
				doc.append(
					"call_details",
					{"date": add_days(nowdate(), -random.randint(0, 25)), "duration": random.choice([180, 420, 600, 900, 1500, 2700])},
				)
			doc.save(ignore_permissions=True)
			return name

		if _attempt(f"Call Details {name}", go, errors):
			done += 1
	frappe.db.commit()
	return [f"{done} opportunities"]


def revenue_setup(ctx, n, errors):
	"""Sales targets + attributed revenue — what Revenue Of Employee reads:
	Sales-department employees get a target, and existing Sales Orders are
	handed round-robin to them (revenue is summed per order owner, from each
	order's payment terms for the chosen company)."""
	sales = ctx["emp"].get("Sales") or []
	users = []
	for i, emp in enumerate(sales):
		user = frappe.db.get_value("Employee", emp, "user")
		if not user or user == "Administrator":
			continue
		users.append(user)
		frappe.db.set_value(
			"Employee",
			emp,
			{
				"target": random.choice([20000, 50000, 90000, 150000]),
				"target_based_on": random.choice(["Monthly", "Weekly", "Daily"]),
				"start_date": add_days(nowdate(), -20),
			},
			update_modified=False,
		)
	if not users:
		errors.append("no Sales employees with a user to attribute orders to")
		return []
	# Only submitted orders count towards revenue; submit most of the drafts
	# (a few stay draft so the list shows both).
	for so in _existing("Sales Order", docstatus=0)[:-5]:
		_attempt(f"Submit {so}", lambda so=so: frappe.get_doc("Sales Order", so).submit(), errors)
	# The report caches its Sales-employee list for an hour — drop it so the
	# new targets show up straight away.
	frappe.cache().delete_value("sales_emp_details::revenue_of_employee")
	moved = 0
	for i, so in enumerate(_existing("Sales Order", docstatus=1)):
		frappe.db.set_value("Sales Order", so, "owner", users[i % len(users)], update_modified=False)
		so_company = frappe.db.get_value("Sales Order", so, "company")
		for term in frappe.get_all("Customer Payment Terms", filters={"parent": so}, pluck="name"):
			frappe.db.set_value("Customer Payment Terms", term, {"company": so_company, "currency": "INR"}, update_modified=False)
		moved += 1
	frappe.db.commit()
	return [f"{moved} orders"]


def marketing(ctx, n, errors):
	custs = list(ctx["customers"])
	statuses = ["Pending", "Started", "Completed"]
	used = set(frappe.get_all("Marketing", pluck="customer"))
	free = [c for c in custs if c not in used]

	def make(i):
		customer = free.pop() if free else random.choice(custs)
		rows = [
			{
				"date": str(date.today() - timedelta(days=d)),
				"small_application": random.randint(2, 20),
				"large_application": random.randint(0, 8),
			}
			for d in range(random.randint(1, 6))
		]
		for r in rows:
			r["total_application"] = r["small_application"] + r["large_application"]
		doc = frappe.get_doc(
			{
				"doctype": "Marketing",
				"customer": customer,
				"assign_to": _emp(ctx, "Marketing"),
				"status": statuses[i % 3],
				"target": random.choice([10, 15, 20, 30]),
				"target_based_on": random.choice(["Daily", "Weekly", "Monthly"]),
				"start_date": str(date.today() - timedelta(days=random.randint(1, 20))),
				"job_application_count": rows,
			}
		)
		return _insert(doc).name

	created = _top_up("Marketing", n, make, errors)
	ctx["marketing"] = _existing("Marketing")
	return created


def interviews(ctx, n, errors):
	statuses = _existing("Interview Status") or ["Scheduled"]
	types = _existing("Type Of Interview")
	mk = list(ctx["marketing"])
	final = ["Completed", "Cancelled", "Rescheduled", "Get The Offer", "Rejected"]

	def make(i):
		rounds = []
		for r in range(1, random.randint(1, 4) + 1):
			last = r == 1 or random.random() < 0.3
			status = random.choice(statuses) if last else "Completed"
			row = {
				"round": str(r),
				"date_of_interview": add_days(nowdate(), random.randint(-10, 14)),
				"type_of_interview": random.choice(types),
				"from_time": f"{random.randint(9, 16):02d}:00:00",
				"to_time": f"{random.randint(17, 19):02d}:00:00",
				"follow_up": 0,
				"status": status,
			}
			if status in ("Cancelled", "Rescheduled"):
				row.update({"cancelled_by": random.choice(["Company", "Candidate"]), "reason_of_cancel": "Scheduling conflict"})
			rounds.append(row)
		doc = frappe.get_doc(
			{
				"doctype": "Interview",
				"marketing_link": random.choice(mk),
				"company": f"{random.choice(COMPANIES)}",
				"role": random.choice(ROLES),
				"status": rounds[-1]["status"],
				"interview_rounds_table": rounds,
			}
		)
		return _insert(doc).name

	if not types or not mk:
		errors.append("Interview: needs Type Of Interview + Marketing records")
		return []
	return _top_up("Interview", max(n, 40), make, errors)


def _proof(ctx, count=2):
	return [
		{"document": ctx["pdf"], "document_title": f"Proof {k + 1}", "description": "Seed proof of work"}
		for k in range(count)
	]


SERVICE_ITEMS = ["Marketing", "Cover Letter", "Resume", "Interview Support", "Training", "JDC", "RUC"]


def marketing_other_services(ctx, n, errors):
	# Only the app's real service items resolve to a department (via each
	# customer's stage config), so those are the ones to draw from.
	items_ = [i for i in SERVICE_ITEMS if frappe.db.exists("Item", i)]

	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Marketing Other Services",
				"customer": random.choice(ctx["customers"]),
				"service": random.choice(items_),
				"assign_to": _emp(ctx, "Marketing"),
				"status": random.choice(["Pending", "Pending", "Request for Update"]),
				"proof_of_work": _proof(ctx, random.randint(0, 2)),
			}
		)
		return _insert(doc).name

	return _top_up("Marketing Other Services", n, make, errors)


def other_services(ctx, n, errors):
	items_ = [i for i in SERVICE_ITEMS if frappe.db.exists("Item", i)]
	depts = [d for d in ("Resume", "Technical", "Marketing", "HR") if frappe.db.exists("Department", d)]

	def make(i):
		dept = random.choice(depts)
		doc = frappe.get_doc(
			{
				"doctype": "Other Services",
				"customer": random.choice(ctx["customers"]),
				"department": dept,
				"service": random.choice(items_),
				"assign_to": _emp(ctx, dept),
				"status": random.choice(["Pending", "Pending", "Request for Update"]),
				"proof_of_work": _proof(ctx, random.randint(0, 2)),
			}
		)
		return _insert(doc).name

	return _top_up("Other Services", n, make, errors)


def _unused_customers(ctx, doctype):
	used = set(frappe.get_all(doctype, pluck="customer"))
	return [c for c in ctx["customers"] if c not in used]


def cr(ctx, n, errors):
	free = _unused_customers(ctx, "CR")
	statuses = ["Dispute Pending", "Dispute Pending", "Dispute Resolved", "Refund"]
	depts = [d for d in ("Marketing", "Sales", "Resume", "Technical") if frappe.db.exists("Department", d)]

	def make(i):
		status = statuses[i % len(statuses)]
		row = {
			"reason_for_forwarding": random.choice(["Payment dispute", "Service not delivered", "Wrong plan billed", "Candidate unhappy"]),
			"forwarded_by": "Administrator",
			"forwarded_from_department": random.choice(depts),
			"status": "Dispute Pending",
			"forwarded_on": add_days(nowdate(), -random.randint(1, 20)) + " 10:00:00",
			"assign_to": _emp(ctx, "CR"),
		}
		if status != "Dispute Pending":
			row.update({"status": status, "remarks": "Settled with the customer", "resolve_refund_on": nowdate() + " 12:00:00", "action_by": "Administrator"})
		doc = frappe.get_doc(
			{"doctype": "CR", "customer": free.pop() if free else random.choice(ctx["customers"]), "assign_to": row["assign_to"], "cr_history": [row]}
		)
		return _insert(doc).name

	return _top_up("CR", n, make, errors)


def _us_phone():
	return f"+1{random.choice([212, 415, 646, 202, 312, 617, 713, 305])}{random.randint(2, 9)}{random.randint(10**5, 10**6 - 1)}"


def onboardings(ctx, n, errors):
	free = _unused_customers(ctx, "Onboardings")
	statuses = ["Active", "Active", "Completed", "Returned"]

	def make(i):
		status = statuses[i % len(statuses)]
		hist = {
			"company": random.choice(COMPANIES),
			"role": random.choice(ROLES),
			"assign_to": _emp(ctx, "Onboarding"),
			"forwarded_by": "Administrator",
			"forwarded_from": random.choice(["Marketing", "Technical"]),
			"forwarded_on": add_days(nowdate(), -random.randint(1, 20)) + " 09:30:00",
			"status": status,
		}
		if status != "Active":
			hist.update({"action_on": nowdate() + " 15:00:00", "action_by": "Administrator"})
		doc = frappe.get_doc(
			{
				"doctype": "Onboardings",
				"customer": free.pop() if free else random.choice(ctx["customers"]),
				"assign_to": hist["assign_to"],
				"contact_references": [
					{
						"name1": _person(),
						"email": f"contact{i}{k}@example.com",
						"designation": random.choice(["Recruiter", "Hiring Manager", "HR Lead"]),
						"phone_number": _us_phone(),
						"company": hist["company"],
					}
					for k in range(random.randint(1, 3))
				],
				"documents": _proof(ctx, 1),
				"onboarding_history": [hist],
			}
		)
		return _insert(doc).name

	return _top_up("Onboardings", n, make, errors)


# ─── accounting ───────────────────────────────────────────────────────


def _company(name=None):
	return frappe.get_doc("Company", name or _STATE["company"])


def _tax_rows(company, label):
	return _safe_tax_row(company, label, "seed")


def sales_orders(ctx, n, errors):
	company = _company()
	item_names = _existing("Item")
	taxes = _tax_rows(company, "Output GST")

	def make(i):
		chosen = random.sample(item_names, k=random.randint(1, 3))
		rows = _service_items_table(chosen, company)
		total = sum(r["amount"] for r in rows)
		terms = [
			{"payment_condition": "Not Applied", "amount": round(total * 0.5, 2), "description": "Advance"},
			{"payment_condition": "Not Applied", "amount": round(total * 0.5, 2), "description": "On completion"},
		]
		doc = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": random.choice(ctx["customers"]),
				"company": company.name,
				"posting_date": _date_in_fy(),
				"currency": "INR",
				"items": rows,
				"taxes": taxes,
				"payment_terms": terms,
			}
		)
		return _insert(doc).name

	created = _top_up("Sales Order", n, make, errors)
	ctx["sales_orders"] = _existing("Sales Order", company=company.name)
	return created


def _invoice_common(company):
	return _service_items_table, company


def sales_invoices(ctx, n, errors):
	company = _company()
	item_names = _existing("Item")
	debit_to = _get_company_default_account(company, "default_receivable_account", "Receivable")
	_ensure_account_currency(debit_to, company)
	taxes = _tax_rows(company, "Output GST")

	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": random.choice(ctx["customers"]),
				"company": company.name,
				"currency": "INR",
				"debit_to": debit_to,
				"posting_date": _date_in_fy(),
				"items": _service_items_table(random.sample(item_names, k=random.randint(1, 3)), company),
				"taxes": taxes,
			}
		)
		return _insert(doc, submit=True).name

	created = _top_up("Sales Invoice", n, make, errors)
	ctx["sales_invoices"] = _existing("Sales Invoice", docstatus=1, company=company.name)
	return created


def purchase_orders(ctx, n, errors):
	company = _company()
	item_names = _existing("Item")
	sup = _existing("Supplier")
	taxes = _tax_rows(company, "Input GST")

	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": random.choice(sup),
				"company": company.name,
				"currency": "INR",
				"posting_date": _date_in_fy(),
				"schedule_date": add_days(nowdate(), random.randint(3, 30)),
				"items": _service_items_table(random.sample(item_names, k=random.randint(1, 3)), company, doc_type="Purchase"),
				"taxes": taxes,
			}
		)
		return _insert(doc, submit=True).name

	return _top_up("Purchase Order", n, make, errors)


def purchase_invoices(ctx, n, errors):
	company = _company()
	item_names = _existing("Item")
	sup = _existing("Supplier")
	credit_to = _get_company_default_account(company, "default_payable_account", "Payable")
	_ensure_account_currency(credit_to, company)
	taxes = _tax_rows(company, "Input GST")

	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": random.choice(sup),
				"company": company.name,
				"currency": "INR",
				"credit_to": credit_to,
				"posting_date": _date_in_fy(),
				"bill_no": f"SEED-BILL-{i:04d}",
				"bill_date": _date_in_fy(),
				"items": _service_items_table(random.sample(item_names, k=random.randint(1, 3)), company, doc_type="Purchase"),
				"taxes": taxes,
			}
		)
		return _insert(doc, submit=True).name

	created = _top_up("Purchase Invoice", n, make, errors)
	ctx["purchase_invoices"] = _existing("Purchase Invoice", docstatus=1, company=company.name)
	return created


def payment_entries(ctx, n, errors):
	company = _company()
	receivable = _get_company_default_account(company, "default_receivable_account", "Receivable")
	payable = _get_company_default_account(company, "default_payable_account", "Payable")
	cash = _get_company_default_account(company, "default_cash_account", "Cash") or "Cash - V"
	modes = _existing("Mode of Payment")

	already = set(frappe.get_all("Payment Entry Reference", pluck="reference_name"))
	sales = [s for s in ctx.get("sales_invoices", []) if s not in already]
	purchases = [p for p in ctx.get("purchase_invoices", []) if p not in already]
	work = [("Sales Invoice", s, "Receive") for s in sales] + [("Purchase Invoice", p, "Pay") for p in purchases]
	random.shuffle(work)

	def make(i):
		doctype, ref, kind = work.pop()
		party_type = "Customer" if doctype == "Sales Invoice" else "Supplier"
		party = frappe.db.get_value(doctype, ref, "customer" if party_type == "Customer" else "supplier")
		total = frappe.db.get_value(doctype, ref, "outstanding_amount") or frappe.db.get_value(doctype, ref, "grand_total")
		paid_from, paid_to = (receivable, cash) if kind == "Receive" else (cash, payable)
		doc = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": kind,
				"company": company.name,
				"posting_date": _date_in_fy(),
				"currency": "INR",
				"mode_of_payment": random.choice(modes) if modes else None,
				"party_type": party_type,
				"party": party,
				"paid_from": paid_from,
				"paid_to": paid_to,
				"paid_from_account_currency": _account_currency(paid_from, company),
				"paid_to_account_currency": _account_currency(paid_to, company),
				"paid_amount": total,
				"reference_no": f"SEED-REF-{i:04d}",
				"reference_date": _date_in_fy(),
				"references": [
					{"reference_doctype": doctype, "reference_name": ref, "total_amount": total, "outstanding_amount": total, "allocated_amount": total}
				],
			}
		)
		return _insert(doc, submit=True).name

	# The direct entries stop at 3/4 of the target — the rest come from the
	# real "Mark as Paid" flow below so the verification queue has data.
	direct_target = int(n * 0.7)
	created = _top_up("Payment Entry", direct_target, make, errors) if work else []
	return created


def pending_verification_entries(ctx, n, errors):
	"""Payment Entries raised the way users raise them — through a Sales
	Order's payment term — so they land in the Payment Verification queue
	(pending / rejected / verified)."""
	from verp_staffing.accounts.doctype.sales_order.sales_order import (
		create_payment_entry_from_term,
		reject_payment_entry,
		verify_payment_entry,
	)

	made = []
	orders = [so for so in ctx.get("sales_orders", []) if not frappe.db.exists("Customer Payment Terms", {"parent": so, "payment_entry": ["is", "set"]})]
	target = max(12, n // 2)

	for idx, so in enumerate(orders):
		if len(made) >= target:
			break
		term = frappe.db.get_value("Customer Payment Terms", {"parent": so, "idx": 1}, "name")
		if not term:
			continue

		def go(so=so, term=term, idx=idx):
			res = create_payment_entry_from_term(
				sales_order=so,
				payment_term_row=term,
				reference_no=f"SEED-VER-{idx:04d}",
				reference_date=nowdate(),
				remarks="Seed payment awaiting verification",
				payer_account_name=_person(),
				company=_STATE["company"],
			)
			pe = res["payment_entry"]
			# a third stay pending, a third get verified, a third rejected
			if idx % 3 == 1:
				# Verifying submits the entry, which needs the accounts the
				# accountant fills in on the Payment Entry first.
				company = _company()
				receivable = _get_company_default_account(company, "default_receivable_account", "Receivable")
				cash = _get_company_default_account(company, "default_cash_account", "Cash") or "Cash - V"
				frappe.db.set_value(
					"Payment Entry",
					pe,
					{
						"paid_from": receivable,
						"paid_to": cash,
						"paid_from_account_currency": _account_currency(receivable, company),
						"paid_to_account_currency": _account_currency(cash, company),
					},
				)
				verify_payment_entry(pe)
			elif idx % 3 == 2:
				reject_payment_entry(pe, "Amount does not match the bank statement")
			_pending_tracks.append(("Payment Entry", pe))
			return pe

		pe = _attempt(f"Verification flow {so}", go, errors)
		if pe:
			made.append(pe)
	frappe.db.commit()
	_flush_tracks()
	return made


def journal_entries(ctx, n, errors):
	company = _company()
	cash = _get_company_default_account(company, "default_cash_account", "Cash") or "Cash - V"
	expense_accounts = frappe.get_all("Account", filters={"company": company.name, "is_group": 0, "root_type": "Expense", "account_type": "Expense Account"}, pluck="name")
	income = _get_company_default_account(company, "default_income_account", "Income Account")
	for account in expense_accounts + [cash, income]:
		_ensure_account_currency(account, company)

	def line(account, debit, credit):
		return {
			"account": account,
			"account_currency": _account_currency(account, company),
			"exchange_rate": 1,
			"debit_in_account_currency": debit,
			"debit": debit,
			"credit_in_account_currency": credit,
			"credit": credit,
		}

	def make(i):
		amount = random.choice([1500, 2500, 4200, 9000, 18000, 32000])
		if i % 3 == 0:
			lines = [line(cash, amount, 0), line(income, 0, amount)]
		else:
			lines = [line(random.choice(expense_accounts), amount, 0), line(cash, 0, amount)]
		doc = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"company": company.name,
				"posting_date": _date_in_fy(),
				"user_remark": f"Seed entry {i:02d}",
				"accounts": lines,
			}
		)
		return _insert(doc, submit=True).name

	return _top_up("Journal Entry", n, make, errors)


def subscription_plans(ctx, n, errors):
	item_names = _existing("Item")
	intervals = ["Month", "Month", "Year", "Week"]

	def make(i):
		doc = frappe.get_doc(
			{
				"doctype": "Subscription Plan",
				"plan_name": f"Seed Plan {i:02d}",
				"item": random.choice(item_names),
				"rate": random.choice([2500, 5000, 7500, 12000]),
				"currency": "INR",
				"billing_interval": intervals[i % len(intervals)],
				"billing_interval_count": 1,
			}
		)
		return _insert(doc, submit=True).name

	return _top_up("Subscription Plan", max(20, n // 2 + 5), make, errors)


def subscriptions(ctx, n, errors):
	plans = _existing("Subscription Plan", docstatus=1)
	sup = _existing("Supplier")

	def make(i):
		sales = i % 4 != 0
		doc = frappe.get_doc(
			{
				"doctype": "Subscription",
				"subscription_type": "Sales" if sales else "Purchase",
				"party_type": "Customer" if sales else "Supplier",
				"party": random.choice(ctx["customers"]) if sales else random.choice(sup),
				"company": _STATE["company"],
				"plan": random.choice(plans),
				"qty": random.randint(1, 3),
				"start_date": _date_in_fy(),
			}
		)
		return _insert(doc, submit=True).name

	return _top_up("Subscription", max(20, n // 2 + 5), make, errors)


def e_signs(ctx, n, errors):
	statuses = ["Draft", "Draft", "Sent", "Fully Signed"]

	def make(i):
		emails = [f"signer{i}{k}@example.com" for k in range(random.randint(1, 3))]
		rows = []
		for k, email in enumerate(emails):
			rows.append(
				{
					"page_number": 1, "x_percent": 12, "y_percent": 30 + 12 * k, "width_percent": 28, "height_percent": 6,
					"signer_email": email, "field_type": "signature", "field_label": f"Signature {k + 1}", "font_size": "12",
				}
			)
			rows.append(
				{
					"page_number": 1, "x_percent": 45, "y_percent": 30 + 12 * k, "width_percent": 24, "height_percent": 4,
					"signer_email": email, "field_type": "date", "field_label": "Date", "font_size": "12",
				}
			)
		doc = frappe.get_doc(
			{
				"doctype": "E Sign",
				"title": f"Seed Agreement {i:02d} — {random.choice(COMPANIES)}",
				"original_pdf": ctx["pdf"],
				"signature_fields": rows,
			}
		)
		_insert(doc)
		# Status is server-owned (read-only); set it directly for the demo mix.
		frappe.db.set_value("E Sign", doc.name, "status", statuses[i % len(statuses)], update_modified=False)
		return doc.name

	return _top_up("E Sign", n, make, errors)


def technical(ctx, n, errors):
	"""Simple service records per technical doctype (customer + assignee +
	status) — enough to fill their lists."""
	created = {}
	plan = [
		("Resume", "Resume", ["Pending", "Completed"]),
		("Cover Letter", "Resume", ["Pending", "Completed"]),
		("Training", "Technical", ["Pending", "Started", "Completed"]),
		("RUC", "Technical", ["Pending", "Started", "Completed"]),
	]
	for doctype, dept, statuses in plan:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		status_field = meta.get_field("status")
		opts = [o for o in (status_field.options or "").split("\n") if o] if status_field else []
		valid = [s for s in statuses if s in opts] or opts[:1] or [None]
		used = set(frappe.get_all(doctype, pluck="customer"))
		free = [c for c in ctx["customers"] if c not in used]

		def make(i, doctype=doctype, dept=dept, valid=valid, free=free):
			values = {"doctype": doctype, "customer": free.pop() if free else random.choice(ctx["customers"]), "assign_to": _emp(ctx, dept)}
			if valid[0]:
				values["status"] = random.choice(valid)
			return _insert(frappe.get_doc(values)).name

		created[doctype] = _top_up(doctype, n, make, errors)
	return created



# ─── CRM depth: leads, shape, activity ───────────────────────────────


def leads(ctx, n, errors):
	def make(i):
		doc = frappe.get_doc({"doctype": "Lead", "name1": f"{_person()} {i:02d}", "lead_owner": _emp(ctx, "Lead")})
		return _insert(doc).name

	return _top_up("Lead", n, make, errors)


def _backdate(doctype, names, days=75):
	"""Spread records over the last `days` days — creation is what the
	dashboards and trend reports bucket by, and a seeder run stamps every
	record with the same minute."""
	for name in names:
		when = f"{add_days(nowdate(), -random.randint(0, days))} {random.randint(8, 18):02d}:{random.randint(0, 59):02d}:00"
		frappe.db.set_value(doctype, name, "creation", when, update_modified=False)


def crm_shaping(ctx, n, errors):
	"""Give the seeder's own CRM and service records a realistic spread: dates
	across ~75 days, a status / source / visa mix on leads and opportunities,
	and finished work on the service queues. Only ever touches records the
	seeder created."""
	sources = _existing("Lead Source")
	visa_field = frappe.get_meta("Lead Detail Form").get_field("current_visa_status")
	visas = [o for o in (visa_field.options or "").split("\n") if o] if visa_field else []
	lead_status = ["Open"] * 3 + ["Lead"] * 3 + ["Interested"] * 2 + ["Opportunity"] * 2 + ["Won"] * 2 + ["Lost"]
	opp_status = ["Open"] * 4 + ["Quotation"] * 2 + ["Replied"] * 2 + ["Converted"] * 2 + ["Lost"]

	lead_names = _tracked("Lead")
	for name in lead_names:
		values = {"status": random.choice(lead_status)}
		if sources:
			values["source"] = random.choice(sources)
		frappe.db.set_value("Lead", name, values, update_modified=False)
		detail = frappe.db.get_value("Lead", name, "lead_details")
		if detail and visas:
			frappe.db.set_value("Lead Detail Form", detail, "current_visa_status", random.choice(visas), update_modified=False)
	_backdate("Lead", lead_names)

	opp_names = _tracked("Opportunity")
	for name in opp_names:
		values = {"status": random.choice(opp_status)}
		if sources:
			values["source"] = random.choice(sources)
		frappe.db.set_value("Opportunity", name, values, update_modified=False)
	_backdate("Opportunity", opp_names)
	_backdate("Customer", _tracked("Customer"))

	# Service queues: a spread of dates, and about a third finished.
	for doctype in ("Marketing Other Services", "Other Services", "Resume", "Cover Letter", "Training", "RUC", "CR", "Onboardings"):
		names = _tracked(doctype)
		_backdate(doctype, names)
		if doctype in ("Marketing Other Services", "Other Services", "Resume", "Cover Letter", "Training", "RUC"):
			for name in names:
				if random.random() < 0.35:
					frappe.db.set_value(doctype, name, "status", "Completed", update_modified=False)
					if doctype == "Other Services":
						sent = f"{add_days(nowdate(), -random.randint(3, 40))} 10:00:00"
						done = frappe.utils.add_to_date(sent, hours=random.choice([4, 9, 26, 50, 75]), as_string=True)
						frappe.db.set_value("Other Services", name, {"forwarded_on": sent, "completed_on": done}, update_modified=False)
	frappe.db.commit()
	return [f"{len(lead_names)} leads", f"{len(opp_names)} opportunities"]


def crm_activity(ctx, n, errors):
	"""Follow-up tasks and calendar events against the seeded leads and
	opportunities — some done, some due, some overdue."""
	users = sorted({frappe.db.get_value("Employee", e, "user") for pool in ctx.get("emp", {}).values() for e in pool} - {None})
	targets = [("Opportunity", o) for o in _existing("Opportunity")] + [("Lead", l) for l in _existing("Lead")]
	if not users or not targets:
		errors.append("CRM activity: needs seeded employees with users, and leads/opportunities")
		return []

	def when(days):
		return f"{add_days(nowdate(), days)} {random.choice(['09', '11', '14', '16'])}:00:00"

	def task(i):
		ref, name = random.choice(targets)
		done = random.random() < 0.4
		doc = frappe.get_doc(
			{
				"doctype": "CRM Task",
				"description": random.choice(["Send updated profile", "Follow up on interview feedback", "Confirm availability", "Share rate card", "Collect documents", "Check payment status"]),
				"date": when(random.randint(-20, -1) if done else random.randint(-6, 10)),
				"assigned_to": random.choice(users),
				"reference_doctype": ref,
				"related_to": name,
				"is_completed": int(done),
			}
		)
		return _insert(doc).name

	def event(i):
		ref, name = random.choice(targets)
		category = random.choice(["Event", "Meeting", "Call", "Follow Up", "Other"])
		doc = frappe.get_doc(
			{
				"doctype": "CRM Event",
				"category": category,
				"date": when(random.randint(-10, 14)),
				"assigned_to": random.choice(users),
				"summary": f"{category}: {_person()}",
				"reference_doctype": ref,
				"related_to": name,
			}
		)
		return _insert(doc).name

	return _top_up("CRM Task", n * 2, task, errors) + _top_up("CRM Event", n, event, errors)


SECTIONS = [
	("ERP Configuration", config),
	("Sample PDF", sample_pdf),
	("Employee", users_and_employees),
	("Item Category", item_categories),
	("UOM", uoms),
	("Item", items),
	("Supplier Group", supplier_groups),
	("Supplier", suppliers),
	("Bank", banks),
	("Bank Account Type", bank_account_types),
	("Bank Account", bank_accounts),
	("Mode of Payment", modes_of_payment),
	("Tax Category", tax_categories),
	("Fiscal Year", fiscal_years),
	("Company", companies),
	("Account", accounts),
	("Lead", leads),
	("Customer", customers),
	("Opportunity", opportunities),
	("Marketing", marketing),
	("Interview", interviews),
	("Marketing Other Services", marketing_other_services),
	("Other Services", other_services),
	("CR", cr),
	("Onboardings", onboardings),
	("Technical services", technical),
	("Sales Order", sales_orders),
	("Sales Invoice", sales_invoices),
	("Purchase Order", purchase_orders),
	("Purchase Invoice", purchase_invoices),
	("Payment Entry", payment_entries),
	("Payment verification queue", pending_verification_entries),
	("Journal Entry", journal_entries),
	("Call Details (opportunities)", call_details),
	("Revenue targets", revenue_setup),
	("CRM shaping", crm_shaping),
	("CRM activity", crm_activity),
	("Subscription Plan", subscription_plans),
	("Subscription", subscriptions),
	("E Sign", e_signs),
]

DOCTYPES_REPORTED = [
	"Lead", "Opportunity", "Customer", "Employee", "Marketing", "Interview", "Marketing Other Services", "Other Services",
	"CR", "Onboardings", "Resume", "Cover Letter", "Training", "RUC", "Company", "Fiscal Year", "Account", "Bank",
	"Bank Account", "Journal Entry", "Payment Entry", "Purchase Invoice", "Sales Invoice", "Sales Order", "Subscription",
	"Subscription Plan", "Purchase Order", "Supplier", "Supplier Group", "E Sign", "Item", "Item Category", "UOM",
	"Mode of Payment", "Tax Category",
]


def _run_section(ctx, summary, label, fn, count, suffix=""):
	"""One section: run it, commit, flush the tracking log, print a line."""
	errors = []
	try:
		created = fn(ctx, int(count), errors)
	except Exception as exc:
		frappe.db.rollback()
		errors.append(f"section aborted: {str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__}")
		created = []
	frappe.db.commit()
	_flush_tracks()
	n_new = sum(len(v) for v in created.values()) if isinstance(created, dict) else len(created or [])
	key = f"{label}{suffix}"
	summary[key] = (n_new, errors)
	print(f"  {key:<40} +{n_new:<4} {'  ⚠ ' + errors[0] if errors else ''}")


def _print_failures(summary):
	failed = {k: v[1] for k, v in summary.items() if v[1]}
	if failed:
		print("\nFirst errors per section:")
		for label, errs in failed.items():
			for e in errs[:3]:
				print(f"  [{label}] {e}")


def run(count=30):
	"""Seed every section, topping each doctype up to `count` records."""
	frappe.flags.in_sample_data_import = True
	frappe.flags.mute_emails = True
	frappe.set_user("Administrator")
	ctx, summary = {}, {}
	try:
		for label, fn in SECTIONS:
			_run_section(ctx, summary, label, fn, count)
	finally:
		frappe.flags.in_sample_data_import = False
		frappe.flags.mute_emails = False
	print()
	report()
	_print_failures(summary)
	return {k: v[0] for k, v in summary.items()}


# ─── production ───────────────────────────────────────────────────────

DEMO_COMPANIES = [("Vrugle Demo Staffing", "VDS"), ("Vrugle Demo Consulting", "VDC")]

# Not company-bound: masters, CRM, marketing, services. Run once.
_PROD_SHARED_FIRST = [
	"ERP Configuration", "Sample PDF", "Employee", "Item Category", "UOM", "Item", "Supplier Group", "Supplier", "Bank",
	"Bank Account Type", "Bank Account", "Mode of Payment", "Tax Category", "Lead", "Customer", "Opportunity", "Marketing", "Interview",
	"Marketing Other Services", "Other Services", "CR", "Onboardings", "Technical services", "Subscription Plan",
]
# Accounting, run once per demo company (into that company only).
_PROD_PER_COMPANY = [
	"Account", "Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice", "Payment Entry",
	"Payment verification queue", "Journal Entry", "Subscription",
]
_PROD_SHARED_LAST = ["Revenue targets", "Call Details (opportunities)", "CRM shaping", "CRM activity", "E Sign"]


def company_bank_accounts(ctx, n, errors):
	"""A few bank accounts of the active company, each with its own ledger."""
	company, bank_list, types = _STATE["company"], _existing("Bank"), _existing("Bank Account Type")
	asset_group = frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Asset"}, "name")
	if not (asset_group and bank_list):
		errors.append(f"Bank Account: no asset group or banks for {company}")
		return []

	def make(i):
		ledger = _insert(
			frappe.get_doc(
				{
					"doctype": "Account", "account_name": f"Seed Bank Ledger {i:02d}", "company": company, "parent_account": asset_group,
					"is_group": 0, "account_type": "Bank", "root_type": "Asset", "report_type": "Balance Sheet", "account_currency": "INR",
				}
			)
		).name
		doc = frappe.get_doc(
			{
				"doctype": "Bank Account", "account_name": f"Seed {company} Account {i:02d}", "bank": random.choice(bank_list),
				"account_type": random.choice(types) if types else None, "bank_account_no": f"{random.randint(10**9, 10**10 - 1)}",
				"is_company_account": 1, "company": company, "account": ledger, "is_default": 0,
			}
		)
		return _insert(doc).name

	return _top_up("Bank Account", 3, make, errors, filters={"company": company})


def _ensure_company(name, abbr, errors):
	if not frappe.db.exists("Company", name):
		_attempt(
			f"Company {name}",
			lambda: _insert(frappe.get_doc({"doctype": "Company", "company_name": name, "abbr": abbr, "default_currency": "INR", "country": "India"})).name,
			errors,
		)
		frappe.db.commit()
		_flush_tracks()
	return bool(frappe.db.exists("Company", name))


def _ensure_fiscal_year(company, errors):
	"""Put the company into the year that's open today (a company may sit in
	only one active year), creating a calendar year if none is open; and make
	demo posting dates start from that year's first day."""
	today = getdate(nowdate())
	fy = frappe.db.get_value(
		"Fiscal Year", {"disabled": 0, "year_start_date": ["<=", today], "year_end_date": [">=", today]}, ["name", "year_start_date"], as_dict=True
	)

	def go():
		if fy:
			doc = frappe.get_doc("Fiscal Year", fy.name)
			if not any(r.company == company for r in doc.included_companies):
				doc.append("included_companies", {"company": company})
				doc.save(ignore_permissions=True)
			return fy.year_start_date
		doc = frappe.get_doc(
			{"doctype": "Fiscal Year", "year": str(today.year), "year_start_date": f"{today.year}-01-01", "year_end_date": f"{today.year}-12-31", "included_companies": [{"company": company}]}
		)
		_insert(doc)
		return doc.year_start_date

	start = _attempt(f"Fiscal Year for {company}", go, errors)
	if start:
		_STATE["fy_start"] = getdate(start)
	frappe.db.commit()
	return bool(start)


def run_production(count=20, companies=None):
	"""Seed a live site: two demo companies with a full set of accounting
	documents each, plus CRM, marketing and service data — all created and
	read back by the seeder alone (see the module docstring)."""
	companies = companies or DEMO_COMPANIES
	frappe.flags.in_sample_data_import = True
	frappe.flags.mute_emails = True
	frappe.set_user("Administrator")
	by_label = dict(SECTIONS)
	ctx, summary = {}, {}
	saved = dict(_STATE)
	_STATE["tracked_only"] = True
	try:
		ready = []
		setup_errors = []
		for name, abbr in companies:
			if _ensure_company(name, abbr, setup_errors) and _ensure_fiscal_year(name, setup_errors):
				ready.append(name)
		summary["Demo companies"] = (len(ready), setup_errors)
		print(f"  {'Demo companies':<40} {len(ready)}/{len(companies)} ready {'  ⚠ ' + setup_errors[0] if setup_errors else ''}")
		if not ready:
			raise RuntimeError("No demo company could be created — nothing seeded.")

		_STATE["company"] = ready[0]
		for label in _PROD_SHARED_FIRST:
			_run_section(ctx, summary, label, by_label[label], count)
		for name in ready:
			_STATE["company"] = name
			_run_section(ctx, summary, "Bank Account", company_bank_accounts, count, f" [{name}]")
			for label in _PROD_PER_COMPANY:
				_run_section(ctx, summary, label, by_label[label], count, f" [{name}]")
		_STATE["company"] = ready[0]
		for label in _PROD_SHARED_LAST:
			_run_section(ctx, summary, label, by_label[label], count)
	finally:
		_STATE.update(saved)
		frappe.flags.in_sample_data_import = False
		frappe.flags.mute_emails = False
	print()
	_print_failures(summary)
	return {k: v[0] for k, v in summary.items()}


def report():
	"""Current row counts for every doctype the frontend covers."""
	print("Doctype".ljust(28), "Count")
	for dt in DOCTYPES_REPORTED:
		try:
			print(dt.ljust(28), frappe.db.count(dt))
		except Exception:
			print(dt.ljust(28), "n/a")
