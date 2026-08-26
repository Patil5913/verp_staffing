# # Copyright (c) 2025, Vrugle and contributors
# # For license information, please see license.txt

# import json
# import frappe
# from frappe import _
# from frappe.model.document import Document
# from verp_staffing.crm.api.naming import generate_name_series
# from verp_staffing.crm.api.helpers import get_reporting_subtree
# from verp_staffing.employee.doctype.employee.employee import get_employee_from_user

# CANCELLED_LIKE_STATUSES = {"Cancelled", "Rescheduled"}
# FINAL_ROUND_STATUSES = {"Cancelled", "Rescheduled", "Completed"}
# DEFAULT_ROUND_STATUS = "Scheduled"


# class Interview(Document):
#     def autoname(self):
#         if not self.marketing_link:
#             frappe.throw(_("Marketing is required"), frappe.ValidationError)

#         if not frappe.db.exists("Marketing", self.marketing_link):
#             frappe.throw(
#                 _("Marketing '{0}' does not exist").format(self.marketing_link),
#                 frappe.ValidationError,
#             )

#         customer = frappe.db.get_value("Marketing", self.marketing_link, "customer")
#         if not customer:
#             frappe.throw(
#                 _("The selected Marketing record has no linked Customer."),
#                 frappe.ValidationError,
#             )

#         customer_name = frappe.db.get_value("Customer", customer, "name1")
#         self.name = generate_name_series("Interview", customer_name)

#     def validate(self):
#         self._validate_marketing_link()
#         self._validate_required_fields()
#         self._validate_interview_rounds()
#         self._sync_status_from_last_round()

#     # ------------------------------------------------------------------
#     # Field-level validators
#     # ------------------------------------------------------------------

#     def _validate_marketing_link(self):
#         if not self.marketing_link:
#             frappe.throw(_("Marketing is required"), frappe.MandatoryError)

#         if not frappe.db.exists("Marketing", self.marketing_link):
#             frappe.throw(
#                 _("Marketing '{0}' does not exist").format(self.marketing_link),
#                 frappe.ValidationError,
#             )

#         customer = frappe.db.get_value("Marketing", self.marketing_link, "customer")
#         if not customer:
#             frappe.throw(
#                 _("The selected Marketing record has no linked Customer."),
#                 frappe.ValidationError,
#             )

#     def _validate_required_fields(self):
#         if not self.company:
#             frappe.throw(_("Company is required"), frappe.MandatoryError)

#         if not self.role:
#             frappe.throw(_("Role is required"), frappe.MandatoryError)

#     def _validate_interview_rounds(self):
#         """Validate every row in the Interview Rounds child table."""

#         rounds = self.interview_rounds_table or []

#         for i, row in enumerate(rounds, start=1):
#             if not row.date_of_interview:
#                 frappe.throw(
#                     _("Row #{0}: Date is required in Interview Rounds").format(i),
#                     frappe.ValidationError,
#                 )

#             if not row.status:
#                 row.status = DEFAULT_ROUND_STATUS

#             self._validate_round_status_not_locked(row, i)

#             if row.status in CANCELLED_LIKE_STATUSES and (
#                 not row.cancelled_by or not row.reason_of_cancel
#             ):
#                 frappe.throw(
#                     _(
#                         "Row #{0}: 'Cancelled By' and 'Reason of Cancel' are "
#                         "required when status is '{1}'."
#                     ).format(i, row.status),
#                     frappe.MandatoryError,
#                 )

#             follow_up = row.follow_up or 0

#             if not isinstance(follow_up, (int, float)) or int(follow_up) < 0:
#                 frappe.throw(
#                     _("Row #{0}: Follow Up must be a non-negative number").format(i),
#                     frappe.ValidationError,
#                 )

#             if i > 1:
#                 prev_row = rounds[i - 2]
#                 prev_follow_up = prev_row.follow_up or 0

#                 if int(follow_up) not in (
#                     0,
#                     int(prev_follow_up),
#                     int(prev_follow_up) + 1,
#                 ):
#                     frappe.throw(
#                         _(
#                             "Row #{0}: Follow Up value {1} is invalid. "
#                             "Only {2} or {3} is allowed."
#                         ).format(
#                             i,
#                             follow_up,
#                             int(prev_follow_up),
#                             int(prev_follow_up) + 1,
#                         ),
#                         frappe.ValidationError,
#                     )

#     def _validate_round_status_not_locked(self, row, row_number):
#         """Prevent changing the status of a persisted terminal round.

#         Uses the parent document's previous version instead of querying
#         Interview Round directly from the database.
#         """
#         if row.is_new():
#             return

#         doc_before_save = self.get_doc_before_save()

#         if not doc_before_save:
#             return

#         previous_row = next(
#             (
#                 prev_row
#                 for prev_row in doc_before_save.interview_rounds_table or []
#                 if prev_row.name == row.name
#             ),
#             None,
#         )

#         if not previous_row:
#             return

#         if (
#             previous_row.status in FINAL_ROUND_STATUSES
#             and row.status != previous_row.status
#         ):
#             frappe.throw(
#                 _(
#                     "Row #{0}: This interview round is already '{1}' and its "
#                     "status cannot be changed."
#                 ).format(row_number, previous_row.status),
#                 frappe.ValidationError,
#             )

#     def _sync_status_from_last_round(self):
#         """Interview.status is a derived field — it always mirrors the last
#         Interview Round row (by child-table order), never edited directly.
#         """
#         rounds = self.interview_rounds_table or []
#         if not rounds:
#             return

#         last_round = max(rounds, key=lambda r: r.idx)
#         self.status = last_round.status


# # ---------------------------------------------------------------------------
# # Kanban helpers
# # ---------------------------------------------------------------------------

# KANBAN_NAME = "Interview"


# def add_to_kanban(doc, method):
#     kb = frappe.get_doc("Kanban Board", KANBAN_NAME)
#     if any(c.column_name == doc.status_name for c in kb.columns):
#         return
#     kb.append(
#         "columns",
#         {"column_name": doc.status_name, "indicator": "Blue", "status": "Active"},
#     )
#     kb.save(ignore_permissions=True)


# def remove_from_kanban(doc, method):
#     kb = frappe.get_doc("Kanban Board", KANBAN_NAME)
#     kb.columns = [c for c in kb.columns if c.column_name != doc.status_name]
#     kb.save(ignore_permissions=True)


# def sync_kanban(doc, method):
#     kb = frappe.get_doc("Kanban Board", KANBAN_NAME)
#     for col in kb.columns:
#         if col.column_name == doc.get_db_value("status_name"):
#             col.column_name = doc.status_name
#     kb.save(ignore_permissions=True)


# def get_allowed_employee_ids(department):
#     if frappe.session.user == "Administrator":
#         return frappe.db.get_all("Employee", pluck="name")
#     employee = get_employee_from_user(frappe.session.user)
#     if not employee:
#         return []
#     return get_reporting_subtree(employee, department)


# # ---------------------------------------------------------------------------
# # Kanban status update — the ONLY path that should change Interview.status
# # from the Kanban board. It writes to the last round row, then routes
# # through `doc.save()` -> `validate()` so every rule above is enforced
# # uniformly, exactly as it would be from the Form.
# # ---------------------------------------------------------------------------


# @frappe.whitelist()
# def update_interview_status_from_kanban(
#     interview, status, cancelled_by=None, reason_of_cancel=None
# ):
#     if not interview or not status:
#         frappe.throw(_("Interview and status are required."))

#     doc = frappe.get_doc("Interview", interview)

#     if not doc.interview_rounds_table:
#         frappe.throw(
#             _("Cannot change status: {0} has no interview rounds yet.").format(
#                 interview
#             )
#         )

#     last_round = max(doc.interview_rounds_table, key=lambda r: r.idx)

#     if last_round.status in FINAL_ROUND_STATUSES and last_round.status != status:
#         frappe.throw(
#             _(
#                 "This interview round is already '{0}' and its status "
#                 "cannot be changed."
#             ).format(last_round.status)
#         )

#     if status in CANCELLED_LIKE_STATUSES:
#         if not cancelled_by or not reason_of_cancel:
#             frappe.throw(
#                 _("'Cancelled By' and 'Reason of Cancel' are required for this status.")
#             )
#         last_round.cancelled_by = cancelled_by
#         last_round.reason_of_cancel = reason_of_cancel

#     last_round.status = status
#     doc.save()

#     return {"name": doc.name, "status": doc.status}


# # ---------------------------------------------------------------------------
# # Kanban card data
# # ---------------------------------------------------------------------------


# @frappe.whitelist()
# def get_round_summary_for_kanban(names):
#     """Return raw round data (not markup) per Interview, so the client is
#     free to render/restyle without a round trip to the server.
#     """
#     try:
#         names = json.loads(names) if isinstance(names, str) else names
#     except (ValueError, TypeError):
#         frappe.throw(_("Invalid 'names' payload"), frappe.ValidationError)

#     if not names or not isinstance(names, list):
#         return {}

#     rounds = frappe.get_all(
#         "Interview Round",
#         filters={"parenttype": "Interview", "parent": ["in", names]},
#         fields=["parent", "round", "date_of_interview", "status"],
#         order_by="parent asc, idx asc",
#     )

#     grouped = {name: [] for name in names}
#     for row in rounds:
#         grouped[row["parent"]].append(
#             {
#                 "round": row["round"],
#                 "date_of_interview": row["date_of_interview"],
#                 "status": row["status"],
#             }
#         )

#     return grouped


# @frappe.whitelist()
# def get_default_marketing_customer_options(param=""):
#     department = "Marketing"
#     conditions = []
#     values = []

#     if param:
#         conditions.append("m.name = %s")
#         values.append(param)

#     if frappe.session.user != "Administrator":
#         allowed_employees = get_allowed_employee_ids(department)
#         if not allowed_employees:
#             return []
#         placeholders = ", ".join(["%s"] * len(allowed_employees))
#         conditions.append(f"m.assign_to IN ({placeholders})")
#         values.extend(allowed_employees)

#     query = """
# 		SELECT m.name AS value, c.name AS label
# 		FROM `tabMarketing` m
# 		LEFT JOIN `tabCustomer` c ON c.name = m.customer
# 	"""
#     if conditions:
#         query += " WHERE " + " AND ".join(conditions)
#     query += " ORDER BY m.creation DESC LIMIT 1"

#     return frappe.db.sql(query, values, as_dict=True)


# @frappe.whitelist()
# @frappe.validate_and_sanitize_search_inputs
# def search_marketing_customers(doctype, txt, searchfield, start, page_len, filters):
#     department = "Marketing"
#     conditions = []
#     values = {"txt": f"%{txt}%", "start": start, "page_len": min(page_len or 50, 50)}

#     if frappe.session.user != "Administrator":
#         allowed_employees = get_allowed_employee_ids(department)
#         if not allowed_employees:
#             return []
#         placeholders = []
#         for idx, emp in enumerate(allowed_employees):
#             key = f"emp_{idx}"
#             placeholders.append(f"%({key})s")
#             values[key] = emp
#         conditions.append(f"m.assign_to IN ({', '.join(placeholders)})")

#     conditions.append(
#         "(c.name LIKE %(txt)s OR c.name1 LIKE %(txt)s OR m.name LIKE %(txt)s)"
#     )

#     query = (
#         """
# 		SELECT m.name, CONCAT(COALESCE(c.name1, ''))
# 		FROM `tabMarketing` m
# 		INNER JOIN `tabCustomer` c ON c.name = m.customer
# 		WHERE
# 	"""
#         + " AND ".join(conditions)
#         + """
# 		ORDER BY m.creation DESC
# 		LIMIT %(start)s, %(page_len)s
# 	"""
#     )

#     return frappe.db.sql(query, values)


# def _build_conditions(filters):
#     conditions, values = "", {}
#     if filters:
#         if isinstance(filters, str):
#             filters = json.loads(filters)
#         for f in filters or []:
#             if len(f) == 4:
#                 fieldname, operator, value = f[1], f[2], f[3]
#             elif len(f) == 3:
#                 fieldname, operator, value = f[0], f[1], f[2]
#             else:
#                 continue
#             if fieldname in ("company", "role", "status", "marketing_link") and operator == "=":
#                 conditions += f" AND i.{fieldname} = %({fieldname})s"
#                 values[fieldname] = value
#     return conditions, values


# @frappe.whitelist()
# def get_interview_round_events(start, end, filters=None, marketing_link=None):
#     # Calendar event source.
# 	conditions, values = _build_conditions(filters)

# 	if marketing_link:
# 		conditions += " AND i.marketing_link = %(marketing_link)s"
# 		values["marketing_link"] = marketing_link

# 	values.update({"start": start, "end": end})

# 	rounds = frappe.db.sql(f"""
# 		SELECT ir.name AS round_name, ir.parent AS interview, ir.round,
# 			ir.date_of_interview, ir.from_time, ir.to_time, ir.edt_est,
# 			ir.status AS round_status, i.company, i.role, i.status AS interview_status
# 		FROM `tabInterview Round` ir
# 		INNER JOIN `tabInterview` i ON i.name = ir.parent
# 		WHERE ir.date_of_interview BETWEEN %(start)s AND %(end)s
# 		{conditions}
# 		ORDER BY ir.date_of_interview, ir.from_time
# 	""", values, as_dict=True)

# 	events = []
# 	for r in rounds:
# 		has_time = bool(r.from_time and r.to_time)
# 		status = r.round_status or r.interview_status or ""
# 		events.append({
# 			"name": r.interview,
# 			"subject": f"{r.company} — {r.role} (Round {r.round})",
# 			"start": f"{r.date_of_interview} {r.from_time or '09:00:00'}",
# 			"end": f"{r.date_of_interview} {r.to_time or '10:00:00'}",
# 			"allDay": 0 if has_time else 1,
# 			"status": status,
# 			"company": r.company,
# 			"role": r.role,
# 			"round": r.round,
# 			"from_time": r.from_time,
# 			"to_time": r.to_time,
# 			"edt_est": r.edt_est,
# 		})
# 	return events


# @frappe.whitelist()
# def get_interview_gantt_rows(filters=None):
#     """
#     One row per Interview Round, with a GLOBALLY UNIQUE id (the round's
#     own child-table name). This is deliberate: Frappe's list-row keying
#     collapses rows that share the same `name`, which is exactly why
#     multiple rounds under one Interview were previously rendering as a
#     single bar. Because the id is now a Round's id (not a valid
#     Interview document name), the client side handles click-routing
#     itself via the bar's data-id attribute rather than relying on
#     Gantt's default navigate-by-id behaviour.
#     """
#     conditions, values = _build_conditions(filters)

#     rows = frappe.db.sql(
#         f"""
# 		SELECT
# 			ir.name AS round_id, ir.parent AS interview, ir.round,
# 			ir.date_of_interview, ir.from_time, ir.to_time, ir.edt_est,
# 			ir.status AS round_status,
# 			i.company, i.role, i.status AS interview_status,
# 			i.docstatus AS docstatus, i.owner AS owner
# 		FROM `tabInterview Round` ir
# 		INNER JOIN `tabInterview` i ON i.name = ir.parent
# 		WHERE ir.date_of_interview IS NOT NULL
# 		{conditions}
# 		ORDER BY ir.date_of_interview, ir.from_time
# 	""",
#         values,
#         as_dict=True,
#     )

#     out = []
#     for r in rows:
#         status = r.round_status or r.interview_status or ""
#         start_dt = f"{r.date_of_interview} {r.from_time or '09:00:00'}"
#         end_dt = f"{r.date_of_interview} {r.to_time or '10:00:00'}"
#         if end_dt <= start_dt:
#             end_dt = f"{r.date_of_interview} 23:59:00"

#         out.append(
#             {
#                 "name": r.round_id,  # unique per bar (fixes collapsing)
#                 "interview": r.interview,  # for client-side click routing
#                 "owner": r.owner,
#                 "docstatus": r.docstatus or 0,
#                 "status": status,
#                 "company": r.company,
#                 "role": r.role,
#                 "round": r.round,
#                 "date_of_interview": str(r.date_of_interview),
#                 "subject": f"{r.company} — {r.role} · Round {r.round} · {status}",
#                 "from_time": r.from_time,
#                 "to_time": r.to_time,
#                 "edt_est": r.edt_est,
#                 "start": start_dt,
#                 "end": end_dt,
#                 "_assign": "[]",
#                 "_liked_by": "[]",
#                 "_comments": "[]",
#                 "_user_tags": "",
#             }
#         )
#     return out


# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.helpers import (
    get_reporting_subtree,
    get_visible_user_names_cached,
)
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

            if row.status in CANCELLED_LIKE_STATUSES and (
                not row.cancelled_by or not row.reason_of_cancel
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

        if (
            previous_row.status in FINAL_ROUND_STATUSES
            and row.status != previous_row.status
        ):
            frappe.throw(
                _(
                    "Row #{0}: This interview round is already '{1}' and its "
                    "status cannot be changed."
                ).format(row_number, previous_row.status),
                frappe.ValidationError,
            )

    def _sync_status_from_last_round(self):
        rounds = self.interview_rounds_table or []
        if not rounds:
            return

        last_round = max(rounds, key=lambda r: r.idx)
        self.status = last_round.status


# ---------------------------------------------------------------------------
# Kanban board sync (unrelated to visibility scoping — kept as-is)
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
# Permission floor for Interview — registered in hooks.py:
#   permission_query_conditions = {
#       "Interview": "verp_staffing.marketing.doctype.interview.interview.interview_query",
#   }
#
# IMPORTANT: this ONLY affects ORM-based fetches (frappe.get_list/get_all,
# frappe.desk.reportview.get, frappe.client.get_list — which is what List
# view, Kanban's infinite-scroll pagination, and Report view all use).
# It does NOT apply to raw frappe.db.sql() queries — that's why
# get_interview_round_events (Calendar) and get_interview_gantt_rows
# (Gantt) below now build the SAME owner-scoping condition manually. Those
# two were previously unscoped by ownership entirely, regardless of what
# the client sent.
# ---------------------------------------------------------------------------


def interview_query(user):
    if user == "Administrator":
        return ""

    visible_users = get_visible_user_names_cached()
    if not visible_users:
        return "1=0"

    users_sql = ", ".join([frappe.db.escape(u) for u in visible_users])
    return f"`tabInterview`.owner IN ({users_sql})"


def _owner_scoping_sql_condition():
    """Same rule as interview_query, usable inside raw SQL (`i` alias)."""
    if frappe.session.user == "Administrator":
        return ""

    visible_users = get_visible_user_names_cached()
    if not visible_users:
        return " AND 1=0"

    users_sql = ", ".join([frappe.db.escape(u) for u in visible_users])
    return f" AND i.owner IN ({users_sql})"


# ---------------------------------------------------------------------------
# Kanban status update
# ---------------------------------------------------------------------------


@frappe.whitelist()
def update_interview_status_from_kanban(
    interview, status, cancelled_by=None, reason_of_cancel=None
):
    if not interview or not status:
        frappe.throw(_("Interview and status are required."))

    doc = frappe.get_doc("Interview", interview)

    if not doc.interview_rounds_table:
        frappe.throw(
            _("Cannot change status: {0} has no interview rounds yet.").format(
                interview
            )
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


@frappe.whitelist()
def get_round_summary_for_kanban(names):
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
            {
                "round": row["round"],
                "date_of_interview": row["date_of_interview"],
                "status": row["status"],
            }
        )

    return grouped


# ---------------------------------------------------------------------------
# Marketing-customer options
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_assigned_marketing_customers():
    """Every Marketing/Customer pair the current user is allowed to pick in
    the multi-select "Filter Interviews by Customer(s)" dialog. This is the
    single source of truth for two things:
      1. Populating the dialog's checkbox list.
      2. The client's "nothing selected yet" default — ivw_ensure_marketing_param()
         calls this and defaults to ALL of them (true "select all"), rather
         than the old single-most-recent-customer default.
    """
    department = "Marketing"
    conditions = []
    values = []

    if frappe.session.user != "Administrator":
        allowed_employees = get_allowed_employee_ids(department)
        if not allowed_employees:
            return []
        placeholders = ", ".join(["%s"] * len(allowed_employees))
        conditions.append(f"m.assign_to IN ({placeholders})")
        values.extend(allowed_employees)

    query = """
		SELECT m.name AS value, c.name1 AS label
		FROM `tabMarketing` m
		LEFT JOIN `tabCustomer` c ON c.name = m.customer
	"""
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY m.creation DESC"

    rows = frappe.db.sql(query, values, as_dict=True)
    for r in rows:
        r["label"] = r["label"] or r["value"]
    return rows


@frappe.whitelist()
def get_default_marketing_customer_options(param=""):
    # Retained for backward compatibility (label lookup by exact name/s).
    # New flow prefers get_assigned_marketing_customers() for both the
    # dialog and the "select all" default.
    department = "Marketing"
    conditions = []
    values = []

    if param:
        try:
            names = json.loads(param) if param.strip().startswith("[") else [param]
        except (ValueError, TypeError):
            names = [param]
        placeholders = ", ".join(["%s"] * len(names))
        conditions.append(f"m.name IN ({placeholders})")
        values.extend(names)

    if frappe.session.user != "Administrator":
        allowed_employees = get_allowed_employee_ids(department)
        if not allowed_employees:
            return []
        placeholders = ", ".join(["%s"] * len(allowed_employees))
        conditions.append(f"m.assign_to IN ({placeholders})")
        values.extend(allowed_employees)

    query = """
		SELECT m.name AS value, c.name1 AS label
		FROM `tabMarketing` m
		LEFT JOIN `tabCustomer` c ON c.name = m.customer
	"""
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY m.creation DESC"
    if not param:
        query += " LIMIT 1"

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

    query = (
        """
		SELECT m.name, CONCAT(COALESCE(c.name1, ''))
		FROM `tabMarketing` m
		INNER JOIN `tabCustomer` c ON c.name = m.customer
		WHERE
	"""
        + " AND ".join(conditions)
        + """
		ORDER BY m.creation DESC
		LIMIT %(start)s, %(page_len)s
	"""
    )

    return frappe.db.sql(query, values)


def _build_conditions(filters):
    """Builds SQL conditions from a Frappe-style filter list.

    Supports both:
      ["fieldname", "=", value]               (or 4-tuple with doctype)
      ["fieldname", "in", [v1, v2, ...]]       -- NEW: multi-customer support

    IN-list values are escaped and inlined directly as literals (via
    frappe.db.escape) rather than passed as %(name)s placeholders, since a
    variable-length IN(...) doesn't map cleanly onto a single dict key the
    way a scalar "=" filter does. Every value going into an IN clause is
    escaped individually, so this is safe against injection the same way
    frappe.db.escape is used everywhere else in this file.
    """
    conditions, values = "", {}
    if filters:
        if isinstance(filters, str):
            filters = json.loads(filters)
        for f in filters or []:
            if len(f) == 4:
                fieldname, operator, value = f[1], f[2], f[3]
            elif len(f) == 3:
                fieldname, operator, value = f[0], f[1], f[2]
            else:
                continue

            if fieldname not in ("company", "role", "status", "marketing_link"):
                continue

            operator = (operator or "=").lower()

            if operator == "in":
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (ValueError, TypeError):
                        value = [value]
                value = [v for v in (value or []) if v]
                if not value:
                    continue
                escaped = ", ".join(frappe.db.escape(v) for v in value)
                conditions += f" AND i.{fieldname} IN ({escaped})"
            elif operator == "=":
                conditions += f" AND i.{fieldname} = %({fieldname})s"
                values[fieldname] = value
    return conditions, values


@frappe.whitelist()
def get_interview_round_events(start, end, filters=None, marketing_link=None):
    conditions, values = _build_conditions(filters)

    if marketing_link:
        try:
            links = json.loads(marketing_link) if isinstance(marketing_link, str) and marketing_link.strip().startswith("[") else (
                marketing_link if isinstance(marketing_link, list) else [marketing_link]
            )
        except (ValueError, TypeError):
            links = [marketing_link]
        links = [l for l in links if l]
        if links:
            escaped = ", ".join(frappe.db.escape(l) for l in links)
            conditions += f" AND i.marketing_link IN ({escaped})"

    conditions += _owner_scoping_sql_condition()

    values.update({"start": start, "end": end})

    rounds = frappe.db.sql(f"""
        SELECT ir.name AS round_name, ir.parent AS interview, ir.round,
            ir.date_of_interview, ir.from_time, ir.to_time, ir.edt_est,
            ir.status AS round_status, i.company, i.role, i.status AS interview_status,
            i.marketing_link, COALESCE(c.name1, i.marketing_link) AS customer_name
        FROM `tabInterview Round` ir
        INNER JOIN `tabInterview` i ON i.name = ir.parent
        LEFT JOIN `tabMarketing` mk ON mk.name = i.marketing_link
        LEFT JOIN `tabCustomer` c ON c.name = mk.customer
        WHERE ir.date_of_interview BETWEEN %(start)s AND %(end)s
        {conditions}
        ORDER BY ir.date_of_interview, ir.from_time
    """, values, as_dict=True)

    events = []
    for r in rounds:
        has_time = bool(r.from_time and r.to_time)
        status = r.round_status or r.interview_status or ""
        events.append({
            "name": r.interview,
            "subject": f"{r.company} — {r.role} (Round {r.round})",
            "start": f"{r.date_of_interview} {r.from_time or '09:00:00'}",
            "end": f"{r.date_of_interview} {r.to_time or '10:00:00'}",
            "allDay": 0 if has_time else 1,
            "status": status,
            "company": r.company,
            "role": r.role,
            "round": r.round,
            "from_time": r.from_time,
            "to_time": r.to_time,
            "edt_est": r.edt_est,
            "customer": r.customer_name,  # NEW
        })
    return events


@frappe.whitelist()
def get_interview_gantt_rows(filters=None):
    conditions, values = _build_conditions(filters)
    conditions += _owner_scoping_sql_condition()

    rows = frappe.db.sql(
        f"""
        SELECT
            ir.name AS round_id, ir.parent AS interview, ir.round,
            ir.date_of_interview, ir.from_time, ir.to_time, ir.edt_est,
            ir.status AS round_status,
            i.company, i.role, i.status AS interview_status,
            i.docstatus AS docstatus, i.owner AS owner, i.marketing_link,
            COALESCE(c.name1, i.marketing_link) AS customer_name
        FROM `tabInterview Round` ir
        INNER JOIN `tabInterview` i ON i.name = ir.parent
        LEFT JOIN `tabMarketing` mk ON mk.name = i.marketing_link
        LEFT JOIN `tabCustomer` c ON c.name = mk.customer
        WHERE ir.date_of_interview IS NOT NULL
        {conditions}
        ORDER BY ir.date_of_interview, ir.from_time
        """,
        values,
        as_dict=True,
    )

    out = []
    for r in rows:
        status = r.round_status or r.interview_status or ""
        start_dt = f"{r.date_of_interview} {r.from_time or '09:00:00'}"
        end_dt = f"{r.date_of_interview} {r.to_time or '10:00:00'}"
        if end_dt <= start_dt:
            end_dt = f"{r.date_of_interview} 23:59:00"

        out.append({
            "name": r.round_id,
            "interview": r.interview,
            "owner": r.owner,
            "docstatus": r.docstatus or 0,
            "status": status,
            "company": r.company,
            "role": r.role,
            "round": r.round,
            "date_of_interview": str(r.date_of_interview),
            "subject": f"{r.company} — {r.role} · Round {r.round} · {status}",
            "from_time": r.from_time,
            "to_time": r.to_time,
            "edt_est": r.edt_est,
            "start": start_dt,
            "end": end_dt,
            "customer": r.customer_name,  # NEW
            "_assign": "[]",
            "_liked_by": "[]",
            "_comments": "[]",
            "_user_tags": "",
        })
    return out