"""Realistic bulk data for documentation screenshots and mockups.

    bench --site <site> execute verp_staffing.utils.seed_documentation_data.run
    bench --site <site> execute verp_staffing.utils.seed_documentation_data.run --kwargs '{"force": 1}'

or on `bench migrate`, by setting `"seed_documentation_data": 1` in the site's site_config.json
(`after_migrate` below is registered in hooks.py and does nothing without that flag).

What it creates (all names, emails, phones, companies and amounts are made up, but shaped like the real thing):

  * companies    "Vrugle USA" (USD) and "Vrugle" (INR), each with its own chart of accounts and 3-4 bank
                 accounts (own ledger each), plus banks, modes of payment and lead sources
  * staff        ~24 users + employees across every department, wired into each department's
                 role hierarchy (Master Manager -> Manager -> Team Lead -> ...)
  * CRM          100 leads (full candidate profiles) -> 65 opportunities -> 50 customers
  * customers    spread over new / sales-only / resume / marketing (Started, Pending, Hold, Completed) /
                 JDC + interview support / RUC + training / CR (pending, resolved, refund) /
                 onboarding (active) / placed (onboarding completed)
  * interviews   4-8 per marketing customer, several rounds each, every one owned by a different
                 recruiter (Interview.owner)
  * accounting   1-3 Sales Orders per customer with payment terms, invoices raised per term, payment
                 entries verified into the extra bank accounts (or left pending / rejected / overdue),
                 and ~30 journal entries (rent, payroll, ad spend, transfers, bank charges, a refund)
  * activity     call logs on opportunities, CRM tasks and events

USD business (US candidates) goes to "Vrugle USA", INR business (India candidates) to "Vrugle".

Safety, same spirit as seed_production:
  - nothing is emailed or enqueued while it runs
  - runs once per site (global marker); pass force=1 to run again (that adds a second batch of people)
  - every record is added to the sample-data log, so "Remove Sample Data" on ERP Configuration clears it
  - each record is created under a savepoint: a failure is printed at the end and never stops the rest
  - login for the seeded staff: <first>.<last>@vrugle.com / PASSWORD below
"""

import random
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.utils import add_days, cint, getdate, nowdate

from verp_staffing.utils import sample_data_tracking as tracking

MARKER = "verp_documentation_seed_v1"
PASSWORD = "Vrugle@2026"

LEADS = 100
OPPORTUNITIES = 65
CUSTOMERS = 50

COMPANIES = {
	"usa": {"name": "Vrugle USA", "abbr": "VUS", "currency": "USD", "country": "United States"},
	"india": {"name": "Vrugle", "abbr": "VRG", "currency": "INR", "country": "India"},
}

BANKS = {
	"usa": [
		("Chase Bank", "CHASUS33", "Business Checking", "Current Account"),
		("Bank of America", "BOFAUS3N", "Operating Account", "Current Account"),
		("Wells Fargo", "WFBIUS6S", "Payments Account", "Current Account"),
	],
	"india": [
		("HDFC Bank", "HDFCINBB", "Current Account", "Current Account"),
		("ICICI Bank", "ICICINBB", "Collections Account", "Current Account"),
		("State Bank of India", "SBININBB", "Business Savings", "Savings Account"),
		("Axis Bank", "AXISINBB", "Salary Account", "Current Account"),
	],
}
# share of verified payments landing in each bank (same order as BANKS)
BANK_WEIGHTS = {"usa": [55, 30, 15], "india": [45, 28, 17, 10]}
MODES = {
	"usa": ["ACH Transfer", "Wire Transfer", "Zelle", "Credit Card"],
	"india": ["UPI", "NEFT", "IMPS", "RTGS"],
}
LEAD_SOURCES = [
	"LinkedIn", "Website Enquiry", "Referral", "Facebook Ads", "Google Ads", "Instagram", "WhatsApp Enquiry",
	"Webinar", "YouTube", "Email Campaign", "Alumni Network",
]

# key, first, last, department, role, reports-to key   (parents come before children)
STAFF = [
	("lmm", "Priya", "Raghavan", "Lead", "Lead Master Manager", None),
	("lm", "Daniel", "Whitfield", "Lead", "Lead Manager", "lmm"),
	("ltl", "Meera", "Krishnan", "Lead", "Lead Team Lead", "lm"),
	("lp1", "Kevin", "Alvarez", "Lead", "Lead Person", "ltl"),
	("lp2", "Sana", "Qureshi", "Lead", "Lead Person", "ltl"),
	("smm", "Rajesh", "Malhotra", "Sales", "Sales Master Manager", None),
	("sm", "Ashley", "Brennan", "Sales", "Sales Manager", "smm"),
	("stl", "Vikram", "Chauhan", "Sales", "Sales Team Lead", "sm"),
	("sp1", "Jessica", "Turner", "Sales", "Sales Person", "stl"),
	("sp2", "Arjun", "Nambiar", "Sales", "Sales Person", "stl"),
	("mmm", "Neha", "Bhatia", "Marketing", "Marketing Master Manager", None),
	("mm", "Marcus", "Reed", "Marketing", "Marketing Manager", "mmm"),
	("mtl", "Pooja", "Deshmukh", "Marketing", "Marketing Team Lead", "mm"),
	("msr", "Tyler", "Hughes", "Marketing", "Senior Recruiter", "mtl"),
	("mmen", "Farah", "Siddiqui", "Marketing", "Marketing Mentor", "msr"),
	("mr1", "Brandon", "Foster", "Marketing", "Recruiter", "mmen"),
	("mr2", "Lakshmi", "Venkatesh", "Marketing", "Recruiter", "mmen"),
	("rsr", "Anjali", "Kapoor", "Resume", "Senior Resume Person", None),
	("rp", "Rohit", "Saxena", "Resume", "Resume Person", "rsr"),
	("tmm", "Sameer", "Kulkarni", "Technical", "Technical Master Manager", None),
	("hr", "Rachel", "Kim", "HR", "HR Manager", None),
	("cr", "Naveen", "Pillai", "CR", "CR", None),
	("ob", "Grace", "Mitchell", "Onboarding", "OnBoarding Person", None),
	("acc", "Harish", "Menon", "Accounting", "Account Person", None),
]
LEAD_TEAM = ["ltl", "lp1", "lp2", "lm"]
SALES_TEAM = ["sp1", "sp2", "stl", "sm"]
MARKETING_TEAM = ["mr1", "mr2", "mmen", "msr", "mtl"]  # who may own an interview / a marketing record

I_FIRST = [
	"Aarav", "Vivaan", "Aditya", "Sai", "Arjun", "Krishna", "Ishaan", "Rohan", "Kabir", "Karthik", "Siddharth", "Rahul",
	"Nikhil", "Akash", "Varun", "Harsh", "Manish", "Pranav", "Tejas", "Vishal", "Ananya", "Diya", "Isha", "Meera",
	"Priya", "Riya", "Saanvi", "Tara", "Nisha", "Kavya", "Sneha", "Pallavi", "Divya", "Shruti", "Swathi", "Aishwarya",
]
I_LAST = [
	"Sharma", "Patel", "Reddy", "Nair", "Iyer", "Gupta", "Mehta", "Rao", "Singh", "Kumar", "Verma", "Joshi", "Menon",
	"Bose", "Agarwal", "Chowdhury", "Kulkarni", "Pillai", "Naidu", "Banerjee", "Desai", "Shetty", "Bhat", "Ghosh",
	"Trivedi", "Jain", "Mishra", "Chatterjee", "Srinivasan", "Ramanathan",
]
G_NAMES = [
	"Ethan Brooks", "Olivia Hayes", "Marcus Bennett", "Sophia Ramirez", "Daniel Kowalski", "Emily Nguyen", "Jason Park",
	"Hannah Schultz", "Carlos Mendez", "Grace Okafor", "Tyler Jensen", "Maya Thompson", "Andre Williams", "Lauren Fisher",
	"Wei Zhang", "Mei Lin Chen", "David Kim", "Jasmine Torres", "Omar Haddad", "Fatima Rahman", "Noah Castillo",
	"Isabella Rossi", "Ryan O'Connell", "Chloe Anderson", "Victor Petrov", "Natalie Brooks", "Samuel Adeyemi",
	"Angela Moretti", "Luis Herrera", "Rebecca Stein",
]
EMAIL_DOMAINS = ["gmail.com"] * 6 + ["outlook.com", "yahoo.com", "hotmail.com", "icloud.com"]

US_CITIES = [
	("Frisco", "TX", "750"), ("Plano", "TX", "750"), ("Irving", "TX", "750"), ("Austin", "TX", "787"), ("Dallas", "TX", "752"),
	("Charlotte", "NC", "282"), ("Raleigh", "NC", "276"), ("Edison", "NJ", "088"), ("Jersey City", "NJ", "073"),
	("Chicago", "IL", "606"), ("Atlanta", "GA", "303"), ("Columbus", "OH", "432"), ("Phoenix", "AZ", "850"),
	("San Jose", "CA", "951"), ("Boston", "MA", "021"), ("Herndon", "VA", "201"), ("Seattle", "WA", "981"),
]
IN_CITIES = [
	("Hyderabad", "Telangana", "5000"), ("Bengaluru", "Karnataka", "5600"), ("Pune", "Maharashtra", "4110"),
	("Chennai", "Tamil Nadu", "6000"), ("Ahmedabad", "Gujarat", "3800"), ("Noida", "Uttar Pradesh", "2013"),
	("Kochi", "Kerala", "6820"), ("Vijayawada", "Andhra Pradesh", "5200"),
]
STREETS = ["Preston Trail Dr", "Maple Ridge Ln", "Oak Hollow Ct", "Lakeview Blvd", "Cedar Creek Rd", "Willow Bend Way", "Parkside Ave", "Heritage Dr"]
US_VISAS = ["F1 CPT", "F1 OPT", "F1 OPT", "STEM OPT", "STEM OPT", "H1 B", "H1 B", "H4", "GREEN CARD", "USC", "EB - 2", "L - 2"]

TECH = [
	("Java, Spring Boot, Microservices, Kafka, AWS", "Senior Java Developer"),
	("Python, Django, FastAPI, PostgreSQL, Docker", "Python Developer"),
	("Spark, Airflow, Snowflake, SQL, dbt", "Data Engineer"),
	("React, TypeScript, Node.js, GraphQL", "Full Stack Developer"),
	("Selenium, Cypress, Java, TestNG, Postman", "QA Automation Engineer"),
	("Kubernetes, Terraform, Jenkins, AWS, Prometheus", "DevOps Engineer"),
	("Salesforce Apex, LWC, Flows, Integrations", "Salesforce Developer"),
	("SQL, Tableau, JIRA, Requirement Gathering, UAT", "Business Analyst"),
	("Power BI, SQL, Azure Data Factory, DAX", "BI Developer"),
	("ServiceNow, JavaScript, ITSM, REST APIs", "ServiceNow Developer"),
	("Azure, C#, .NET Core, SQL Server", ".NET Developer"),
	("Machine Learning, PyTorch, scikit-learn, MLOps", "ML Engineer"),
]
UNIVERSITIES_US = [
	"University of Texas at Dallas", "Northeastern University", "Arizona State University", "Illinois Institute of Technology",
	"Stevens Institute of Technology", "Texas A&M University-Commerce", "Wright State University", "Cleveland State University",
	"Kent State University", "University of North Texas", "New Jersey Institute of Technology",
]
UNIVERSITIES_IN = [
	"Anna University", "JNTU Hyderabad", "VIT Vellore", "SRM Institute of Science and Technology", "Savitribai Phule Pune University",
	"Osmania University", "Amrita Vishwa Vidyapeetham", "Manipal Institute of Technology", "BITS Pilani",
]
COURSES = [
	("Master of Science", "Computer Science"), ("Master of Science", "Information Systems"), ("Master of Science", "Data Science"),
	("Bachelor of Technology", "Information Technology"), ("Bachelor of Technology", "Computer Science and Engineering"),
	("Master of Business Administration", "Business Analytics"),
]
PAST_EMPLOYERS = [
	"Kestrel Infotech", "BlueOrbit Solutions", "Nimbus Software Pvt Ltd", "Trident Technologies", "Ardent Systems",
	"Vantage Digital", "Crestline Consulting", "Helix Data Services", "Orchid Softworks", "Meridian IT Services",
]
CERTS = [
	"AWS Certified Developer - Associate", "Oracle Certified Professional, Java SE 11", "Microsoft Certified: Azure Fundamentals",
	"Certified Kubernetes Application Developer", "Salesforce Platform Developer I", "Google Data Analytics Certificate",
	"Databricks Certified Data Engineer Associate", "PMI Agile Certified Practitioner", "ISTQB Foundation Level",
]

# fictional hiring companies for interviews
HIRING = [
	"Northbridge Financial", "Summit Health Systems", "BlueRidge Analytics", "Pinnacle Logistics", "Harborview Insurance",
	"Redwood Retail Group", "Lakeshore Energy", "Cobalt Networks", "Sterling Capital Partners", "Evergreen Pharma",
	"Ironclad Software", "Brightpath Education", "Atlas Mobility", "Crescent Bank & Trust", "Silverline Telecom",
	"Orion Aerospace Systems", "Maple & Finch Foods", "Granite Ridge Mortgage", "Vertex Cloud Services", "Keystone Healthcare",
]
INTERVIEW_ROLES = [
	"Senior Java Developer", "Data Engineer", "Full Stack Developer", "Python Developer", "DevOps Engineer",
	"QA Automation Engineer", "Business Analyst", "Cloud Engineer", "Salesforce Developer", "BI Developer", ".NET Developer",
]
FEEDBACK_GOOD = [
	"Strong on fundamentals, they want a system design round next.",
	"Went well. Interviewer liked the project walkthrough and asked about the data pipeline design.",
	"Positive feedback on coding round, waiting for the hiring manager's decision.",
	"Answered the behavioural questions confidently. Moving to the panel round.",
	"Good technical discussion around microservices and SQL tuning.",
]
FEEDBACK_BAD = [
	"Struggled on the concurrency questions. Team is moving ahead with other candidates.",
	"Feedback: good attitude but limited hands-on experience with the client's stack.",
	"Position was put on hold by the client after this round.",
	"Not selected. They wanted more production experience with Kubernetes.",
]
CANCEL_REASONS = ["Interviewer unavailable", "Client rescheduled the panel", "Candidate had a conflict", "Requirement put on hold"]
CR_CASES = [
	("Marketing", "Customer asked for a refund: no interviews in the last 45 days."),
	("Resume", "Unhappy with the resume revisions, wants the fee reviewed."),
	("Sales", "Disputes the second instalment, says it was not part of the agreement."),
	("Marketing", "Charged twice for the same instalment, wants one payment returned."),
]

RATES = {
	"usa": {"Marketing": [1500, 1800, 2000, 2200, 2500], "Resume": [250, 300, 350, 400], "Cover Letter": [150, 200, 250],
			"RUC": [800, 900, 1000], "Training": [600, 900, 1200], "JDC": [300, 400], "Interview Support": [500, 600, 750]},
	"india": {"Marketing": [45000, 55000, 65000, 75000], "Resume": [7000, 8500, 10000], "Cover Letter": [3000, 4000, 5000],
			  "RUC": [18000, 22000], "Training": [15000, 20000, 28000], "JDC": [8000, 10000], "Interview Support": [12000, 15000]},
}

# One entry per customer (50): what stage the customer is in, and how their money looks.
# stage: new | sales | resume | marketing | jdc | technical | cr | onboarding | placed
# marketing status / payment plan: see _plan_customer
PLAN = (
	[("new", None, "none")] * 4
	+ [("sales", None, p) for p in ("none", "advance", "pending", "none")]
	+ [("resume", s, p) for s, p in zip(["Started", "Completed", "Pending", "Request for Update", "Completed", "Started", "Completed", "Started"],
										["full", "advance", "pending", "advance", "full", "partial", "full", "pending"])]
	+ [("marketing", s, p) for s, p in zip(
		["Started"] * 8 + ["Pending"] * 3 + ["Hold"] * 2 + ["Completed"] * 3,
		["partial", "full", "pending", "advance", "partial", "overdue", "full", "partial", "advance", "pending", "none", "partial", "rejected", "full", "partial", "full"])]
	+ [("jdc", "Started", p) for p in ("full", "partial", "full", "advance")]
	+ [("technical", s, p) for s, p in zip(["Started", "Completed", "Pending", "Started"], ["partial", "full", "advance", "pending"])]
	+ [("cr", s, p) for s, p in zip(["Dispute Pending", "Dispute Pending", "Dispute Resolved", "Refund"], ["partial", "advance", "full", "full"])]
	+ [("onboarding", "Active", p) for p in ("full", "full", "partial")]
	+ [("placed", "Completed", "full")] * 3
)

_tracks: list[tuple[str, str]] = []
_errors: list[str] = []


# -- plumbing ----------------------------------------------------------------


def _track(doctype, name):
	if name:
		_tracks.append((doctype, name))


def _flush_tracks():
	if not _tracks:
		return
	log = tracking._read_log()
	for doctype, name in _tracks:
		names = log.setdefault(doctype, [])
		if name not in names:
			names.append(name)
	tracking._write_log(log)
	_tracks.clear()


def _attempt(label, fn):
	"""Run fn under a savepoint. On failure roll back to it, remember the message, return None."""
	point = f"docseed_{frappe.generate_hash(length=8)}"
	tracked_before = len(_tracks)
	frappe.db.savepoint(point)
	try:
		return fn()
	except Exception as exc:
		try:
			frappe.db.rollback(save_point=point)
		except Exception:
			frappe.db.rollback()
		del _tracks[tracked_before:]  # those records were rolled back with the savepoint
		msg = (str(exc).splitlines() or [type(exc).__name__])[0][:200]
		_errors.append(f"{label}: {msg}")
		frappe.log_error(title=f"Documentation seed: {label}", message=frappe.get_traceback())
		return None


def _insert(doc, tracked=False):
	if tracked:
		tracking.insert_tracked(doc)  # also tracks the Lead Detail Form etc. created alongside
	else:
		doc.insert(ignore_permissions=True)
		_track(doc.doctype, doc.name)
	return doc


def _today():
	return getdate(nowdate())


def _ago(days):
	return _today() - timedelta(days=days)


def _stamp(doctype, name, day, hour=None):
	"""Backdate creation/modified so lists, dashboards and trends spread over time."""
	hour = random.randint(8, 18) if hour is None else hour
	when = f"{day} {hour:02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
	frappe.db.set_value(doctype, name, {"creation": when, "modified": when}, update_modified=False)


def _set_owner(doctype, name, user):
	if user:
		frappe.db.set_value(doctype, name, "owner", user, update_modified=False)


def _wanted_status(doctype, wanted):
	options = (frappe.get_meta(doctype).get_field("status").options or "").split("\n")
	return wanted if wanted in options else None


def _pick(seq):
	return random.choice(seq)


# -- people ------------------------------------------------------------------


def _people(n):
	"""n unique made-up candidates: ~70% Indian names, the rest global."""
	people, seen = [], set()
	indian = int(n * 0.7)
	globals_ = list(G_NAMES)
	random.shuffle(globals_)
	while len(people) < n:
		if len(people) < indian:
			first, last = _pick(I_FIRST), _pick(I_LAST)
		else:
			if not globals_:
				break
			first, last = globals_.pop().split(" ", 1)
		if f"{first} {last}" in seen:
			continue
		seen.add(f"{first} {last}")
		people.append({"first": first, "last": last, "name": f"{first} {last}", "indian": len(people) < indian})
	random.shuffle(people)
	return people


def _fill_person(p, region):
	"""Email, phone, visa and address for a candidate. `region` decides the phone format, city and visa."""
	slug = f"{p['first']}.{p['last']}".lower().replace(" ", "").replace("'", "")
	tail = _pick([str(random.randint(1, 99)), str(random.randint(1985, 2001)), ""])
	p["email"] = f"{slug}{tail}@{_pick(EMAIL_DOMAINS)}"
	p["region"] = region
	if region == "usa":
		p["phone"] = f"+1 ({_pick([214, 469, 972, 704, 732, 312, 404, 614, 480, 408, 617, 703])}) {random.randint(200, 989)}-{random.randint(1000, 9999)}"
		city, state, zip_prefix = _pick(US_CITIES)
		p["city"], p["state"], p["country"] = city, state, "United States"
		p["address"] = f"{random.randint(120, 9800)} {_pick(STREETS)}, Apt {random.randint(101, 640)}, {city}, {state} {zip_prefix}{random.randint(10, 99)}"
		p["visa"] = _pick(US_VISAS)
		p["universities"] = UNIVERSITIES_US
	else:
		p["phone"] = f"+91 {_pick(['98', '99', '90', '81', '88', '70', '63'])}{random.randint(10, 99)}{random.randint(10000, 99999)}"
		city, state, pin_prefix = _pick(IN_CITIES)
		p["city"], p["state"], p["country"] = city, state, "India"
		p["address"] = f"Flat {random.randint(101, 908)}, {_pick(['Sri Sai', 'Lakshmi', 'Green Valley', 'Palm Grove', 'Skyline'])} Residency, {_pick(['Road No. 4', 'Main Road', '2nd Cross', 'Sector 12'])}, {city}, {state} {pin_prefix}{random.randint(10, 99)}"
		p["visa"] = ""
		p["universities"] = UNIVERSITIES_IN
	p["google_voice"] = f"+1 ({_pick([214, 469, 972, 704, 732])}) {random.randint(200, 989)}-{random.randint(1000, 9999)}"
	tech, role = _pick(TECH)
	p["tech"], p["target_role"] = tech, role
	return p


# -- phases ------------------------------------------------------------------


def _ensure_config():
	"""Lead sources, banks, bank account types and modes of payment (this site starts with none)."""
	for source in LEAD_SOURCES:
		if not frappe.db.exists("Lead Source", source):
			_attempt(f"Lead Source {source}", lambda s=source: _insert(frappe.get_doc({"doctype": "Lead Source", "name1": s})))
	for kind in ("Current Account", "Savings Account"):
		if not frappe.db.exists("Bank Account Type", kind):
			_attempt(f"Bank Account Type {kind}", lambda k=kind: _insert(frappe.get_doc({"doctype": "Bank Account Type", "account_type": k})))
	for region in BANKS:
		for bank, swift, _label, _kind in BANKS[region]:
			if not frappe.db.exists("Bank", bank):
				_attempt(f"Bank {bank}", lambda b=bank, s=swift: _insert(frappe.get_doc({"doctype": "Bank", "bank_name": b, "swift_number": s})))
	types = {"ACH Transfer": "Bank", "Wire Transfer": "Bank", "Zelle": "Bank", "Credit Card": "General", "UPI": "Phone", "NEFT": "Bank", "IMPS": "Bank", "RTGS": "Bank"}
	for mode, kind in types.items():
		if not frappe.db.exists("Mode of Payment", mode):
			_attempt(f"Mode of Payment {mode}", lambda m=mode, k=kind: _insert(frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": m, "enabled": 1, "type": k})))
	frappe.db.commit()


def _ensure_companies(ctx):
	"""Vrugle USA (USD) and Vrugle (INR): company, open fiscal year, and their bank accounts."""
	today = _today()
	fy = frappe.db.get_value("Fiscal Year", {"disabled": 0, "year_start_date": ["<=", today], "year_end_date": [">=", today]}, ["name", "year_start_date"], as_dict=True)
	ctx["fy_start"] = getdate(fy.year_start_date) if fy else date_from_year(today)
	ctx["company"] = {}
	for region, c in COMPANIES.items():
		if not frappe.db.exists("Company", c["name"]):
			_attempt(
				f"Company {c['name']}",
				lambda c=c: _insert(frappe.get_doc({"doctype": "Company", "company_name": c["name"], "abbr": c["abbr"], "default_currency": c["currency"], "country": c["country"]})),
			)
			frappe.db.commit()
		if not frappe.db.exists("Company", c["name"]):
			continue
		_attempt(f"Fiscal Year for {c['name']}", lambda c=c: _include_in_fiscal_year(c["name"], fy, today))
		ctx["company"][region] = c["name"]
	frappe.db.commit()

	ctx["acc"] = {}
	for region, company in ctx["company"].items():
		ctx["acc"][region] = _company_accounts(region, company)
	_flush_tracks()
	frappe.db.commit()


def date_from_year(today):
	return getdate(f"{today.year}-01-01")


def _include_in_fiscal_year(company, fy, today):
	if fy:
		doc = frappe.get_doc("Fiscal Year", fy.name)
		if not any(r.company == company for r in doc.included_companies):
			doc.append("included_companies", {"company": company})
			doc.save(ignore_permissions=True)
		return
	doc = frappe.get_doc({"doctype": "Fiscal Year", "year": str(today.year), "year_start_date": f"{today.year}-01-01", "year_end_date": f"{today.year}-12-31", "included_companies": [{"company": company}]})
	_insert(doc)


def _company_accounts(region, company):
	"""Ledger accounts the seeder posts to, and the company's bank accounts (each with its own ledger)."""
	abbr, currency = COMPANIES[region]["abbr"], COMPANIES[region]["currency"]
	get = lambda **f: frappe.db.get_value("Account", {"company": company, "is_group": 0, **f}, "name")
	named = lambda label: frappe.db.get_value("Account", {"company": company, "account_name": label, "is_group": 0}, "name")
	acc = {
		"receivable": get(account_type="Receivable"),
		"income": named("Sales") or get(account_type="Income Account"),
		"rent": named("Office Expenses") or get(account_type="Expense Account"),
		"salary": named("Salary") or get(account_type="Expense Account"),
		"marketing": named("Marketing Expenses") or get(account_type="Expense Account"),
		"equity": get(root_type="Equity"),
		"banks": [],
	}
	group = frappe.db.get_value("Account", {"company": company, "is_group": 1, "account_type": "Bank"}, "name") or frappe.db.get_value(
		"Account", {"company": company, "is_group": 1, "root_type": "Asset"}, "name"
	)
	for n, (bank, _swift, label, kind) in enumerate(BANKS[region]):
		digits = f"{random.randint(10**9, 10**10 - 1)}"
		ledger_name = f"{bank} {label} ({digits[-4:]})"
		existing = frappe.db.get_value("Bank Account", {"company": company, "bank": bank}, ["name", "account"], as_dict=True)
		if existing:
			acc["banks"].append(existing.account)
			continue

		def make(bank=bank, label=label, kind=kind, digits=digits, ledger_name=ledger_name, n=n):
			ledger = _insert(
				frappe.get_doc(
					{
						"doctype": "Account", "account_name": ledger_name, "company": company, "parent_account": group, "is_group": 0,
						"account_type": "Bank", "root_type": "Asset", "report_type": "Balance Sheet", "account_currency": currency,
					}
				)
			).name
			doc = {
				"doctype": "Bank Account", "account_name": f"{COMPANIES[region]['name']} - {bank} {label}", "bank": bank, "account_type": kind,
				"bank_account_no": digits, "is_company_account": 1, "company": company, "account": ledger, "is_default": int(n == 0),
			}
			if region == "india":
				doc["ifsc_code"] = f"{bank.split()[0][:4].upper()}000{random.randint(1000, 9999)}"
			_insert(frappe.get_doc(doc))
			return ledger

		ledger = _attempt(f"Bank Account {bank} ({company})", make)
		if ledger:
			acc["banks"].append(ledger)
	return acc


def _create_staff(ctx):
	from frappe.utils.password import update_password

	ctx["emp"], ctx["user"] = {}, {}
	for key, first, last, dept, role, parent in STAFF:
		email = f"{first}.{last}@vrugle.com".lower()

		def make(key=key, first=first, last=last, dept=dept, role=role, parent=parent, email=email):
			if not frappe.db.exists("User", email):
				user = frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "last_name": last, "send_welcome_email": 0, "enabled": 1})
				if frappe.db.exists("Role", role):
					user.append("roles", {"role": role})
				_insert(user)
				update_password(email, PASSWORD)
			emp = frappe.db.get_value("Employee", {"user": email}, "name")
			if not emp:
				doc = frappe.get_doc(
					{
						"doctype": "Employee", "user": email, "employee_name": f"{first} {last}", "enabled": 1,
						"start_date": _ago(random.randint(200, 1100)),
						"employee_assignment_details_table": [{"department": dept, "designation": role, "assigned_to": ctx["emp"].get(parent) if parent else None}],
					}
				)
				emp = _insert(doc).name
			ctx["emp"][key], ctx["user"][key] = emp, email

		_attempt(f"Staff {first} {last}", make)
	_flush_tracks()
	frappe.db.commit()
	for key in ("lmm", "smm", "mmm", "rsr", "tmm", "cr", "ob", "acc"):
		if key not in ctx["emp"]:
			_errors.append(f"Staff: {key} missing, later steps that assign to it will fall back to Administrator's auto-assign")


def _enrich_lead_detail(ldf, p):
	"""Fill the Lead Detail Form the Lead created, with a believable candidate profile."""
	doc = frappe.get_doc("Lead Detail Form", ldf)
	doc.first_name, doc.surname = p["first"], p["last"]
	doc.email = p["email"]
	doc.personal_phone_number = p["phone"]
	doc.google_voice_number = p["google_voice"]
	doc.number_for_marketing = p["google_voice"]
	doc.marketing_email_id = f"{p['first']}.{p['last']}.jobs@{'gmail.com'}".lower().replace(" ", "")
	doc.date_of_birth = f"{random.randint(1988, 2001)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
	doc.technologies = p["tech"]
	doc.current_address = p["address"]
	doc.current_visa_status = p["visa"] or None
	doc.certificate_or_completed_course = _pick(CERTS)
	doc.additional_skills = "Agile/Scrum, CI/CD, REST APIs, Git, JIRA"
	doc.availability_for_interview = "Weekdays, 10 AM - 6 PM " + ("EST" if p["region"] == "usa" else "IST")
	doc.personal_linkedin = f"https://www.linkedin.com/in/{p['first'].lower()}-{p['last'].lower().replace(' ', '-')}-{random.randint(10, 99)}{_pick('abcdef')}{random.randint(10, 99)}"
	doc.remarks = _pick(
		["Referred by a former student.", "Wants product-company roles, open to relocation.", "Prefers contract-to-hire.", "Needs marketing to start within two weeks.", "Strong communicator, first job search in the US."]
	)
	course = _pick(COURSES)
	end_year = random.randint(2021, 2025)
	doc.append(
		"educational_details",
		{
			"specialization": course[1], "university": _pick(p["universities"]), "start_date": f"08-{end_year - 2}", "end_date": f"05-{end_year}",
			"course_name": course[0], "grade": round(random.uniform(3.1, 3.9), 2) if p["region"] == "usa" else round(random.uniform(7.2, 9.1), 1),
			"course_description": f"{course[0]} in {course[1]}, coursework in distributed systems, databases and cloud computing.",
		},
	)
	if random.random() < 0.7:
		doc.experience = 1
		start = random.randint(2019, 2022)
		doc.append(
			"past_experience_table",
			{
				"company": _pick(PAST_EMPLOYERS), "job_role": p["target_role"], "employment_type": "Full-time", "location": f"{_pick(IN_CITIES)[0]}, India",
				"location_type": _pick(["Onsite", "Hybrid"]), "start_date": f"06-{start}", "end_date": f"07-{start + random.randint(1, 3)}",
				"description": f"Built and supported {p['tech'].split(',')[0]} based applications; worked closely with QA and product teams.",
				"skills": p["tech"],
			},
		)
	doc.append("address_history", {"state": p["state"], "country": p["country"], "from_date": f"{random.randint(2022, 2024)}-0{random.randint(1, 9)}", "to_date": "Present"})
	doc.save(ignore_permissions=True)


def _create_crm(ctx):
	"""100 leads, 65 of them with an opportunity, 50 of those turned into customers.

	Returns ctx["customers"]: one dict per customer (person, names of lead/opportunity/customer, region).
	"""
	people = _people(LEADS)
	converted = people[:CUSTOMERS]
	other_opp = people[CUSTOMERS:OPPORTUNITIES]
	lead_only = people[OPPORTUNITIES:]
	for i, p in enumerate(people):
		# ~35% India-based (Indian names only), the rest US candidates
		region = "india" if p["indian"] and random.random() < 0.5 else "usa"
		_fill_person(p, region)
	# how each converted person progressed; oldest customers first
	random.shuffle(converted)
	stage_plan = list(PLAN)
	random.shuffle(stage_plan)  # which customer is in which stage is arbitrary
	ctx["customers"] = []

	# lead-only people: status mix
	lead_only_status = ["Open"] * 12 + ["Lead"] * 11 + ["Interested"] * 7 + ["Lost"] * 5
	random.shuffle(lead_only_status)
	# opportunities that did not convert
	other_status = ["Open"] * 6 + ["Quotation"] * 3 + ["Replied"] * 3 + ["Lost"] * 3
	random.shuffle(other_status)

	sales_stages = frappe.get_all("Sales Stage", pluck="name")
	stage_by_status = {
		"Open": ["Prospecting", "Qualification", "Needs Analysis"], "Quotation": ["Proposal/Price Quote", "Negotiation/Review"],
		"Replied": ["Value Proposition", "Identifying Decision Makers"], "Converted": ["Negotiation/Review"], "Lost": ["Perception Analysis", "Proposal/Price Quote"],
	}
	prob = {"Open": [10, 25], "Quotation": [50, 75], "Replied": [25, 50], "Converted": [100], "Lost": [0]}

	def opp_amount(region):
		return _pick([1800, 2400, 3200, 3800, 4500]) if region == "usa" else _pick([55000, 72000, 95000, 120000, 150000])

	def build(p, opp_status, lead_status, lead_days, opp_days, cust_days, plan):
		lead_owner, sales_owner = ctx["emp"].get(_pick(LEAD_TEAM)), ctx["emp"].get(_pick(SALES_TEAM))
		lead = frappe.get_doc({"doctype": "Lead", "name1": p["name"], "lead_owner": lead_owner, "source": _pick(LEAD_SOURCES), "status": lead_status or "Open"})
		lead._email, lead._personal_phone_number = p["email"], p["phone"]
		_insert(lead, tracked=True)
		_stamp("Lead", lead.name, _ago(lead_days))
		_set_owner("Lead", lead.name, frappe.db.get_value("Employee", lead_owner, "user"))
		if lead.lead_details:
			_attempt(f"Lead profile {p['name']}", lambda: _enrich_lead_detail(lead.lead_details, p))
		out = {"person": p, "lead": lead.name, "plan": plan}
		if not opp_status:
			return out

		opp = frappe.get_doc(
			{
				"doctype": "Opportunity", "name1": p["name"], "opportunity_from_lead": lead.name, "opportunity_owner": sales_owner,
				"source": lead.source, "status": opp_status, "sales_stage": _pick(stage_by_status[opp_status]),
				"probability_": _pick(prob[opp_status]), "currency": COMPANIES[p["region"]]["currency"], "opportunity_amount": opp_amount(p["region"]),
				"expected_closing_date": add_days(_ago(opp_days), random.randint(7, 30)),
			}
		)
		for d in range(random.randint(1, 3)):
			opp.append("call_details", {"date": add_days(_ago(opp_days), d * 2 + 1), "duration": random.choice([420, 600, 900, 1260, 1800])})
		_insert(opp, tracked=True)
		_stamp("Opportunity", opp.name, _ago(opp_days))
		_set_owner("Opportunity", opp.name, frappe.db.get_value("Employee", sales_owner, "user"))
		out["opportunity"], out["sales_owner"] = opp.name, sales_owner
		if opp_status != "Converted":
			return out

		customer = frappe.get_doc({"doctype": "Customer", "name1": p["name"], "customer_from": "Opportunity", "party_name": opp.name, "customer_owner": sales_owner})
		_insert(customer, tracked=True)
		_stamp("Customer", customer.name, _ago(cust_days))
		_set_owner("Customer", customer.name, frappe.db.get_value("Employee", sales_owner, "user"))
		out["customer"], out["days"] = customer.name, cust_days
		return out

	for p, plan in zip(converted, stage_plan):
		cust_days = random.randint(12, 118)
		opp_days = cust_days + random.randint(3, 9)
		lead_days = opp_days + random.randint(2, 14)
		res = _attempt(f"Customer chain {p['name']}", lambda: build(p, "Converted", None, lead_days, opp_days, cust_days, plan))
		if res and res.get("customer"):
			ctx["customers"].append(res)
	for p, status in zip(other_opp, other_status):
		opp_days = random.randint(4, 70)
		_attempt(f"Opportunity chain {p['name']}", lambda: build(p, status, None, opp_days + random.randint(2, 14), opp_days, None, None))
	for p, status in zip(lead_only, lead_only_status):
		_attempt(f"Lead {p['name']}", lambda: build(p, None, status, random.randint(1, 160), None, None, None))
	_flush_tracks()
	frappe.db.commit()


# -- services ---------------------------------------------------------------


def _assign(doctype, customer, employee):
	if not employee:
		return
	for name in frappe.get_all(doctype, {"customer": customer}, pluck="name"):
		frappe.db.set_value(doctype, name, "assign_to", employee, update_modified=False)


def _sample_pdf():
	import io

	from pypdf import PdfWriter

	existing = frappe.db.get_value("File", {"file_name": "candidate_document.pdf", "is_private": 1}, "file_url")
	if existing:
		return existing
	writer = PdfWriter()
	writer.add_blank_page(width=595, height=842)
	buf = io.BytesIO()
	writer.write(buf)
	f = frappe.get_doc({"doctype": "File", "file_name": "candidate_document.pdf", "content": buf.getvalue(), "is_private": 1})
	f.insert(ignore_permissions=True)
	_track("File", f.name)
	return f.file_url


def _forward(customer, service, **kw):
	from verp_staffing.crm.api.auto_assign import forward_candidate

	return forward_candidate(customer, service, **kw)


def _marketing(c, ctx, status):
	"""Forward to Marketing, then give it an owner, a target and a week of job-application counts."""
	customer, idx = c["customer"], c["index"]
	_forward(customer, "Marketing")
	name = frappe.db.get_value("Marketing", {"customer": customer}, "name")
	doc = frappe.get_doc("Marketing", name)
	doc.assign_to = ctx["emp"].get(MARKETING_TEAM[idx % len(MARKETING_TEAM)]) or doc.assign_to
	doc.target, doc.target_based_on = _pick([15, 20, 25, 30, 40]), _pick(["Daily", "Daily", "Weekly"])
	doc.start_date = _ago(c["active_days"])
	if _wanted_status("Marketing", status):
		doc.status = status
	if not doc.get("job_application_count"):
		for d in range(1, 9):
			if (_today() - timedelta(days=d)).weekday() >= 5:
				continue  # weekends off
			small, large = random.randint(8, 24), random.randint(1, 9)
			doc.append("job_application_count", {"date": _ago(d), "small_application": small, "large_application": large, "total_application": small + large})
	doc.save(ignore_permissions=True)
	_stamp("Marketing", name, _ago(c["active_days"]))
	return name


def _service_status(doctype, customer, status, child=None, row=None):
	name = frappe.db.get_value(doctype, {"customer": customer}, "name")
	if not name:
		return
	doc = frappe.get_doc(doctype, name)
	if _wanted_status(doctype, status):
		doc.status = status
	if child and not doc.get(child):
		doc.append(child, row)
	doc.save(ignore_permissions=True)


def _resume_services(c, ctx, status):
	customer, pdf = c["customer"], ctx["pdf"]
	_forward(customer, "Resume")
	_forward(customer, "Cover Letter")
	_assign("Resume", customer, ctx["emp"].get("rsr" if c["index"] % 2 else "rp"))
	_assign("Cover Letter", customer, ctx["emp"].get("rp" if c["index"] % 2 else "rsr"))
	name = c["person"]["name"]
	_service_status("Resume", customer, status, "resume_table", {"document": pdf, "document_title": f"{name} - Resume v2", "date": _ago(random.randint(1, 6))})
	cover_status = {"Completed": "Completed", "Started": "Started", "Pending": "Pending", "Request for Update": "Started"}[status]
	_service_status("Cover Letter", customer, cover_status, "proof_of_work", {"document": pdf, "document_title": "Cover letter", "description": "Tailored cover letter", "date": _ago(random.randint(1, 5))})


def _technical_services(c, ctx, status):
	customer = c["customer"]
	_forward(customer, "RUC")
	_forward(customer, "Training")
	_assign("RUC", customer, ctx["emp"].get("tmm"))
	_assign("Training", customer, ctx["emp"].get("tmm"))
	projects = ["Payments API walkthrough", "Data pipeline design", "React dashboard", "System design mock", "SQL query tuning"]
	rows = [
		{"date": _ago(d * 3 + 1), "session_duration_in_hour": _pick([1, 1.5, 2]), "projects": _pick(projects), "quality": _pick(["GOOD", "EXCELLENT", "AVERAGE"]),
		 "candidate_feedback": _pick(["Helpful session, clear explanations.", "Good pace, learned a lot.", "Would like more mock interviews."])}
		for d in range(random.randint(2, 4))
	]
	name = frappe.db.get_value("RUC", {"customer": customer}, "name")
	if name:
		doc = frappe.get_doc("RUC", name)
		if _wanted_status("RUC", status):
			doc.status = status
		if not doc.get("session_details"):
			for r in rows:
				doc.append("session_details", r)
		doc.save(ignore_permissions=True)
	_service_status("Training", customer, {"Completed": "Completed", "Pending": "Pending"}.get(status, "Started"))


def _interviews(c, ctx, style):
	"""4-8 interviews for a marketing customer, each with its own owner and a few rounds.

	style: "offer" ends with Get The Offer (placed / onboarding customers), "mix" is a realistic spread.
	"""
	customer = c["customer"]
	marketing = frappe.db.get_value("Marketing", {"customer": customer}, "name")
	types = frappe.get_all("Type Of Interview", pluck="name")
	if not (marketing and types):
		return []
	count = random.randint(4, 8)
	kinds = ["offer"] if style == "offer" else []
	pool = ["rejected", "rejected", "waiting", "completed", "cancelled", "rescheduled", "upcoming", "upcoming"]
	kinds += [_pick(pool) for _ in range(count - len(kinds))]
	random.shuffle(kinds)
	owners = [ctx["user"][k] for k in MARKETING_TEAM if k in ctx["user"]]
	start_owner = c["index"] % max(len(owners), 1)
	created = []
	used = set()

	for n, kind in enumerate(kinds):
		company = _pick([h for h in HIRING if h not in used] or HIRING)
		used.add(company)
		rounds = _rounds(kind, c["active_days"], types)
		doc = frappe.get_doc(
			{"doctype": "Interview", "marketing_link": marketing, "company": company, "role": c["person"]["target_role"] if n % 2 else _pick(INTERVIEW_ROLES),
			 "status": rounds[-1]["status"], "interview_rounds_table": rounds}
		)
		_insert(doc)
		first_day = min(getdate(r["date_of_interview"]) for r in rounds)
		_stamp("Interview", doc.name, add_days(first_day, -random.randint(1, 3)))
		if owners:
			_set_owner("Interview", doc.name, owners[(start_owner + n) % len(owners)])  # different owner for each interview
		created.append(doc.name)
	return created


def _rounds(kind, active_days, types):
	def round_(number, day, status, feedback=None, **extra):
		hour = _pick([9, 10, 11, 13, 14, 15])
		return {
			"round": str(number), "date_of_interview": str(day), "type_of_interview": _pick(types),
			"from_time": f"{hour}:00:00", "to_time": f"{hour + 1}:00:00", "follow_up": 0, "status": status, "feedback": feedback, **extra,
		}

	span = max(active_days - 3, 6)
	base = random.randint(2, span)  # days ago the first round happened
	total = {"offer": 3, "rejected": random.randint(1, 3), "waiting": random.randint(1, 2), "completed": random.randint(2, 3),
			 "cancelled": 1, "rescheduled": 2, "upcoming": random.randint(1, 3)}[kind]
	rows = []
	for r in range(1, total + 1):
		day = _ago(max(base - (r - 1) * 4, 1))
		last = r == total
		if kind == "offer":
			rows.append(round_(r, day, "Get The Offer" if last else "Completed", "Offer letter received, background check next." if last else _pick(FEEDBACK_GOOD)))
		elif kind == "rejected":
			rows.append(round_(r, day, "Rejected" if last else "Completed", _pick(FEEDBACK_BAD) if last else _pick(FEEDBACK_GOOD)))
		elif kind == "waiting":
			rows.append(round_(r, day, "Completed", _pick(FEEDBACK_GOOD)))
		elif kind == "completed":
			rows.append(round_(r, day, "Completed", _pick(FEEDBACK_GOOD)))
		elif kind == "cancelled":
			rows.append(round_(r, day, "Cancelled", None, cancelled_by=_pick(["Company", "Candidate"]), reason_of_cancel=_pick(CANCEL_REASONS)))
		elif kind == "rescheduled":
			if last:
				rows.append(round_(r, _ago(max(base - 4, 1)), "Completed", _pick(FEEDBACK_GOOD)))
			else:
				rows.append(round_(r, day, "Rescheduled", None, cancelled_by="Company", reason_of_cancel="Client rescheduled the panel"))
		elif kind == "upcoming":
			if last:
				rows.append(round_(r, add_days(_today(), random.randint(0, 9)), "Scheduled"))
			else:
				rows.append(round_(r, day, "Completed", _pick(FEEDBACK_GOOD)))
	return rows


def _jdc(c, ctx):
	"""JDC and Interview Support on real interview rounds of this customer."""
	customer = c["customer"]
	marketing = frappe.db.get_value("Marketing", {"customer": customer}, "name")
	interviews = frappe.get_all("Interview", {"marketing_link": marketing}, pluck="name")
	rounds = frappe.get_all("Interview Round", {"parenttype": "Interview", "parent": ["in", interviews or ["-"]]}, pluck="name", order_by="creation asc")
	if not rounds:
		return
	_forward(customer, "JDC", interview_round=rounds[0])
	_forward(customer, "Interview Support", interview_round=rounds[min(1, len(rounds) - 1)])
	_assign("JDC", customer, ctx["emp"].get("tmm"))
	_assign("Interview Support", customer, ctx["emp"].get("tmm"))
	for doctype, status in (("JDC", _pick(["Started", "Completed"])), ("Interview Support", _pick(["Pending", "Started"]))):
		name = frappe.db.get_value(doctype, {"customer": customer}, "name")
		if name and _wanted_status(doctype, status):
			frappe.db.set_value(doctype, name, "status", status, update_modified=False)


def _cr(c, ctx, status):
	from verp_staffing.crm.api.auto_assign import handle_cr_forward

	service, reason = CR_CASES[c["index"] % len(CR_CASES)]
	customer = c["customer"]
	handle_cr_forward(customer=customer, from_service_name=service, reason_for_forwarding=reason, assign_employee=ctx["emp"].get("cr"))
	name = frappe.db.get_value("CR", {"customer": customer}, "name")
	if status == "Dispute Pending" or not name:
		return
	row = frappe.get_all("CR History", {"parent": name}, pluck="name", order_by="creation desc", limit=1)
	values = {"status": status, "remarks": "Settled with the customer over a call." if status == "Dispute Resolved" else "Partial refund approved by accounts.",
			  "resolve_refund_on": f"{_ago(random.randint(1, 8))} 12:00:00", "action_by": ctx["user"].get("cr", "Administrator")}
	if row:
		frappe.db.set_value("CR History", row[0], values, update_modified=False)
	frappe.db.set_value("CR", name, "status", status, update_modified=False)


def _onboarding(c, ctx, completed):
	from verp_staffing.crm.api.auto_assign import handle_onboarding_forward

	customer = c["customer"]
	marketing = frappe.db.get_value("Marketing", {"customer": customer}, "name")
	interview = frappe.db.get_value("Interview", {"marketing_link": marketing, "status": "Get The Offer"}, "name") or frappe.db.get_value("Interview", {"marketing_link": marketing}, "name")
	if not interview:
		return
	handle_onboarding_forward(
		customer=customer, from_service_name="Marketing", interview=interview, email=c["person"]["email"], password="not-stored",
		assign_employee=ctx["emp"].get("ob"),
	)
	name = frappe.db.get_value("Onboardings", {"customer": customer}, "name")
	if not name:
		return
	company = frappe.db.get_value("Interview", interview, "company")
	doc = frappe.get_doc("Onboardings", name)
	frappe.flags.cr_system_action = True
	try:
		for k in range(random.randint(1, 3)):
			first, last = _pick(I_FIRST + ["Megan", "Brian", "Stephanie", "Robert"]), _pick(I_LAST + ["Collins", "Murphy", "Baker"])
			doc.append(
				"contact_references",
				{"name1": f"{first} {last}", "email": f"{first}.{last}@{company.split()[0].lower().replace('&', '')}.com".lower(), "designation": _pick(["Talent Acquisition Partner", "Hiring Manager", "HR Business Partner"]),
				 "phone_number": f"+1 ({_pick([214, 312, 404, 617, 703])}) {random.randint(200, 989)}-{random.randint(1000, 9999)}", "company": company},
			)
		doc.save(ignore_permissions=True)
	finally:
		frappe.flags.cr_system_action = False
	if completed:
		hist = frappe.get_all("Onboarding History", {"parent": name}, pluck="name", order_by="creation desc", limit=1)
		if hist:
			frappe.db.set_value("Onboarding History", hist[0], {"status": "Completed", "action_on": f"{_ago(random.randint(1, 10))} 15:00:00", "action_by": ctx["user"].get("ob", "Administrator")}, update_modified=False)
		frappe.db.set_value("Onboardings", name, "status", "Completed", update_modified=False)


# -- accounting --------------------------------------------------------------


def _sales_order_items(stage, k, region, c_index):
	if k == 0:
		names = {
			"resume": ["Resume", "Cover Letter"], "marketing": ["Marketing"] + (["Resume"] if c_index % 2 else []), "jdc": ["Marketing", "JDC"],
			"technical": ["RUC", "Training"], "cr": ["Marketing", "Resume"], "onboarding": ["Marketing", "Resume", "Cover Letter"], "placed": ["Marketing", "Resume", "Cover Letter"],
			"sales": ["Marketing"], "new": [],
		}[stage]
	else:
		names = _pick([["Interview Support"], ["Training"], ["JDC", "Interview Support"], ["Cover Letter"]])
	return [(n, _pick(RATES[region][n])) for n in names]


def _create_sales_orders(c, ctx):
	"""1-3 Sales Orders for a customer, each with payment terms. Returns [(so_name, [term_row_names])]."""
	stage, region, customer = c["stage"], c["person"]["region"], c["customer"]
	if stage == "new":
		return []
	company, acc = ctx["company"].get(region), ctx["acc"].get(region)
	if not (company and acc and acc["income"]):
		_errors.append(f"Sales Order {customer}: company/accounts for {region} not ready")
		return []
	how_many = {"sales": 1, "resume": 1, "technical": random.randint(1, 2), "marketing": random.randint(1, 2), "jdc": 2, "cr": 2, "onboarding": random.randint(2, 3), "placed": random.randint(2, 3)}[stage]
	out = []
	for k in range(how_many):
		items = _sales_order_items(stage, k, region, c["index"])
		total = sum(rate for _n, rate in items)
		terms_n = 1 if total < (400 if region == "usa" else 12000) else random.choice([2, 2, 3])
		fractions = {1: [1], 2: [0.5, 0.5], 3: [0.4, 0.3, 0.3]}[terms_n]
		desc = {1: ["Full payment"], 2: ["Advance payment", "Balance after first interview"], 3: ["Advance payment", "Second instalment", "Final instalment on placement"]}[terms_n]
		amounts = [int(round(total * f)) for f in fractions[:-1]]
		amounts.append(total - sum(amounts))
		posting = add_days(_ago(c["days"]), random.randint(0, 2) + k * random.randint(10, 25))
		posting = min(posting, _ago(1))
		posting = max(posting, ctx["fy_start"])
		currency = COMPANIES[region]["currency"]
		so = frappe.get_doc(
			{
				"doctype": "Sales Order", "customer": customer, "company": company, "currency": currency, "posting_date": str(posting),
				"items": [{"item": n, "type": "Sales", "income_account": acc["income"], "qty": 1, "rate": r, "amount": r} for n, r in items],
				"payment_terms": [{"payment_condition": "Not Applied", "amount": a, "so_currency": currency, "description": d} for a, d in zip(amounts, desc)],
			}
		)
		_insert(so)
		# a couple of "sales" customers keep their order as a draft, everything else is submitted
		if not (stage == "sales" and c["plan"] == "none" and c["index"] % 2 == 0):
			_submit_sales_order(so)
		# backdate only after submitting: submit checks `modified` against the copy in memory
		_stamp("Sales Order", so.name, posting)
		_set_owner("Sales Order", so.name, frappe.db.get_value("Employee", c.get("sales_owner"), "user") if c.get("sales_owner") else None)
		out.append((so.name, str(posting)))
	return out


def _submit_sales_order(so):
	"""Submit with the "send candidate form / agreement immediately" switches off (they need email and PDFs)."""
	from verp_staffing.accounts.doctype.sales_order import sales_order as so_module

	real = so_module.get_erp_config

	def config():
		cfg = dict(real())
		cfg["send_candidate_form_immediately"] = 0
		cfg["send_agreement_immediately"] = 0
		return cfg

	with patch.object(so_module, "get_erp_config", config):
		so.submit()


def _pay(c, ctx, orders):
	"""Raise invoices and payment entries against each order's terms, according to the customer's plan."""
	from verp_staffing.accounts.doctype.sales_order.sales_order import create_payment_entry_from_term, reject_payment_entry, verify_payment_entry

	region, plan = c["person"]["region"], c["plan"]
	acc, company = ctx["acc"].get(region), ctx["company"].get(region)
	if plan == "none" or not (acc and acc["banks"] and company):
		return
	currency = COMPANIES[region]["currency"]
	weights = BANK_WEIGHTS[region][: len(acc["banks"])]
	for order_no, (so_name, so_date) in enumerate(orders):
		so = frappe.get_doc("Sales Order", so_name)
		if so.docstatus != 1:
			continue
		terms = list(so.payment_terms)
		# what happens to term k of this order: verify | pending | reject | skip (left unpaid)
		actions = {
			"full": ["verify"] * len(terms),
			"partial": ["verify", "pending"] + ["skip"] * 5,
			"advance": ["verify"] + ["skip"] * 5,
			"pending": ["pending"] + ["skip"] * 5,
			"overdue": ["verify", "pending"] + ["skip"] * 5,
			"rejected": ["reject"] + ["skip"] * 5,
		}[plan]
		if order_no > 0 and plan in ("partial", "pending", "overdue", "rejected"):
			actions = ["verify"] + ["skip"] * 5  # only the latest order carries the awkward state
		day = getdate(so_date)
		for k, term in enumerate(terms):
			action = actions[k]
			if action == "skip":
				continue
			day = min(day + timedelta(days=random.randint(1, 12)), _ago(1) if action != "pending" else _today())
			ledger = random.choices(acc["banks"], weights=weights)[0]
			mode = _pick(MODES[region])
			ref = _reference(region, mode, day)
			payer = c["person"]["name"] if random.random() < 0.8 else _pick([f"{_pick(I_FIRST)} {c['person']['last']}", f"{c['person']['last']} Family Trust"])

			res = create_payment_entry_from_term(
				sales_order=so_name, payment_term_row=term.name, reference_no=ref, reference_date=str(day), remarks=f"Payment towards {term.description}",
				payer_account_name=payer, company=company, conversion_rate=1,
			)
			si, pe = res["invoice"], res["payment_entry"]
			_track("Sales Invoice", si)
			_track("Payment Entry", pe)
			due = day if action != "pending" or plan != "overdue" else _ago(random.randint(4, 20))
			_redate_invoice(si, day, due)
			frappe.db.set_value(
				"Payment Entry", pe,
				{"posting_date": str(day), "mode_of_payment": mode, "paid_from": acc["receivable"], "paid_from_account_currency": currency, "paid_to": ledger, "paid_to_account_currency": currency},
				update_modified=False,
			)
			_stamp("Payment Entry", pe, day)
			_stamp("Sales Invoice", si, day)
			if action == "verify":
				verify_payment_entry(pe, paid_from=acc["receivable"], paid_to=ledger)
			elif action == "reject":
				reject_payment_entry(pe, "Amount does not match the bank statement")
			if action == "pending" and plan == "overdue":
				frappe.db.set_value("Sales Invoice", si, "due_date", str(_ago(random.randint(4, 20))), update_modified=False)


def _reference(region, mode, day):
	stamp = day.strftime("%Y%m%d")
	return {
		"ACH Transfer": f"ACH{stamp}{random.randint(10000, 99999)}", "Wire Transfer": f"FED{stamp}{random.randint(100000, 999999)}",
		"Zelle": f"ZL{random.randint(10**9, 10**10 - 1)}", "Credit Card": f"CC-{random.randint(100000, 999999)}",
		"UPI": f"{random.randint(10**11, 10**12 - 1)}", "NEFT": f"NEFT{stamp}{random.randint(10**7, 10**8 - 1)}",
		"IMPS": f"{random.randint(10**11, 10**12 - 1)}", "RTGS": f"RTGS{stamp}{random.randint(10**7, 10**8 - 1)}",
	}[mode]


def _redate_invoice(si, day, due):
	"""Invoices are posted 'today' when raised from a term; move them (and their GL entries) to when they'd really have been."""
	frappe.db.set_value("Sales Invoice", si, {"posting_date": str(day), "due_date": str(due)}, update_modified=False)
	frappe.db.sql("update `tabGL Entry` set posting_date=%s where voucher_type='Sales Invoice' and voucher_no=%s", (str(day), si))


def _journal_entries(ctx):
	"""Rent, payroll, ad spend, subscriptions, bank charges, transfers between banks and one refund, per company."""
	specs = {
		"usa": {"rent": 4800, "payroll": 41500, "ads": [2600, 3100, 3400], "tools": 1150, "charges": 45, "capital": 250000, "transfer": 20000, "refund": 1500, "fee": 28},
		"india": {"rent": 95000, "payroll": 680000, "ads": [58000, 64000, 71000], "tools": 24500, "charges": 590, "capital": 2500000, "transfer": 300000, "refund": 45000, "fee": 236},
	}
	for region, company in ctx["company"].items():
		acc, s, currency = ctx["acc"][region], specs[region], COMPANIES[region]["currency"]
		if len(acc["banks"]) < 2:
			_errors.append(f"Journal Entry ({company}): needs at least two bank accounts")
			continue
		main, second = acc["banks"][0], acc["banks"][1]
		third = acc["banks"][2] if len(acc["banks"]) > 2 else second

		def line(account, debit, credit):
			return {"account": account, "account_currency": currency, "exchange_rate": 1, "debit_in_account_currency": debit, "debit": debit,
					"credit_in_account_currency": credit, "credit": credit}

		entries = []
		start = max(ctx["fy_start"], _ago(110))
		if acc["equity"]:
			entries.append((start, "Journal Entry", "Owner capital introduced", [line(main, s["capital"], 0), line(acc["equity"], 0, s["capital"])]))
		months = [(_today().replace(day=1) - timedelta(days=30 * m)).replace(day=1) for m in (3, 2, 1, 0)]
		for m in months:
			label = m.strftime("%B %Y")
			entries.append((m.replace(day=5), "Journal Entry", f"Office rent - {label}", [line(acc["rent"], s["rent"], 0), line(main, 0, s["rent"])]))
			if m < _today().replace(day=1):
				entries.append((m.replace(day=28), "Journal Entry", f"Payroll - {label}", [line(acc["salary"], s["payroll"], 0), line(main, 0, s["payroll"])]))
		for i, amount in enumerate(s["ads"]):
			entries.append((_ago(20 + i * 30), "Journal Entry", f"{'Google Ads' if i % 2 == 0 else 'LinkedIn Ads'} campaign - {_ago(20 + i * 30).strftime('%B %Y')}", [line(acc["marketing"], amount, 0), line(second, 0, amount)]))
		entries.append((_ago(35), "Journal Entry", "LinkedIn Recruiter and Google Workspace subscriptions", [line(acc["rent"], s["tools"], 0), line(second, 0, s["tools"])]))
		entries.append((_ago(12), "Journal Entry", f"Bank charges - {main.split(' (')[0]}", [line(acc["rent"], s["charges"], 0), line(main, 0, s["charges"])]))
		entries.append((_ago(28), "Bank Entry", f"Transfer to {third.split(' (')[0]}", [line(third, s["transfer"], 0), line(main, 0, s["transfer"])]))
		entries.append((_ago(15), "Bank Entry", f"Transfer to {second.split(' (')[0]}", [line(second, s["transfer"] // 2, 0), line(main, 0, s["transfer"] // 2)]))
		entries.append((_ago(9), "Journal Entry", "Refund issued to customer after CR review", [line(acc["income"], s["refund"], 0), line(main, 0, s["refund"])]))

		for day, voucher_type, remark, lines in entries:
			day = max(day, ctx["fy_start"])
			if day > _today():
				continue

			def make(day=day, voucher_type=voucher_type, remark=remark, lines=lines):
				values = {"doctype": "Journal Entry", "voucher_type": voucher_type, "company": company, "posting_date": str(day), "user_remark": remark, "accounts": lines}
				if voucher_type == "Bank Entry":  # a bank entry needs its reference
					values.update({"cheque_no": f"TRF{day.strftime('%y%m%d')}{random.randint(100, 999)}", "cheque_date": str(day)})
				doc = frappe.get_doc(values)
				_insert(doc)
				doc.submit()
				_stamp("Journal Entry", doc.name, day)

			_attempt(f"Journal Entry '{remark}' ({company})", make)
	_flush_tracks()
	frappe.db.commit()


def _activity(ctx):
	"""Follow-up tasks and calendar events on leads and opportunities."""
	users = [u for u in ctx["user"].values() if u]
	targets = [("Opportunity", c["opportunity"]) for c in ctx["customers"] if c.get("opportunity")]
	targets += [("Lead", name) for name in frappe.get_all("Lead", pluck="name", limit=40, order_by="creation desc")]
	if not (users and targets):
		return
	tasks = ["Send updated profile to the candidate", "Follow up on interview feedback", "Confirm availability for next week", "Share the rate card and plan options", "Collect ID and visa documents", "Check payment status with accounts", "Schedule the onboarding call"]
	for i in range(40):
		ref, name = _pick(targets)
		done = random.random() < 0.4
		_attempt(
			f"CRM Task {i}",
			lambda ref=ref, name=name, done=done: _insert(
				frappe.get_doc(
					{"doctype": "CRM Task", "description": _pick(tasks), "date": f"{add_days(_today(), random.randint(-20, -1) if done else random.randint(-5, 12))} {_pick(['09', '11', '14', '16'])}:00:00",
					 "assigned_to": _pick(users), "reference_doctype": ref, "related_to": name, "is_completed": int(done)}
				)
			),
		)
	for i in range(25):
		ref, name = _pick(targets)
		category = _pick(["Meeting", "Call", "Follow Up", "Event"])
		person = frappe.db.get_value(ref, name, "name1") or name
		_attempt(
			f"CRM Event {i}",
			lambda ref=ref, name=name, category=category, person=person: _insert(
				frappe.get_doc(
					{"doctype": "CRM Event", "category": category, "date": f"{add_days(_today(), random.randint(-10, 14))} {_pick(['10', '11', '13', '15'])}:00:00",
					 "assigned_to": _pick(users), "summary": f"{category}: {person}", "reference_doctype": ref, "related_to": name}
				)
			),
		)
	_flush_tracks()
	frappe.db.commit()


# -- one customer ------------------------------------------------------------


def _customer_journey(c, ctx):
	"""Each step under its own savepoint, so one failing step doesn't lose the rest."""
	stage, status = c["stage"], c["status"]
	customer = c["customer"]
	steps = []
	if stage in ("marketing", "jdc", "onboarding", "placed", "cr"):
		with_marketing = stage != "cr" or c["index"] % 2 == 0
		if with_marketing:
			m_status = {"onboarding": "Completed", "placed": "Completed", "jdc": "Started"}.get(stage, status if stage == "marketing" else "Started")
			steps += [("marketing", lambda: _marketing(c, ctx, m_status)), ("interviews", lambda: _interviews(c, ctx, "offer" if stage in ("onboarding", "placed") else "mix"))]
	if stage in ("resume", "onboarding", "placed") or (stage == "marketing" and c["index"] % 3 == 0):
		steps.append(("resume", lambda: _resume_services(c, ctx, status if stage == "resume" else "Completed")))
	if stage == "technical":
		steps.append(("technical", lambda: _technical_services(c, ctx, status)))
	if stage == "jdc":
		steps.append(("jdc", lambda: _jdc(c, ctx)))
	if stage == "cr":
		steps.append(("cr", lambda: _cr(c, ctx, status)))
	if stage in ("onboarding", "placed"):
		steps.append(("onboarding", lambda: _onboarding(c, ctx, completed=stage == "placed")))

	for label, step in steps:
		_attempt(f"{label} for {customer}", step)

	def money():
		orders = _create_sales_orders(c, ctx)
		_pay(c, ctx, orders)

	_attempt(f"sales for {customer}", money)

	def overall():
		from verp_staffing.crm.api.customer_overall_status import compute_customer_status

		frappe.db.set_value("Customer", customer, "overall_status", compute_customer_status(customer), update_modified=False)

	_attempt(f"overall status for {customer}", overall)
	frappe.db.commit()


def _track_service_records(ctx):
	"""Everything forward_candidate / the forwards created for our customers goes into the sample-data log."""
	customers = [c["customer"] for c in ctx["customers"]]
	if not customers:
		return
	for doctype in ("Marketing", "Resume", "Cover Letter", "RUC", "Training", "JDC", "Interview Support", "CR", "Onboardings", "Marketing Other Services", "Other Services", "Technical Other Services"):
		try:
			for name in frappe.get_all(doctype, {"customer": ["in", customers]}, pluck="name"):
				_track(doctype, name)
		except Exception:
			continue
	for so, in frappe.db.sql("select name from `tabSales Order` where customer in %(c)s", {"c": customers}):
		_track("Sales Order", so)
	_flush_tracks()


# -- entry points ------------------------------------------------------------


def run(force=0):
	"""Seed everything. Prints what was made and anything that failed."""
	if frappe.db.get_global(MARKER) and not cint(force):
		print("Documentation data was already seeded on this site. Pass force=1 to add another batch.")
		return {}
	if not frappe.db.count("Department") or not frappe.db.exists("Role", "Sales Master Manager"):
		print("Departments/roles are missing: finish the app's install/setup first.")
		return {}

	frappe.flags.in_sample_data_import = True
	frappe.flags.mute_emails = True
	frappe.flags.mute_messages = True
	frappe.set_user("Administrator")
	_errors.clear()
	ctx = {}
	try:
		with patch("frappe.enqueue"), patch("frappe.sendmail"):
			for label, fn in (
				("Banks, modes of payment, lead sources", _ensure_config),
				("Companies and bank accounts", lambda: _ensure_companies(ctx)),
				("Staff and hierarchy", lambda: _create_staff(ctx)),
			):
				print(f"  {label} ...")
				fn()
			ctx["pdf"] = _attempt("sample pdf", _sample_pdf) or ""
			print("  Leads, opportunities, customers ...")
			_create_crm(ctx)
			customers = ctx["customers"]
			print(f"    {frappe.db.count('Lead')} leads, {frappe.db.count('Opportunity')} opportunities, {len(customers)} customers")
			for i, c in enumerate(sorted(customers, key=lambda x: -x["days"])):
				c["index"] = i
				c["stage"], c["status"], _plan = c["plan"][0], c["plan"][1], c["plan"][2]
				c["plan"] = _plan
				c["active_days"] = max(min(c["days"] - 3, 75), 10)
				print(f"  [{i + 1}/{len(customers)}] {c['person']['name']} ({c['stage']})", end="\r")
				_customer_journey(c, ctx)
			print()
			print("  Journal entries ...")
			_journal_entries(ctx)
			print("  Tasks and events ...")
			_activity(ctx)
			_track_service_records(ctx)
		frappe.db.set_global(MARKER, "1")
		frappe.db.commit()
	finally:
		frappe.flags.in_sample_data_import = False
		frappe.flags.mute_emails = False
		frappe.flags.mute_messages = False
		frappe.set_user("Administrator")

	summary = {dt: frappe.db.count(dt) for dt in ("User", "Employee", "Lead", "Opportunity", "Customer", "Marketing", "Interview", "Sales Order", "Sales Invoice", "Payment Entry", "Journal Entry", "Bank Account")}
	print("\nCounts now:", ", ".join(f"{k} {v}" for k, v in summary.items()))
	if _errors:
		print(f"\n{len(_errors)} step(s) failed (full traces are in the Error Log):")
		for e in _errors[:40]:
			print("  -", e)
	else:
		print("No failures.")
	return summary


def after_migrate():
	"""Runs the seed on `bench migrate` when site_config has "seed_documentation_data": 1. A failure never blocks the migrate."""
	if not frappe.conf.get("seed_documentation_data") or frappe.db.get_global(MARKER):
		return
	if not frappe.db.count("Department"):
		return
	try:
		run()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Documentation seed failed", message=frappe.get_traceback())
