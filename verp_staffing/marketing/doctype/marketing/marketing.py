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
                _(
                    "No Department has selected 'marketing' as a service. "
                    "<a href='/app/department'>Go to Department List</a>"
                ),
                title=_("Marketing Service Not Configured"),
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


# This api is called from the client-side
@frappe.whitelist()
def _is_superior_in_marketing(assign_to: str, current_user: str) -> bool:
    """
    Returns True if current_user is anywhere above assign_to
    in the Marketing assignment hierarchy.
    """
    if current_user == "Administrator":
        return {"is_superior": True}
    if current_user == frappe.db.get_value("Employee", assign_to, "user"):
        return {"is_superior": False}

    # Single query — entire Marketing chain at once
    rows = frappe.db.sql(
        """
        SELECT ead.parent, ead.assigned_to, e.user
        FROM `tabEmployee Assignment Detail` ead
        JOIN `tabEmployee` e ON e.name = ead.assigned_to
        WHERE ead.department = 'Marketing'
          AND ead.assigned_to IS NOT NULL
        """,
        as_dict=True,
    )
    # Build map: employee → (manager_employee, manager_user)
    # { child: (manager_emp, manager_user) }
    chain_map = {r.parent: (r.assigned_to, r.user) for r in rows}

    # Walk upward in Python — no DB calls
    visited = set()
    current = assign_to
    while current and current not in visited:
        visited.add(current)
        entry = chain_map.get(current)
        if not entry:
            break
        manager_emp, manager_user = entry
        if manager_user == current_user:
            return {"is_superior": True}
        current = manager_emp

    return {"is_superior": False}
