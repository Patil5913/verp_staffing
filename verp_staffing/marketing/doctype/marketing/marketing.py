# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import get_visible_employee_names
import json
from frappe.utils import now_datetime
from verp_staffing.crm.api.naming import generate_name_series


class Marketing(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Marketing", customer_name)

    def validate(self):
        if self.target is not None and self.target != int(self.target):
            frappe.throw(_("Target must be a whole number"))
        if self.start_date and (not self.target or self.target <= 0):
            frappe.throw(_("Target must be greater than 0 when Start Date is set"))

    def after_insert(self):
        self.update_customer_stage()

    def update_customer_stage(self):
        service = "marketing"
        department = frappe.db.get_value(
            "Department Service", {"service_name": service}, "parent"
        )
        if not department:
            frappe.throw(
                _("No Department has selected 'marketing' as a service. "
                "<a href='/app/department'>Go to Department List</a>"),
                title=_("Marketing Service Not Configured")
            )
        stage_raw = frappe.db.get_value("Customer", self.customer, "stage")
        stage = json.loads(stage_raw) if stage_raw else {}
        # department = parents[0].parent

        if "marketing" not in stage:
            stage["marketing"] = []
        stage["marketing"].append(
            {"department": department, "timestamp": str(now_datetime())}
        )
        frappe.db.set_value("Customer", self.customer, "stage", json.dumps(stage))


@frappe.whitelist()
def get_interviews_by_marketing(marketing):
    if not marketing:
        return []

    return frappe.get_all(
        "Interview", filters={"marketing_link": marketing}, fields=["company"]
    )

def _get_marketing_hierarchy_users(assign_to: str) -> list[str]:
    """Walk up the Marketing assignment chain and return all user emails."""
    visited = set()
    users = []
    current = assign_to
    while current and current not in visited:
        visited.add(current)
        row = frappe.db.sql(
            """
            SELECT t.assigned_to
            FROM `tabEmployee Assignment Detail` t
            WHERE t.parent = %s AND t.department = 'Marketing'
            LIMIT 1
            """,
            (current,),
            as_dict=True,
        )
        if not row or not row[0].assigned_to:
            break
        next_emp = row[0].assigned_to
        user = frappe.db.get_value("Employee", next_emp, "user")
        if user:
            users.append(user)
        current = next_emp
    return users

@frappe.whitelist()
def can_edit_marketing(assign_to=None):
    current_user = frappe.session.user

    if current_user == "Administrator":
        return {
            "can_edit": True,
            "can_delete": True,
            "can_add": True,
        }

    if not assign_to:
        return {
            "can_edit": False,
            "can_delete": False,
            "can_add": False,
        }

    assign_to_user = frappe.db.get_value("Employee", assign_to, "user")

    if current_user == assign_to_user:
        return {
            "can_edit": False,
            "can_delete": False,
            "can_add": False,
        }

    can = current_user in _get_marketing_hierarchy_users(assign_to)
    return {"can_edit": can, "can_delete": can, "can_add": can}


@frappe.whitelist()
def can_edit_job_application_date(assign_to=None):
    current_user = frappe.session.user

    # Administrator can edit date
    if current_user == "Administrator":
        return {"can_edit_date": True}

    if not assign_to:
        return {"can_edit_date": False}

    assign_to_user = frappe.db.get_value("Employee", assign_to, "user")

    if current_user == assign_to_user:
        return {"can_edit_date": False}

    visited = set()
    users = []
    current_employee = assign_to

    while current_employee and current_employee not in visited:
        visited.add(current_employee)

        nxt = frappe.db.sql(
            """
            SELECT t.assigned_to
            FROM `tabEmployee Assignment Detail` t
            WHERE t.parent = %s
              AND t.department = 'Marketing'
            LIMIT 1
            """,
            (current_employee,),
            as_dict=True,
        )

        if not nxt:
            break

        next_employee = nxt[0].assigned_to
        next_user = frappe.db.get_value("Employee", next_employee, "user")

        if next_user:
            users.append(next_user)

        current_employee = next_employee

    if current_user in users:
        return {"can_edit_date": True}

    return {"can_edit_date": False}


@frappe.whitelist()
def can_edit_by_hierarchy(assign_to):
    user = frappe.session.user

    if user == "Administrator":
        return {"can_edit": 1}

    allowed_employees = get_visible_employee_names(user)

    if not allowed_employees:
        return {"can_edit": 0}

    # assign_to is Employee name
    if assign_to in allowed_employees:
        return {"can_edit": 1}

    return {"can_edit": 0}
