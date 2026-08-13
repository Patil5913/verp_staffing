# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.helpers import get_reporting_subtree
from verp_staffing.employee.doctype.employee.employee import get_employee_from_user

CANCELLED_LIKE_STATUSES = {"Cancelled", "Rescheduled"}
FINAL_ROUND_STATUSES = {"Cancelled", "Rescheduled", "Completed"}
DEFAULT_ROUND_STATUS = "Scheduled"

class Interview(Document):
	def autoname(self):
		if not self.marketing_link:
			frappe.throw(_("Marketing is required"), frappe.ValidationError)

		if not frappe.db.exists("Marketing", self.marketing_link):
			frappe.throw(
				_("Marketing '{0}' does not exist").format(self.marketing_link),
				frappe.ValidationError,
			)

		customer = frappe.db.get_value("Marketing", self.marketing_link, "customer")
		if not customer:
			frappe.throw(
				_("The selected Marketing record has no linked Customer."),
				frappe.ValidationError,
			)

		customer_name = frappe.db.get_value("Customer", customer, "name1")
		self.name = generate_name_series("Interview", customer_name)

	def validate(self):
		self._validate_marketing_link()
		self._validate_required_fields()
		self._validate_interview_rounds()
		self._sync_status_from_last_round()

	# ------------------------------------------------------------------
	# Field-level validators
	# ------------------------------------------------------------------

	def _validate_marketing_link(self):
		if not self.marketing_link:
			frappe.throw(_("Marketing is required"), frappe.MandatoryError)

		if not frappe.db.exists("Marketing", self.marketing_link):
			frappe.throw(
				_("Marketing '{0}' does not exist").format(self.marketing_link),
				frappe.ValidationError,
			)

		customer = frappe.db.get_value("Marketing", self.marketing_link, "customer")
		if not customer:
			frappe.throw(
				_("The selected Marketing record has no linked Customer."),
				frappe.ValidationError,
			)

	def _validate_required_fields(self):
		if not self.company:
			frappe.throw(_("Company is required"), frappe.MandatoryError)

		if not self.role:
			frappe.throw(_("Role is required"), frappe.MandatoryError)

	def _validate_interview_rounds(self):
		"""Validate every row in the Interview Rounds child table."""

		rounds = self.interview_rounds_table or []

		for i, row in enumerate(rounds, start=1):
			if not row.date_of_interview:
				frappe.throw(
					_("Row #{0}: Date is required in Interview Rounds").format(i),
					frappe.ValidationError,
				)

			if not row.status:
				row.status = DEFAULT_ROUND_STATUS

			self._validate_round_status_not_locked(row, i)

			if (
				row.status in CANCELLED_LIKE_STATUSES
				and (not row.cancelled_by or not row.reason_of_cancel)
			):
				frappe.throw(
					_(
						"Row #{0}: 'Cancelled By' and 'Reason of Cancel' are "
						"required when status is '{1}'."
					).format(i, row.status),
					frappe.MandatoryError,
				)

			follow_up = row.follow_up or 0

			if not isinstance(follow_up, (int, float)) or int(follow_up) < 0:
				frappe.throw(
					_("Row #{0}: Follow Up must be a non-negative number").format(i),
					frappe.ValidationError,
				)

			if i > 1:
				prev_row = rounds[i - 2]
				prev_follow_up = prev_row.follow_up or 0

				if int(follow_up) not in (
					0,
					int(prev_follow_up),
					int(prev_follow_up) + 1,
				):
					frappe.throw(
						_(
							"Row #{0}: Follow Up value {1} is invalid. "
							"Only {2} or {3} is allowed."
						).format(
							i,
							follow_up,
							int(prev_follow_up),
							int(prev_follow_up) + 1,
						),
						frappe.ValidationError,
					)

	def _validate_round_status_not_locked(self, row, row_number):
		"""Prevent changing the status of a persisted terminal round.

		Uses the parent document's previous version instead of querying
		Interview Round directly from the database.
		"""
		if row.is_new():
			return

		doc_before_save = self.get_doc_before_save()

		if not doc_before_save:
			return

		previous_row = next(
			(
				prev_row
				for prev_row in doc_before_save.interview_rounds_table or []
				if prev_row.name == row.name
			),
			None,
		)

		if not previous_row:
			return

		if previous_row.status in FINAL_ROUND_STATUSES and row.status != previous_row.status:
			frappe.throw(
				_(
					"Row #{0}: This interview round is already '{1}' and its "
					"status cannot be changed."
				).format(row_number, previous_row.status),
				frappe.ValidationError,
		)

	def _sync_status_from_last_round(self):
		"""Interview.status is a derived field — it always mirrors the last
		Interview Round row (by child-table order), never edited directly.
		"""
		rounds = self.interview_rounds_table or []
		if not rounds:
			return

		last_round = max(rounds, key=lambda r: r.idx)
		self.status = last_round.status


# ---------------------------------------------------------------------------
# Kanban helpers
# ---------------------------------------------------------------------------

KANBAN_NAME = "Interview"


def add_to_kanban(doc, method):
	kb = frappe.get_doc("Kanban Board", KANBAN_NAME)
	if any(c.column_name == doc.status_name for c in kb.columns):
		return
	kb.append(
		"columns",
		{"column_name": doc.status_name, "indicator": "Blue", "status": "Active"},
	)
	kb.save(ignore_permissions=True)


def remove_from_kanban(doc, method):
	kb = frappe.get_doc("Kanban Board", KANBAN_NAME)
	kb.columns = [c for c in kb.columns if c.column_name != doc.status_name]
	kb.save(ignore_permissions=True)


def sync_kanban(doc, method):
	kb = frappe.get_doc("Kanban Board", KANBAN_NAME)
	for col in kb.columns:
		if col.column_name == doc.get_db_value("status_name"):
			col.column_name = doc.status_name
	kb.save(ignore_permissions=True)


def get_allowed_employee_ids(department):
	if frappe.session.user == "Administrator":
		return frappe.db.get_all("Employee", pluck="name")
	employee = get_employee_from_user(frappe.session.user)
	if not employee:
		return []
	return get_reporting_subtree(employee, department)


# ---------------------------------------------------------------------------
# Kanban status update — the ONLY path that should change Interview.status
# from the Kanban board. It writes to the last round row, then routes
# through `doc.save()` -> `validate()` so every rule above is enforced
# uniformly, exactly as it would be from the Form.
# ---------------------------------------------------------------------------


@frappe.whitelist()
def update_interview_status_from_kanban(interview, status, cancelled_by=None, reason_of_cancel=None):
	if not interview or not status:
		frappe.throw(_("Interview and status are required."))

	doc = frappe.get_doc("Interview", interview)

	if not doc.interview_rounds_table:
		frappe.throw(
			_("Cannot change status: {0} has no interview rounds yet.").format(interview)
		)

	last_round = max(doc.interview_rounds_table, key=lambda r: r.idx)

	if last_round.status in FINAL_ROUND_STATUSES and last_round.status != status:
		frappe.throw(
			_(
				"This interview round is already '{0}' and its status "
				"cannot be changed."
			).format(last_round.status)
		)

	if status in CANCELLED_LIKE_STATUSES:
		if not cancelled_by or not reason_of_cancel:
			frappe.throw(
				_("'Cancelled By' and 'Reason of Cancel' are required for this status.")
			)
		last_round.cancelled_by = cancelled_by
		last_round.reason_of_cancel = reason_of_cancel

	last_round.status = status
	doc.save()

	return {"name": doc.name, "status": doc.status}


# ---------------------------------------------------------------------------
# Kanban card data
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_round_summary_for_kanban(names):
	"""Return raw round data (not markup) per Interview, so the client is
	free to render/restyle without a round trip to the server.
	"""
	try:
		names = json.loads(names) if isinstance(names, str) else names
	except (ValueError, TypeError):
		frappe.throw(_("Invalid 'names' payload"), frappe.ValidationError)

	if not names or not isinstance(names, list):
		return {}

	rounds = frappe.get_all(
		"Interview Round",
		filters={"parenttype": "Interview", "parent": ["in", names]},
		fields=["parent", "round", "date_of_interview", "status"],
		order_by="parent asc, idx asc",
	)

	grouped = {name: [] for name in names}
	for row in rounds:
		grouped[row["parent"]].append(
			{"round": row["round"], "date_of_interview": row["date_of_interview"], "status": row["status"]}
		)

	return grouped


@frappe.whitelist()
def get_default_marketing_customer_options(param=""):
	department = "Marketing"
	conditions = []
	values = []

	if param:
		conditions.append("m.name = %s")
		values.append(param)

	if frappe.session.user != "Administrator":
		allowed_employees = get_allowed_employee_ids(department)
		if not allowed_employees:
			return []
		placeholders = ", ".join(["%s"] * len(allowed_employees))
		conditions.append(f"m.assign_to IN ({placeholders})")
		values.extend(allowed_employees)

	query = """
		SELECT m.name AS value, c.name AS label
		FROM `tabMarketing` m
		LEFT JOIN `tabCustomer` c ON c.name = m.customer
	"""
	if conditions:
		query += " WHERE " + " AND ".join(conditions)
	query += " ORDER BY m.creation DESC LIMIT 1"

	return frappe.db.sql(query, values, as_dict=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_marketing_customers(doctype, txt, searchfield, start, page_len, filters):
	department = "Marketing"
	conditions = []
	values = {"txt": f"%{txt}%", "start": start, "page_len": min(page_len or 50, 50)}

	if frappe.session.user != "Administrator":
		allowed_employees = get_allowed_employee_ids(department)
		if not allowed_employees:
			return []
		placeholders = []
		for idx, emp in enumerate(allowed_employees):
			key = f"emp_{idx}"
			placeholders.append(f"%({key})s")
			values[key] = emp
		conditions.append(f"m.assign_to IN ({', '.join(placeholders)})")

	conditions.append(
		"(c.name LIKE %(txt)s OR c.name1 LIKE %(txt)s OR m.name LIKE %(txt)s)"
	)

	query = """
		SELECT m.name, CONCAT(COALESCE(c.name1, ''))
		FROM `tabMarketing` m
		INNER JOIN `tabCustomer` c ON c.name = m.customer
		WHERE
	""" + " AND ".join(conditions) + """
		ORDER BY m.creation DESC
		LIMIT %(start)s, %(page_len)s
	"""

	return frappe.db.sql(query, values)