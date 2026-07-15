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
"""

import random

import frappe
from frappe import _
from frappe.utils import add_days, today, random_string


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

SAMPLE_SUPPLIERS = [
	("Sample Supplier 1", "Company"),
	("Sample Supplier 2", "Company"),
	("Sample Supplier 3", "Individual"),
]


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _get_or_create(doctype, filters, values=None):
	"""Return an existing doc matching filters, or insert a new one."""
	name = frappe.db.exists(doctype, filters)
	if name:
		return frappe.get_doc(doctype, name if isinstance(name, str) else filters)

	doc = frappe.get_doc({"doctype": doctype, **(values or {}), **filters})
	doc.insert(ignore_permissions=True)
	return doc


def _safe(step_name, fn, *args, **kwargs):
	"""Run a seeding step, log and continue on failure (never abort the
	whole run because one section hit a missing master/config)."""
	try:
		return fn(*args, **kwargs)
	except Exception:
		frappe.log_error(
			title=f"Sample Data: {step_name} failed",
			message=frappe.get_traceback(),
		)
		return None


def _default_currency(company):
	return company.default_currency or "INR"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def create_sample_data(company):
	"""Seed the whole demo data set for `company` (a Company doc)."""

	employees = _safe(
		"Users & Employees", create_users_and_employees, DEPARTMENT_MAP
	)
	if not employees:
		return

	_safe("Administrator Employee", create_administrator_employee, DEPARTMENT_MAP, employees)

	leads = _safe("Leads", create_leads, employees) or []

	opportunities = _safe(
		"Opportunities", create_opportunities, employees, leads
	) or []

	customers = _safe(
		"Customers", create_customers, employees, leads, opportunities
	) or []

	# THIS WAS MISSING: SAMPLE_ITEMS are just names - they need to exist
	# as real Item records before anything can link to them.
	items = _safe("Sample Items", create_sample_items) or []

	if customers and items:
		_safe(
			"Sales Order", create_sales_order, company, customers[0], items
		)
		_safe("Sales Invoices", create_sales_invoices, company, customers, items)

	suppliers = _safe("Suppliers", create_suppliers) or []

	purchase_orders = _safe(
		"Purchase Orders", create_purchase_orders, company, suppliers, items
	) or []

	purchase_invoices = _safe(
		"Purchase Invoices", create_purchase_invoices, company, suppliers, items
	) or []

	sales_invoices = frappe.get_all(
		"Sales Invoice", filters={"docstatus": 1}, pluck="name"
	)

	_safe(
		"Payment Entries",
		create_payment_entries,
		company,
		sales_invoices,
		purchase_orders,
		purchase_invoices,
	)

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
	department, holding every department role."""

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
		doc.insert(ignore_permissions=True)
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
		doc.insert(ignore_permissions=True)
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
		doc.insert(ignore_permissions=True)
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
		doc.insert(ignore_permissions=True)
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
		doc.insert(ignore_permissions=True)
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
		doc.insert(ignore_permissions=True)
		customers.append(doc.name)

	return customers


# ---------------------------------------------------------------------------
# 3. Items - THE MISSING PIECE. SAMPLE_ITEMS are just names; Sales/Purchase
# Order & Invoice item rows link to real Item records, so those records
# have to exist before anything else references them.
# ---------------------------------------------------------------------------

def _get_or_create_leaf_category(name="Services"):
	"""Item Category is almost always a tree doctype - inserting a bare
	node without parent_item_category throws MandatoryError. Reuse an
	existing leaf category if one exists; only create one as a child of
	the tree root otherwise."""

	existing = frappe.db.get_value("Item Category", {"item_category_name": name}, "name")
	if existing:
		return existing

	existing_leaf = frappe.db.get_value("Item Category", {"is_group": 0}, "name")
	if existing_leaf:
		return existing_leaf

	root = frappe.db.get_value("Item Category", {"is_group": 1}, "name") or frappe.db.get_value(
		"Item Category", {}, "name"
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

def _service_items_table(items, doc_type="Sales"):
	rows = []
	for item_name in items:
		rate = random.choice([5000, 7500, 10000, 15000])
		rows.append(
			{
				"item": item_name,
				"type": doc_type,
				"qty": 1,
				"rate": rate,
				"amount": rate,
			}
		)
	return rows


def _sample_tax_row(account_head, rate=10):
	return {
		"charge_type": "On Net Total",
		"account_head": account_head,
		"rate": rate,
	}


def _get_or_create_tax_account(company, label):
	name = frappe.db.exists("Account", {"account_name": label, "company": company.name})
	if name:
		return name

	# Account is a tree doctype - a bare insert without parent_account /
	# root_type / account_type throws MandatoryError. Reuse an existing
	# leaf account under this company rather than guessing at your Chart
	# of Accounts structure; only create one as a last resort.
	existing_leaf = frappe.db.get_value(
		"Account", {"company": company.name, "is_group": 0}, "name"
	)
	if existing_leaf:
		return existing_leaf

	parent = frappe.db.get_value(
		"Account", {"company": company.name, "is_group": 1}, "name"
	)
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
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _safe_tax_row(company, label, step_name):
	"""Tax account creation failing should not take the whole order down
	with it - return no tax rows instead of aborting."""
	try:
		account = _get_or_create_tax_account(company, label)
		return [_sample_tax_row(account)]
	except Exception:
		frappe.log_error(
			title=f"Sample Data: {step_name} tax account skipped",
			message=frappe.get_traceback(),
		)
		return []


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
			"items": _service_items_table(items),
			"taxes": taxes,
		}
	)
	so.insert(ignore_permissions=True)  # left in draft, as requested
	return so.name


def create_sales_invoices(company, customers, items):
	if not items:
		return []

	invoices = []
	for customer in customers[:2]:
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"posting_date": today(),
				"items": _service_items_table(items),
			}
		)
		si.insert(ignore_permissions=True)
		si.submit()
		invoices.append(si.name)

	return invoices


# ---------------------------------------------------------------------------
# 5. Supplier -> Purchase Order (submitted) -> Purchase Invoice (submitted)
# ---------------------------------------------------------------------------

def create_suppliers():
	suppliers = []
	for name, supplier_type in SAMPLE_SUPPLIERS:
		doc = _get_or_create(
			"Supplier",
			{"supplier_name": name},
			{"supplier_type": supplier_type},
		)
		suppliers.append(doc.name)
	return suppliers


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
				"items": _service_items_table(items, doc_type="Purchase"),
				"taxes": taxes,
			}
		)
		po.insert(ignore_permissions=True)
		po.submit()
		orders.append(po.name)

	return orders


def create_purchase_invoices(company, suppliers, items):
	if not suppliers or not items:
		return []

	taxes = _safe_tax_row(company, "Input GST", "Purchase Invoice")

	invoices = []
	for supplier in suppliers[:2]:
		pi = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"bill_no": f"BILL-{random_string(5).upper()}",
				"bill_date": add_days(today(), -3),
				"items": _service_items_table(items, doc_type="Purchase"),
				"taxes": taxes,
			}
		)
		pi.insert(ignore_permissions=True)
		pi.submit()
		invoices.append(pi.name)

	return invoices


# ---------------------------------------------------------------------------
# 6. Payment Entry, referencing Sales Invoice / Purchase Order / Purchase Invoice
# ---------------------------------------------------------------------------

def _doc_total(doctype, name):
	"""Best-effort total for a submitted doc from its items table, since
	the schema you shared doesn't expose a grand_total field explicitly.
	Swap this out for doc.grand_total if that field exists in your app."""
	doc = frappe.get_doc(doctype, name)
	return sum(row.amount for row in doc.get("items", []))


def create_payment_entries(company, sales_invoices, purchase_orders, purchase_invoices):
	currency = _default_currency(company)

	references = []
	references += [("Sales Invoice", n, "Receive") for n in sales_invoices]
	references += [("Purchase Order", n, "Pay") for n in purchase_orders]
	references += [("Purchase Invoice", n, "Pay") for n in purchase_invoices]

	entries = []
	for doctype, name, payment_type in references:
		total = _doc_total(doctype, name) or 0

		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": payment_type,
				"company": company.name,
				"currency": currency,
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
		pe.insert(ignore_permissions=True)
		pe.submit()
		entries.append(pe.name)

	return entries