import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.helpers import get_reporting_subtree


class Interview(Document):
    def autoname(self):
        if not self.marketing_link:
            frappe.throw(_("Marketing is required"), frappe.ValidationError)

        # Validate the marketing link exists before trying to use it
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
        self._validate_status()
        self._validate_interview_rounds()

    # ------------------------------------------------------------------
    # Field-level validators
    # ------------------------------------------------------------------

    def _validate_marketing_link(self):
        """Marketing must exist and must resolve to a real customer."""
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
        """Company and Role are mandatory (mirroring JSON reqd:1)."""
        if not self.company:
            frappe.throw(_("Company is required"), frappe.MandatoryError)

        if not self.role:
            frappe.throw(_("Role is required"), frappe.MandatoryError)

    def _validate_status(self):
        """Status must exist in the Interview Status doctype."""
        if not self.status:
            frappe.throw(_("Status is required"), frappe.MandatoryError)

        if not frappe.db.exists("Interview Status", self.status):
            frappe.throw(
                _("Interview Status '{0}' does not exist").format(self.status),
                frappe.ValidationError,
            )

    def _validate_interview_rounds(self):
        """Validate every row in the Interview Rounds child table."""
        rounds = self.interview_rounds_table or []

        for i, row in enumerate(rounds, start=1):
            # date_of_interview is required in every round
            if not row.date_of_interview:
                frappe.throw(
                    _("Row #{0}: Date is required in Interview Rounds").format(i),
                    frappe.ValidationError,
                )

            # follow_up must be a non-negative integer
            follow_up = row.follow_up or 0
            if not isinstance(follow_up, (int, float)) or int(follow_up) < 0:
                frappe.throw(
                    _("Row #{0}: Follow Up must be a non-negative number").format(i),
                    frappe.ValidationError,
                )

            # follow_up must increment by exactly 1 from the previous row
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

        # Round numbers must be sequential (1, 2, 3 …)
        for i, row in enumerate(rounds, start=1):
            if row.round != i:
                frappe.throw(
                    _(
                        "Interview round numbers are out of sequence. "
                        "Please refresh and try again."
                    ),
                    frappe.ValidationError,
                )


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
        {
            "column_name": doc.status_name,
            "indicator": "Blue",
            "status": "Active",
        },
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


# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------


def get_logged_in_employee():
    """Returns Employee ID linked to logged-in user."""
    if frappe.session.user == "Administrator":
        return None
    return frappe.db.get_value(
        "Employee",
        {"user": frappe.session.user},
        "name",
    )


def get_allowed_employee_ids(department):
    """
    Administrator → all employees
    Normal user   → self + reporting subtree
    """
    if frappe.session.user == "Administrator":
        return frappe.db.get_all("Employee", pluck="name")
    employee = get_logged_in_employee()
    if not employee:
        return []
    return get_reporting_subtree(employee, department)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_default_marketing_customer_options(param=""):
    department = "Marketing"

    conditions = []
    values = []

    # Selected customer from URL
    if param:
        conditions.append("m.name = %s")
        values.append(param)

    # Hierarchy restriction
    if frappe.session.user != "Administrator":
        allowed_employees = get_allowed_employee_ids(department)

        if not allowed_employees:
            return []

        placeholders = ", ".join(["%s"] * len(allowed_employees))

        conditions.append(f"m.assign_to IN ({placeholders})")

        values.extend(allowed_employees)

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            m.name AS value,
            c.name AS label
        FROM `tabMarketing` m
        LEFT JOIN `tabCustomer` c
            ON c.name = m.customer
        {where_clause}
        ORDER BY m.creation DESC
        LIMIT 1
    """

    return frappe.db.sql(
        query,
        values,
        as_dict=True,
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_marketing_customers(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters,
):
    department = "Marketing"

    conditions = []
    values = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": min(page_len or 50, 50),
    }

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
        "(c.name LIKE %(txt)s OR c.name1 LIKE %(txt)s) OR m.name LIKE %(txt)s"
    )

    where_clause = " AND ".join(conditions)
    return frappe.db.sql(
        f"""
        SELECT
            m.name,
            CONCAT(
                COALESCE(c.name1, '')
            )
        FROM `tabMarketing` m
        INNER JOIN `tabCustomer` c
            ON c.name = m.customer
        WHERE {where_clause}
        ORDER BY m.creation DESC
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )
