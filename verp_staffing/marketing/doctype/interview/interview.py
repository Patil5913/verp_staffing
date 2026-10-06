# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.utils.timezone import convert_round, normalize_round, round_day, user_time_zone
from verp_staffing.crm.api.helpers import (
    get_reporting_subtree,
    get_visible_employee_names_cached,
    get_visible_user_names_cached,
)
from verp_staffing.employee.doctype.employee.employee import get_employee_from_user
from verp_staffing.utils.user_security import is_admin

LOCKED_STATUS_KEYWORDS = (
    "cancelled",
    "canceled",
    "completed",
    "rescheduled",
    "rejected",
)
CANCELLED_LIKE_KEYWORDS = ("cancelled", "canceled", "rescheduled")
CANCELLED_LIKE_STATUSES = {"Cancelled", "Rescheduled"}
FINAL_ROUND_STATUSES = {"Cancelled", "Rescheduled", "Completed"}
DEFAULT_ROUND_STATUS = "Scheduled"
TODAY_STATUS = "Today"
# A Completed round is still waiting on the company's answer, so it may move on to one of these
# (and only these); every other final status stays locked.
COMPLETED_OUTCOMES = {"Get The Offer", "Rejected"}
# An interview whose latest round is in one of these is over — never shown as "Today".
TODAY_EXCLUDED_STATUSES = FINAL_ROUND_STATUSES | {"Rejected", "Get The Offer", TODAY_STATUS}


def _is_outcome_of_completed(previous, new):
    return previous == "Completed" and new in COMPLETED_OUTCOMES


def is_status_locked(status):
    if not status or not isinstance(status, str):
        return False
    lower = status.lower()
    return any(keyword in lower for keyword in LOCKED_STATUS_KEYWORDS)


def is_cancelled_like_status(status):
    if not status or not isinstance(status, str):
        return False
    lower = status.lower()
    return any(keyword in lower for keyword in CANCELLED_LIKE_KEYWORDS)


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
        self._set_default_status()
        self.set_customer_from_marketing()
        self._validate_marketing_link()
        self._validate_required_fields()
        self._validate_interview_rounds()
        self._sync_status_from_last_round()

    def _set_default_status(self):
        """A new Interview with no status gets ERP Configuration's Default Interview Status
        (the form fills it in too; this covers every other way of creating one)."""
        if self.is_new() and not self.status:
            self.status = frappe.db.get_single_value("ERP Configuration", "default_interview_status") or None

    def set_customer_from_marketing(self):
        """Interview.customer is a cached, denormalized copy of
        Marketing.customer's name1, kept in sync here on every save so
        Gantt/Calendar (and anything else that needs the customer's
        display name against a large batch of rounds) can read it straight
        off the Interview row instead of joining Marketing -> Customer on
        every single fetch. This is the single place that field is ever
        written — never edit it directly.
        """
        if not self.marketing_link:
            self.customer = None
            return

        customer_name = frappe.db.get_value(
            "Marketing", self.marketing_link, "customer"
        )
        if not customer_name:
            self.customer = None
            return

        name1 = frappe.db.get_value("Customer", customer_name, "name1")
        self.customer = name1 or None

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
            normalize_round(row, self._previous_round(row))

            if is_cancelled_like_status(row.status) and (
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

    def _previous_round(self, row):
        before = self.get_doc_before_save()
        if row.is_new() or not before:
            return None
        return next((r for r in before.interview_rounds_table or [] if r.name == row.name), None)

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
            and not _is_outcome_of_completed(previous_row.status, row.status)
            and not is_admin()
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


def _owner_scoping_sql_condition():
    if frappe.session.user == "Administrator":
        return ""

    visible_users = get_visible_user_names_cached()
    if not visible_users:
        return " AND 1=0"

    users_sql = ", ".join([frappe.db.escape(u) for u in visible_users])
    condition = f"i.owner IN ({users_sql})"

    # Same reach as interview_query: also the interviews of Marketing records assigned inside the team
    team = get_visible_employee_names_cached()
    if team:
        team_sql = ", ".join([frappe.db.escape(e) for e in team])
        condition += (
            f" OR i.marketing_link IN (SELECT m.name FROM `tabMarketing` m WHERE m.assign_to IN ({team_sql}))"
        )
    return f" AND ({condition})"


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

    if status == TODAY_STATUS:
        frappe.throw(
            _("'Today' is worked out automatically from the round's date and can't be set by hand.")
        )

    last_round = max(doc.interview_rounds_table, key=lambda r: r.idx)

    if (
        last_round.status in FINAL_ROUND_STATUSES
        and last_round.status != status
        and not _is_outcome_of_completed(last_round.status, status)
        and not is_admin()
    ):
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
# "Today" — derived, never stored
# ---------------------------------------------------------------------------
# An interview with a round dated today (that isn't over) shows as
# "Today" in the list and on the Kanban. Nothing is written back: the stored
# status stays what the round says, so there's no "Today" to un-set later.
# One indexed query over just today's rounds (bounded by a day's interviews),
# rather than touching every interview.


def _todays_interview_names(names=None):
    """Interviews with a still-open round dated today (any round — an earlier
    one can be today while a later one is already booked). "Today" is the
    company's day. Rounds are stored in the company zone, so this is a plain date
    match; a round still in another zone (the company zone was changed later) is moved first."""
    today = frappe.utils.getdate(frappe.utils.today())
    query = """
        SELECT r.parent, r.date_of_interview, r.from_time, r.time_zone
        FROM `tabInterview Round` r
        INNER JOIN `tabInterview` i ON i.name = r.parent
        WHERE r.parenttype = 'Interview'
          AND r.date_of_interview BETWEEN %(day_before)s AND %(day_after)s
          AND IFNULL(r.status, '') NOT IN %(excluded)s
          AND IFNULL(i.status, '') NOT IN %(excluded)s
    """
    values = {"day_before": frappe.utils.add_days(today, -1), "day_after": frappe.utils.add_days(today, 1), "excluded": tuple(TODAY_EXCLUDED_STATUSES)}
    if names:
        query += " AND r.parent IN %(names)s"
        values["names"] = tuple(names)
    rows = frappe.db.sql(query, values, as_dict=True)
    return {r.parent for r in rows if round_day(r.date_of_interview, r.from_time, r.time_zone) == today}


def _status_wanted(filters):
    """Pulls plain `status = x` / `status in [...]` conditions out of `filters`
    (dict, or [field, op, value] / [doctype, field, op, value] lists).
    Returns (remaining filters as a list, wanted status set or None)."""
    filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
    rest, wanted = [], None

    def take(values):
        nonlocal wanted
        values = set(values)
        wanted = values if wanted is None else wanted & values

    if isinstance(filters, dict):
        items = []
        for field, cond in filters.items():
            if isinstance(cond, (list, tuple)) and len(cond) == 2:
                items.append([field, cond[0], cond[1]])
            else:
                items.append([field, "=", cond])
    else:
        items = list(filters or [])

    for item in items:
        field, op, value = (item[1], item[2], item[3]) if len(item) == 4 else (item[0], item[1], item[2])
        op = str(op).lower()
        if field == "status" and op == "=":
            take([value])
        elif field == "status" and op == "in":
            take(value if isinstance(value, (list, tuple)) else str(value).split(","))
        else:
            rest.append(item)
    return rest, wanted


def _interview_query_args(filters):
    """(filters, or_filters, empty) for get_list, with the status filters
    translated to the derived "Today" status."""
    rest, wanted = _status_wanted(filters)
    if wanted is None:
        return rest, None, False, set()

    today = _todays_interview_names()
    if TODAY_STATUS in wanted:
        others = wanted - {TODAY_STATUS}
        if others:
            or_filters = [["name", "in", list(today) or [""]], ["status", "in", list(others)]]
            return rest, or_filters, False, today
        if not today:
            return rest, None, True, today
        return rest + [["name", "in", list(today)]], None, False, today

    out = rest + [["status", "in", list(wanted)]]
    if today:
        out.append(["name", "not in", list(today)])
    return out, None, False, today


@frappe.whitelist()
def get_interview_list(
    fields=None, filters=None, order_by=None, limit_start=0, limit_page_length=20
):
    """frappe.client.get_list for Interview, with status = "Today" derived."""
    fields = frappe.parse_json(fields) if isinstance(fields, str) else fields
    filters, or_filters, empty, _today = _interview_query_args(filters)
    if empty:
        return []

    rows = frappe.get_list(
        "Interview",
        fields=fields or ["name"],
        filters=filters,
        or_filters=or_filters,
        order_by=order_by,
        limit_start=frappe.utils.cint(limit_start),
        limit_page_length=frappe.utils.cint(limit_page_length),
    )
    if rows and any("status" in r for r in rows):
        today = _todays_interview_names([r["name"] for r in rows if r.get("name")])
        for r in rows:
            if r.get("name") in today:
                r["status"] = TODAY_STATUS
    return rows


@frappe.whitelist()
def get_interview_count(filters=None):
    filters, or_filters, empty, _today = _interview_query_args(filters)
    if empty:
        return 0
    rows = frappe.get_list(
        "Interview",
        fields=["count(name) as total"],
        filters=filters,
        or_filters=or_filters,
        limit_page_length=0,
    )
    return rows[0].total if rows else 0


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
        fields=["parent", "round", "round_title", "date_of_interview", "from_time", "time_zone", "status"],
        order_by="parent asc, idx asc",
    )

    tz = user_time_zone()
    grouped = {name: [] for name in names}
    for row in rounds:
        local = convert_round(row["date_of_interview"], row["from_time"], None, row["time_zone"], tz)
        grouped[row["parent"]].append(
            {
                "round": row["round"],
                "round_title": row["round_title"],
                "date_of_interview": local["date"] or row["date_of_interview"],
                "status": row["status"],
            }
        )

    return grouped


# ---------------------------------------------------------------------------
# Marketing-customer options
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_assigned_marketing_customers(txt="", start=0, page_length=0):
    """Every Marketing/Customer pair the current user is allowed to pick.

    Two callers, two modes:
      1. ivw_ensure_marketing_param() (client) calls this with NO args —
         page_length stays 0/falsy, so this returns the FULL assigned list
         unpaginated. That's what makes "nothing selected yet" default to
         a true "select all".
      2. The multi-select dialog calls this with an explicit txt/start/
         page_length for its own searchable, paginated, scroll-to-load-more
         list — the dialog never needs the full list in memory at once.
    """
    department = "Marketing"
    conditions = []
    values = {}

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

    if txt:
        conditions.append("(c.name1 LIKE %(txt)s OR m.name LIKE %(txt)s)")
        values["txt"] = f"%{txt}%"

    query = """
		SELECT m.name AS value, c.name1 AS label
		FROM `tabMarketing` m
		LEFT JOIN `tabCustomer` c ON c.name = m.customer
	"""
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY m.creation DESC"

    start = int(start or 0)
    page_length = int(page_length or 0)
    if page_length:
        query += " LIMIT %(page_length)s OFFSET %(start)s"
        values["page_length"] = page_length
        values["start"] = start

    rows = frappe.db.sql(query, values, as_dict=True)
    for r in rows:
        r["label"] = r["label"] or r["value"]
    return rows


@frappe.whitelist()
def get_default_marketing_customer_options(param=""):
    # Retained for backward compatibility only — nothing in the current
    # client flow calls this anymore (get_assigned_marketing_customers
    # covers both the dialog and the "select all" default now).
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
      ["fieldname", "=", value]
      ["fieldname", "in", [v1, v2, ...]]
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
            links = (
                json.loads(marketing_link)
                if isinstance(marketing_link, str)
                and marketing_link.strip().startswith("[")
                else (
                    marketing_link
                    if isinstance(marketing_link, list)
                    else [marketing_link]
                )
            )
        except (ValueError, TypeError):
            links = [marketing_link]
        links = [l for l in links if l]
        if links:
            escaped = ", ".join(frappe.db.escape(l) for l in links)
            conditions += f" AND i.marketing_link IN ({escaped})"

    conditions += _owner_scoping_sql_condition()

    # Rounds are stored in the company zone; the viewer sees them in their own zone, where a round can land
    # on the neighbouring day - so fetch a day either side and keep what falls in the range afterwards.
    first, last = frappe.utils.getdate(start), frappe.utils.getdate(end)
    values.update({"start": frappe.utils.add_days(first, -1), "end": frappe.utils.add_days(last, 1)})

    rounds = frappe.db.sql(
        f"""
        SELECT ir.name AS round_name, ir.parent AS interview, ir.round,
            ir.date_of_interview, ir.from_time, ir.to_time, ir.time_zone,
            ir.status AS round_status, i.company, i.role, i.status AS interview_status,
            i.marketing_link, i.customer AS customer_name
        FROM `tabInterview Round` ir
        INNER JOIN `tabInterview` i ON i.name = ir.parent
        WHERE ir.date_of_interview BETWEEN %(start)s AND %(end)s
        {conditions}
        ORDER BY ir.date_of_interview, ir.from_time
    """,
        values,
        as_dict=True,
    )

    tz = user_time_zone()
    events = []
    for r in rounds:
        has_time = bool(r.from_time is not None and r.to_time is not None)
        local = convert_round(r.date_of_interview, r.from_time, r.to_time, r.time_zone, tz)
        if not first <= local["date"] <= last:
            continue
        status = r.round_status or r.interview_status or ""
        start_time = local["from_time"] or "09:00:00"
        end_time = local["to_time"] or "10:00:00"
        end_day = local["date"] if end_time >= start_time else frappe.utils.add_days(local["date"], 1)
        events.append({
            "name": r.interview,
            "subject": f"{r.company} — {r.role} (Round {r.round})",
            "start": f"{local['date']} {start_time}",
            "end": f"{end_day} {end_time}",
            "allDay": 0 if has_time else 1,
            "status": status,
            "company": r.company,
            "role": r.role,
            "round": r.round,
            "from_time": local["from_time"],
            "to_time": local["to_time"],
            "time_zone": r.time_zone,
            "tz_label": local["tz_label"],
            "entered": local["entered"],
            "customer": r.customer_name or r.marketing_link,
        })
    events.sort(key=lambda e: e["start"])
    return events


@frappe.whitelist()
def get_interview_gantt_rows(filters=None):
    conditions, values = _build_conditions(filters)
    conditions += _owner_scoping_sql_condition()

    rows = frappe.db.sql(
        f"""
        SELECT
            ir.name AS round_id, ir.parent AS interview, ir.round,
            ir.date_of_interview, ir.from_time, ir.to_time, ir.time_zone,
            ir.status AS round_status,
            i.company, i.role, i.status AS interview_status,
            i.docstatus AS docstatus, i.owner AS owner, i.marketing_link,
            i.customer AS customer_name
        FROM `tabInterview Round` ir
        INNER JOIN `tabInterview` i ON i.name = ir.parent
        WHERE ir.date_of_interview IS NOT NULL
        {conditions}
        ORDER BY ir.date_of_interview, ir.from_time
        """,
        values,
        as_dict=True,
    )

    tz = user_time_zone()
    out = []
    for r in rows:
        status = r.round_status or r.interview_status or ""
        local = convert_round(r.date_of_interview, r.from_time, r.to_time, r.time_zone, tz)
        start_dt = f"{local['date']} {local['from_time'] or '09:00:00'}"
        end_dt = f"{local['date']} {local['to_time'] or '10:00:00'}"
        if end_dt <= start_dt:
            end_dt = f"{local['date']} 23:59:00"

        out.append({
            "name": r.round_id,
            "interview": r.interview,
            "owner": r.owner,
            "docstatus": r.docstatus or 0,
            "status": status,
            "company": r.company,
            "role": r.role,
            "round": r.round,
            "date_of_interview": str(local["date"]),
            "subject": f"{r.company} — {r.role} · Round {r.round} · {status}",
            "from_time": local["from_time"],
            "to_time": local["to_time"],
            "time_zone": r.time_zone,
            "tz_label": local["tz_label"],
            "start": start_dt,
            "end": end_dt,
            "customer": r.customer_name or r.marketing_link,
            "_assign": "[]",
            "_liked_by": "[]",
            "_comments": "[]",
            "_user_tags": "",
        })
    return out
