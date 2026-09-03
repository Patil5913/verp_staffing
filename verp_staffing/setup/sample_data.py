"""
Sample data seeding for verp_staffing.

Mirrors the strategy ERPNext uses for its own "Add a few sample records"
setup-wizard checkbox: a single entry point (create_sample_data) that is
only ever called when the user opts in, builds everything through
frappe.get_doc(...).insert(ignore_permissions=True), and is written so that
a failure in one section (e.g. missing Item Category, missing Account)
does not take down the rest of the seed run - each logical block is wrapped
and logged via frappe.log_error, exactly like erpnext.demo does.

Order of creation follows the dependency chain requested:
	Employees (incl. Administrator, using pre-existing Departments/Roles)
	-> Lead
	-> Opportunity (direct + from Lead)
	-> Customer (direct + from Lead/Opportunity)
	-> Item (service items referenced by Orders/Invoices below)
	-> Sales Order (draft)
	-> Sales Invoice (submitted)
	-> Supplier
	-> Purchase Order (submitted)
	-> Purchase Invoice (submitted)
	-> Payment Entry (submitted, referencing Sales Invoice / Purchase Order /
	   Purchase Invoice)

Every record actually inserted below (as opposed to reused via
get-or-create) is logged through insert_tracked()/track() from
verp_staffing.utils.sample_data_tracking, so "Remove Sample Data" on
ERP Configuration knows exactly what it's safe to delete later without
having to guess from the record name.
"""

import random
import frappe
from frappe import _
from frappe.utils import add_days, today, random_string
from verp_staffing.utils.sample_data_tracking import insert_tracked, track


DEPARTMENT_MAP = {
	"Lead": {
		"department": "Lead",
		"role": "Lead Master Manager",
	},
	"Sales": {
		"department": "Sales",
		"role": "Sales Master Manager",
	},
	"Marketing": {
		"department": "Marketing",
		"role": "Marketing Master Manager",
	},
	"Resume": {
		"department": "Resume",
		"role": "Senior Resume Person",
	},
	"HR": {
		"department": "HR",
		"role": "HR Manager",
	},
	"Technical": {
		"department": "Technical",
		"role": "Technical Master Manager",
	},
	"CR": {
		"department": "CR",
		"role": "CR",
	},
	"Onboarding": {
		"department": "Onboarding",
		"role": "OnBoarding Person",
	},
	"Accounting": {
		"department": "Accounting",
		"role": "Account Person",
	},
}

# NOTE: these are Item *names*. They get created below via
# create_sample_items() - they are not assumed to pre-exist. If you already
# maintain these as fixtures elsewhere, create_sample_items() will just
# reuse the existing records (it's get-or-create, not insert-always).
SAMPLE_ITEMS = ["Marketing", "Cover Letter", "Resume", "Training", "JDC", "RUC"]

SAMPLE_LEADS = ["Sample Lead 1", "Sample Lead 2", "Sample Lead 3", "Sample Lead 4", "Sample Lead 5"]

SAMPLE_ROLES = ["Software Engineer", "Data Analyst", "QA Engineer", "DevOps Engineer", "Business Analyst"]


SAMPLE_SUPPLIERS = [
	("Sample Supplier 1", "Company"),
	("Sample Supplier 2", "Company"),
	("Sample Supplier 3", "Individual"),
]

ITEM_SERVICE_DOCTYPE_MAP = {
	"Marketing": ("Marketing", "Marketing"),
	"Resume": ("Resume", "Resume"),
	"Cover Letter": ("Cover Letter", "Resume"),
	"Training": ("Training", "Technical"),
	"RUC": ("RUC", "Technical"),
	# "JDC" intentionally omitted - no doctype provided for it yet.
}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _get_any_existing(doctype):
	return frappe.db.get_value(doctype, {}, "name")

def _get_or_create_service_doc(doctype, customer, employees, dept):
	existing = frappe.db.exists(doctype, {"customer": customer})
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": doctype,
			"customer": customer,
			"assign_to": employees.get(dept),
			"status": "Pending",
		}
	)
	insert_tracked(doc)
	return doc.name


def create_service_records_for_sales_order(customer, items, employees):
	created = []

	for item_name in items:
		mapping = ITEM_SERVICE_DOCTYPE_MAP.get(item_name)
		if not mapping:
			continue

		doctype, dept = mapping
		name = _get_or_create_service_doc(doctype, customer, employees, dept)
		created.append(name)

		if doctype == "Marketing":
			interviews = _safe("Interviews", create_interviews_for_marketing, name)
			created.extend(interviews or [])

	return created

def _get_or_create(doctype, filters, values=None, track_as_sample=True):
	"""Return an existing doc matching filters, or insert a new one.

	track_as_sample=False is for callers that reuse this get-or-create
	helper for something that ISN'T actually sample data (see
	create_administrator_employee below) - without it, this helper had
	no way to opt out and was logging the real Administrator's own
	Employee record as removable sample data."""
	name = frappe.db.exists(doctype, filters)
	if name:
		return frappe.get_doc(doctype, name if isinstance(name, str) else filters)

	doc = frappe.get_doc({"doctype": doctype, **(values or {}), **filters})
	if track_as_sample:
		insert_tracked(doc)
	else:
		doc.insert(ignore_permissions=True)
	return doc


def _rollback_to_new_savepoint(fn, on_error_title, *args, **kwargs):
	"""Run fn under a fresh SAVEPOINT and, on failure, roll back only to
	that savepoint - not the whole transaction. Sample data seeding now
	runs inside the single request-wide transaction the setup wizard
	uses (see setup_wizard.py - there is no manual commit boundary
	before this runs anymore). A bare frappe.db.rollback() here would
	silently wipe the Company and Fiscal Year created earlier in that
	same request, not just this step's own partial writes - which is
	exactly the bug a mid-request commit was previously (wrongly)
	papering over.
	"""
	savepoint = f"sd_{frappe.generate_hash(length=10)}"
	frappe.db.savepoint(savepoint)
	try:
		return fn(*args, **kwargs)
	except Exception:
		frappe.log_error(title=on_error_title, message=frappe.get_traceback())
		frappe.db.rollback(save_point=savepoint)
		return None


def _safe(step_name, fn, *args, **kwargs):
	"""Run a seeding step, log and continue on failure (never abort the
	whole run because one section hit a missing master/config).
	Rolls back to a savepoint taken just before this step, not the
	whole transaction - see _rollback_to_new_savepoint above."""
	return _rollback_to_new_savepoint(
		fn, f"Sample Data: {step_name} failed", *args, **kwargs
	)


def _default_currency(company):
	return company.default_currency or "INR"


def _get_or_create_tree_root(doctype, root_name, name_field, extra=None):
	"""Tree (NestedSet) doctypes need a group root to exist before any
	leaf can be inserted under it. On a fresh site with zero records for
	the doctype, there's nothing to attach to - this creates that root
	node once, get-or-create style."""
	existing = frappe.db.get_value(doctype, {"is_group": 1}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": doctype,
			name_field: root_name,
			"is_group": 1,
			**(extra or {}),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _get_company_default_account(company, fieldname, account_type=None):
	"""Prefer the Company's own default_* account field (default_receivable_
	account, default_payable_account, etc. - all real fields on Company);
	fall back to any leaf Account of the right type for this company.
	Returns None (never throws) if nothing suitable exists, so callers can
	decide whether to skip rather than crash."""
	account = company.get(fieldname)
	if account:
		return account

	filters = {"company": company.name, "is_group": 0}
	if account_type:
		filters["account_type"] = account_type
	return frappe.db.get_value("Account", filters, "name")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def create_sample_data(company):
	"""Seed the whole demo data set for `company` (a Company doc)."""
	frappe.flags.in_sample_data_import = True
	employees = _safe(
		"Users & Employees", create_users_and_employees, DEPARTMENT_MAP
	)
	if not employees:
		return

	_safe("Administrator Employee", create_administrator_employee, DEPARTMENT_MAP, employees)
	frappe.db.commit()

	leads = _safe("Leads", create_leads, employees) or []
	opportunities = _safe("Opportunities", create_opportunities, employees, leads) or []
	customers = _safe("Customers", create_customers, employees, leads, opportunities) or []
	frappe.db.commit()  # CRM data secured even if anything below fails hard

	# THIS WAS MISSING: SAMPLE_ITEMS are just names - they need to exist
	# as real Item records before anything can link to them.
	items = _safe("Sample Items", create_sample_items) or []
	frappe.db.commit()

	if customers and items:
		so_name = _safe("Sales Order", create_sales_order, company, customers[0], items)
		if so_name:
			_safe(
				"Service Records",
				create_service_records_for_sales_order,
				customers[0],
				items,
				employees,
			)
		_safe("Sales Invoices", create_sales_invoices, company, customers, items)
		frappe.db.commit()

	suppliers = _safe("Suppliers", create_suppliers) or []
	frappe.db.commit()

	purchase_orders = []
	purchase_invoices = []
	if suppliers and items:
		purchase_orders = _safe(
			"Purchase Orders", create_purchase_orders, company, suppliers, items
		) or []
		purchase_invoices = _safe(
			"Purchase Invoices", create_purchase_invoices, company, suppliers, items
		) or []
		frappe.db.commit()

	# NEW: Subscription Plan / Subscription
	plan = _safe("Subscription Plan", create_subscription_plan, company, items)
	_safe("Subscriptions", create_subscriptions, company, customers, suppliers, plan)
	frappe.db.commit()

	sales_invoices = frappe.get_all("Sales Invoice", filters={"docstatus": 1}, pluck="name")
	_safe(
		"Payment Entries",
		create_payment_entries,
		company,
		sales_invoices,
		purchase_orders,
		purchase_invoices,
	)
	frappe.db.commit()

	_safe("Journal Entries", create_journal_entries, company, employees)
	frappe.flags.in_sample_data_import = False
	frappe.db.commit()


# ---------------------------------------------------------------------------
# 1. Users, Employees (Departments & Roles assumed to already exist)
# ---------------------------------------------------------------------------

def create_users_and_employees(department_map):
	"""One User + one Employee per department, Employee.designation is set
	to that department's role, per your Employee Assignment Detail schema
	(designation options="Role"). Assumes the Department and Role records
	named in department_map already exist."""

	employees = {}

	for dept_name, info in department_map.items():
		email = f"{dept_name.lower().replace(' ', '_')}@example.com"

		user = _get_or_create(
			"User",
			{"name": email},
			{
				"email": email,
				"first_name": dept_name,
				"send_welcome_email": 0,
			},
		)

		# grant the department role to the user so permissions line up
		# with the Employee's assignment below
		if info["role"] not in [r.role for r in user.get("roles", [])]:
			user.append("roles", {"role": info["role"]})
			user.save(ignore_permissions=True)

		employee = _get_or_create(
			"Employee",
			{"user": user.name},
			{
				"employee_name": f"{dept_name}",
				"enabled": 1,
				"employee_assignment_details_table": [
					{
						"department": info["department"],
						"designation": info["role"],
					}
				],
			},
		)

		employees[dept_name] = employee.name

	return employees


def create_administrator_employee(department_map, employees):
	"""Administrator becomes an Employee with one assignment row per
	department, holding every department role.

	Deliberately NOT tracked as sample data: this is the real
	Administrator's own Employee record, not a demo entity, so
	"Remove Sample Data" should never touch it."""

	admin_user = "Administrator"

	assignment_rows = []
	for dept_name, info in department_map.items():
		assignment_rows.append(
			{
				"department": info["department"],
				"designation": info["role"],
			}
		)

	admin_employee = _get_or_create(
		"Employee",
		{"user": admin_user},
		{
			"employee_name": "Administrator",
			"enabled": 1,
			"employee_assignment_details_table": assignment_rows,
		},
		track_as_sample=False,
	)

	return admin_employee.name


# ---------------------------------------------------------------------------
# 2. Lead -> Opportunity -> Customer
# ---------------------------------------------------------------------------

def create_leads(employees):
	lead_owner = employees.get("Lead")
	leads = []

	for name in SAMPLE_LEADS:
		doc = frappe.get_doc(
			{
				"doctype": "Lead",
				"name1": name,
				"lead_owner": lead_owner,
			}
		)
		insert_tracked(doc)
		leads.append(doc.name)

	return leads


def create_opportunities(employees, leads):
	sales_owner = employees.get("Sales")
	opportunities = []

	# a couple of opportunities created directly
	for name in ["Sample Opportunity 1", "Sample Opportunity 2"]:
		doc = frappe.get_doc(
			{
				"doctype": "Opportunity",
				"name1": name,
				"opportunity_owner": sales_owner,
			}
		)
		insert_tracked(doc)
		opportunities.append(doc.name)

	# and a couple converted from existing leads
	for lead_name in leads[:2]:
		doc = frappe.get_doc(
			{
				"doctype": "Opportunity",
				"name1": f"Opportunity from {lead_name}",
				"opportunity_owner": sales_owner,
				"opportunity_from_lead": lead_name,
			}
		)
		insert_tracked(doc)
		opportunities.append(doc.name)

	return opportunities


def create_customers(employees, leads, opportunities):
	sales_owner = employees.get("Sales")
	customers = []

	# direct customers, no lead/opportunity reference
	for name in ["Sample Customer 1", "Sample Customer 2"]:
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"name1": name,
				"customer_owner": sales_owner,
			}
		)
		insert_tracked(doc)
		customers.append(doc.name)

	# customer created off the back of a Lead
	if leads:
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"name1": f"{leads[0]} (via Lead)",
				"customer_from": "Lead",
				"party_name": leads[0],
				"customer_owner": sales_owner,
			}
		)
		insert_tracked(doc)
		customers.append(doc.name)

	# customer created off the back of an Opportunity
	if opportunities:
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"name1": f"{opportunities[0]} (via Opportunity)",
				"customer_from": "Opportunity",
				"party_name": opportunities[0],
				"customer_owner": sales_owner,
			}
		)
		insert_tracked(doc)
		customers.append(doc.name)

	return customers


# ---------------------------------------------------------------------------
# 3. Items - Item Category is a tree (NestedSet) doctype. On a completely
# fresh site there is no root node to attach a leaf category to yet, which
# is exactly what was breaking this step (and, by the `if items:` guards
# further down, silently skipping Sales Order/Invoice/Purchase Order/
# Purchase Invoice too - they all correctly refuse to run without real
# Item records).
#
# NOTE: Item Category itself is deliberately NOT tracked as sample data
# (see _get_or_create_leaf_category / _get_or_create_tree_root below) -
# it's shared structural setup, not a demo entity, and other real Items
# may depend on it after sample data is removed.
# ---------------------------------------------------------------------------

def _get_or_create_leaf_category(name="Services"):
	existing = frappe.db.get_value("Item Category", {"item_category_name": name}, "name")
	if existing:
		return existing

	existing_leaf = frappe.db.get_value("Item Category", {"is_group": 0}, "name")
	if existing_leaf:
		return existing_leaf

	# FIX: previously fell through to `root = None` here on a fresh site
	# (no group AND no ungrouped record to fall back to), then tried to
	# insert a leaf with parent_item_category=None - invalid for a
	# NestedSet doctype and the actual reason create_sample_items() (and
	# therefore everything downstream that needs Items) was failing.
	root = _get_or_create_tree_root(
		"Item Category", "All Item Categories", "item_category_name"
	)

	doc = frappe.get_doc(
		{
			"doctype": "Item Category",
			"item_category_name": name,
			"is_group": 0,
			"parent_item_category": root,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def create_sample_items():
	item_category = _get_or_create_leaf_category()

	item_names = []
	for item_name in SAMPLE_ITEMS:
		doc = _get_or_create(
			"Item",
			{"item_name": item_name},
			{
				"item_category": item_category,
				"is_service": 1,
			},
		)
		item_names.append(doc.name)

	return item_names


# ---------------------------------------------------------------------------
# 4. Sales Order (draft) / Sales Invoice (submitted)
# ---------------------------------------------------------------------------

def _service_items_table(items, company, doc_type="Sales"):
	rows = []

	if doc_type == "Sales":
		default_account = _get_company_default_account(
			company, "default_income_account", "Income Account"
		)
	else:
		default_account = _get_company_default_account(
			company, "default_expense_account", "Expense Account"
		)

	_ensure_account_currency(default_account, company)

	if not default_account:
		frappe.log_error(
			title="Sample Data: item rows missing account",
			message=f"No default {doc_type} account found for company {company.name}",
		)

	for item_name in items:
		rate = random.choice([5000, 7500, 10000, 15000])
		row = {
			"item": item_name,
			"type": doc_type,
			"qty": 1,
			"rate": rate,
			"amount": rate,
		}
		if doc_type == "Sales":
			row["income_account"] = default_account
		else:
			row["expense_account"] = default_account
		rows.append(row)

	return rows


def _sample_tax_row(account_head, rate=10):
	return {
		"charge_type": "On Net Total",
		"account_head": account_head,
		"rate": rate,
	}


def _account_currency(account, company):
	currency = frappe.db.get_value("Account", account, "account_currency")
	return currency or _default_currency(company)


def _ensure_account_currency(account, company):
	"""Sales Order's validate_account_currencies() throws outright if an
	account's account_currency isn't already set to company/doc currency -
	there's no fetch_from fallback for it like there is on Payment Entry.
	Normalize in place so any account we resolve (company default or one
	of our get-or-create fallbacks) always passes that check."""
	if not account:
		return
	if not frappe.db.get_value("Account", account, "account_currency"):
		frappe.db.set_value(
			"Account", account, "account_currency", _default_currency(company)
		)


def _get_or_create_tax_account(company, label):
	name = frappe.db.exists("Account", {"account_name": label, "company": company.name})
	if name:
		_ensure_account_currency(name, company)
		return name

	# FIX: previously fell back to *any* leaf account regardless of type,
	# and the create-new path never set account_type/account_currency at
	# all. Sales Order's validate_tax_accounts() requires account_type in
	# ["Tax", "Chargeable", "Expense"], and validate_account_currencies()
	# requires account_currency to be set - a generic or blank-typed
	# account silently fails both and _safe() eats the exception, which
	# is exactly what was killing every Sales Order after Customers.
	existing_tax_leaf = frappe.db.get_value(
		"Account",
		{
			"company": company.name,
			"is_group": 0,
			"account_type": ["in", ["Tax", "Chargeable"]],
		},
		"name",
	)
	if existing_tax_leaf:
		_ensure_account_currency(existing_tax_leaf, company)
		return existing_tax_leaf

	parent = frappe.db.get_value(
		"Account",
		{"company": company.name, "is_group": 1, "root_type": "Liability"},
		"name",
	) or frappe.db.get_value("Account", {"company": company.name, "is_group": 1}, "name")

	if not parent:
		frappe.throw(
			_("No Chart of Accounts found for company {0}; skipping tax account creation").format(
				company.name
			)
		)

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": label,
			"company": company.name,
			"parent_account": parent,
			"is_group": 0,
			"account_type": "Tax",
			"root_type": "Liability",
			"report_type": "Balance Sheet",
			"account_currency": _default_currency(company),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _safe_tax_row(company, label, step_name):
	"""Tax account creation failing should not take the whole order down
	with it - return no tax rows instead of aborting. Savepoint-scoped
	for the same reason as _safe() above."""

	def _create():
		account = _get_or_create_tax_account(company, label)
		return [_sample_tax_row(account)]

	result = _rollback_to_new_savepoint(
		_create, f"Sample Data: {step_name} tax account skipped"
	)
	return result or []


def create_sales_order(company, customer, items):
	if not items:
		return None

	currency = _default_currency(company)
	taxes = _safe_tax_row(company, "Output GST", "Sales Order")

	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"company": company.name,
			"posting_date": today(),
			"currency": currency,
			"items": _service_items_table(items, company),          # FIX
			"taxes": taxes,
		}
	)
	insert_tracked(so)
	return so.name


def create_purchase_orders(company, suppliers, items):
	if not suppliers or not items:
		return []

	currency = _default_currency(company)
	taxes = _safe_tax_row(company, "Input GST", "Purchase Order")

	orders = []
	for supplier in suppliers[:2]:
		po = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": supplier,
				"company": company.name,
				"currency": currency,
				"items": _service_items_table(items, company, doc_type="Purchase"),   # FIX
				"taxes": taxes,
			}
		)
		insert_tracked(po)
		po.submit()
		orders.append(po.name)

	return orders


def create_purchase_invoices(company, suppliers, items):
	if not suppliers or not items:
		return []

	currency = _default_currency(company)
	taxes = _safe_tax_row(company, "Input GST", "Purchase Invoice")

	credit_to = _get_company_default_account(company, "default_payable_account", "Payable")
	_ensure_account_currency(credit_to, company)   # was missing too — same currency check as SO
	if not credit_to:
		frappe.log_error(
			title="Sample Data: Purchase Invoices skipped",
			message=f"No payable account found for company {company.name}",
		)
		return []

	invoices = []
	for supplier in suppliers[:2]:
		pi = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"company": company.name,
				"currency": currency,
				"credit_to": credit_to,
				"bill_no": f"BILL-{random_string(5).upper()}",
				"bill_date": add_days(today(), -3),
				"items": _service_items_table(items, company, doc_type="Purchase"),   # FIX
				"taxes": taxes,
			}
		)
		insert_tracked(pi)
		pi.submit()
		invoices.append(pi.name)

	return invoices


def create_sales_invoices(company, customers, items):
	if not items:
		return []

	currency = _default_currency(company)
	debit_to = _get_company_default_account(company, "default_receivable_account", "Receivable")

	taxes = _safe_tax_row(company, "Input GST", "Purchase Invoice")

	invoices = []
	for customer in customers[:2]:
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"company": company.name,
				"currency": currency,
				"debit_to": debit_to,
				"posting_date": today(),
				"taxes": taxes,
				"items": _service_items_table(items, company),
			}
		)
		insert_tracked(si)
		si.submit()
		invoices.append(si.name)

	return invoices


# ---------------------------------------------------------------------------
# 5. Supplier -> Purchase Order (submitted) -> Purchase Invoice (submitted)
# ---------------------------------------------------------------------------

def create_suppliers():
	supplier_group = _get_or_create_supplier_group()

	suppliers = []
	for name, supplier_type in SAMPLE_SUPPLIERS:
		doc = _get_or_create(
			"Supplier",
			{"supplier_name": name},
			{"supplier_type": supplier_type, "supplier_group": supplier_group},
		)
		suppliers.append(doc.name)
	return suppliers


# ---------------------------------------------------------------------------
# 6. Payment Entry, referencing Sales Invoice / Purchase Order / Purchase Invoice
# ---------------------------------------------------------------------------

def _doc_total(doctype, name):
	"""Best-effort total for a submitted doc from its items table, since
	the schema you shared doesn't expose a grand_total field explicitly.
	Swap this out for doc.grand_total if that field exists in your app."""
	doc = frappe.get_doc(doctype, name)
	return sum(row.amount for row in doc.get("items", []))


def _party_for_reference(doctype, name):
	"""Sales Invoice references a Customer; Purchase Order/Invoice
	reference a Supplier. Payment Entry needs to know which, and who,
	before it can resolve paid_from/paid_to below."""
	if doctype == "Sales Invoice":
		return "Customer", frappe.db.get_value("Sales Invoice", name, "customer")
	return "Supplier", frappe.db.get_value(doctype, name, "supplier")


def _account_currency(account, company):
	"""Account.account_currency is optional in the schema (no default,
	not reqd) - fall back to the company currency if it was never set
	on the account itself."""
	currency = frappe.db.get_value("Account", account, "account_currency")
	return currency or _default_currency(company)


def create_payment_entries(company, sales_invoices, purchase_orders, purchase_invoices):
	currency = _default_currency(company)

	references = []
	references += [("Sales Invoice", n, "Receive") for n in sales_invoices]
	# references += [("Purchase Order", n, "Pay") for n in purchase_orders]
	references += [("Purchase Invoice", n, "Pay") for n in purchase_invoices]

	receivable = _get_company_default_account(company, "default_receivable_account", "Receivable")
	payable = _get_company_default_account(company, "default_payable_account", "Payable")
	cash_or_bank = _get_company_default_account(
		company, "default_bank_account", "Bank"
	) or _get_company_default_account(company, "default_cash_account", "Cash")

	entries = []
	for doctype, name, payment_type in references:
		party_type, party = _party_for_reference(doctype, name)
		if not party:
			continue

		if payment_type == "Receive":
			paid_from, paid_to = receivable, cash_or_bank
		else:
			paid_from, paid_to = cash_or_bank, payable

		if not paid_from or not paid_to:
			frappe.log_error(
				title="Sample Data: Payment Entry skipped",
				message=f"Missing default account(s) for company {company.name} "
				f"(payment_type={payment_type})",
			)
			continue

		total = _doc_total(doctype, name) or 0

		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": payment_type,
				"company": company.name,
				"currency": currency,
				"party_type": party_type,
				"party": party,
				"paid_from": paid_from,
				"paid_to": paid_to,
				# FIX: no fetch_from on these two fields in this app's
				# Payment Entry doctype (unlike paid_from_account_type /
				# paid_to_account_type, which do have fetch_from) - they
				# were never being populated, so submit() threw
				# MandatoryError on "Account Currency (From/To)".
				"paid_from_account_currency": _account_currency(paid_from, company),
				"paid_to_account_currency": _account_currency(paid_to, company),
				"paid_amount": total,
				"references": [
					{
						"reference_doctype": doctype,
						"reference_name": name,
						"total_amount": total,
						"outstanding_amount": total,
						"allocated_amount": total,
					}
				],
			}
		)
		insert_tracked(pe)
		pe.submit()
		entries.append(pe.name)

	return entries

def _get_or_create_supplier_group(name="Services"):
	existing = frappe.db.get_value("Supplier Group", {"supplier_group_name": name}, "name")
	if existing:
		return existing

	existing_any = frappe.db.get_value("Supplier Group", {}, "name")
	if existing_any:
		return existing_any

	doc = frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": name})
	doc.insert(ignore_permissions=True)
	return doc.name


def create_subscription_plan(company, items):
	if not items:
		return None

	item = frappe.get_doc("Item", items[0])
	currency = _default_currency(company)

	existing = frappe.db.exists("Subscription Plan", {"plan_name": item.item_name})
	if existing:
		return existing

	plan = frappe.get_doc(
		{
			"doctype": "Subscription Plan",
			"item": item.name,
			"plan_name": item.item_name,
			"rate": 5000,
			"currency": currency,
			"billing_interval": "Month",
			"billing_interval_count": 1,
		}
	)
	insert_tracked(plan)
	plan.submit()
	return plan.name


def create_subscriptions(company, customers, suppliers, plan):
	if not plan:
		return []

	subscriptions = []

	if customers:
		sub = frappe.get_doc(
			{
				"doctype": "Subscription",
				"subscription_type": "Sales",
				"party_type": "Customer",
				"party": customers[0],
				"company": company.name,
				"plan": plan,
				"qty": 1,
				"start_date": today(),
			}
		)
		insert_tracked(sub)
		sub.submit()
		subscriptions.append(sub.name)

	if suppliers:
		sub = frappe.get_doc(
			{
				"doctype": "Subscription",
				"subscription_type": "Purchase",
				"party_type": "Supplier",
				"party": suppliers[0],
				"company": company.name,
				"plan": plan,
				"qty": 1,
				"start_date": today(),
			}
		)
		insert_tracked(sub)
		sub.submit()
		subscriptions.append(sub.name)

	return subscriptions

def create_journal_entries(company, employees):
	debit_account = _get_company_default_account(company, "default_cash_account", "Cash") \
		or _get_company_default_account(company, "default_bank_account", "Bank")
	credit_account = _get_company_default_account(company, "default_income_account", "Income Account")

	_ensure_account_currency(debit_account, company)
	_ensure_account_currency(credit_account, company)

	if not debit_account or not credit_account:
		frappe.log_error(
			title="Sample Data: Journal Entry skipped",
			message=f"Missing default account(s) for company {company.name}",
		)
		return []

	amount = 50000

	je = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"company": company.name,
			"posting_date": today(),
			"accounts": [
				{
					"account": debit_account,
					"account_currency": _account_currency(debit_account, company),
					"exchange_rate": 1,                        # FIX: validate_exchange_rate requires this
					"debit_in_account_currency": amount,
					"debit": amount,                            # FIX: validate_debit_credit_not_zero
					"credit_in_account_currency": 0,            # runs before set_amounts() computes these
					"credit": 0,
				},
				{
					"account": credit_account,
					"account_currency": _account_currency(credit_account, company),
					"exchange_rate": 1,
					"debit_in_account_currency": 0,
					"debit": 0,
					"credit_in_account_currency": amount,
					"credit": amount,
				},
			],
		}
	)
	insert_tracked(je)
	je.submit()
	return [je.name]

def create_interviews_for_marketing(marketing_name):
	interview_status = _get_any_existing("Interview Status")
	if not interview_status:
		frappe.log_error(
			title="Sample Data: Interviews skipped",
			message="No 'Interview Status' record found - Interview.status is mandatory "
			"and this app doesn't expose a schema to create one.",
		)
		return []

	type_of_interview = _get_any_existing("Type Of Interview")

	interviews = []
	for i in range(2):
		doc = frappe.get_doc(
			{
				"doctype": "Interview",
				"marketing_link": marketing_name,
				"company": f"Sample Company {random_string(4).upper()}",  # plain Data field, not a Company link
				"role": random.choice(SAMPLE_ROLES),
				"status": interview_status,
			}
		)

		if type_of_interview:
			num_rounds = random.randint(4, 6)
			for r in range(1, num_rounds + 1):
				doc.append(
					"interview_rounds_table",
					{
						"round": f"Round {r}",
						"date_of_interview": add_days(today(), r),
						"type_of_interview": type_of_interview,
						"edt_est": "EDT",
						"follow_up": 0,
						"status": interview_status,
					},
				)
		else:
			frappe.log_error(
				title="Sample Data: Interview Rounds skipped",
				message="No 'Type Of Interview' record found - interview_rounds_table.type_of_interview "
				"is mandatory per row, so rounds were left empty for this Interview.",
			)

		insert_tracked(doc)
		interviews.append(doc.name)

	return interviews