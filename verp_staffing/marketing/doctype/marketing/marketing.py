# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

from unittest import result
import frappe,json
from frappe.model.document import Document
import json

from frappe.utils import now_datetime

class Marketing(Document):
    def after_insert(self):
        self.create_customer()
 
    def create_customer(self):
        service = "marketing"
        parents = frappe.db.sql("""
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name=%s
        """, (service), as_dict=True)

        customer = frappe.get_doc({
            "doctype":  "Customer",
            "name": self.customer
        })
        stage = json.loads(customer.stage) if customer.stage else {}

        # department = parents[0].parent
        if not parents:
            # frappe.throw("No Department Service found for 'marketing'")
            return

        department = parents[0].parent

        stage["marketing"] = {
            "department": department,
            "timestamp": str(now_datetime()),
            "count": 1
        }
        frappe.db.set_value(
            "Customer",
            customer,
            "stage",
            json.dumps(stage)
        )

    def before_insert(self):
        if self.customer:
            title = frappe.db.get_value("Customer", self.customer, "title")
            if title:
                self.title = title



@frappe.whitelist()
def get_interviews_by_marketing(marketing):
    if not marketing:
        return []

    return frappe.get_all(
        "Interview", filters={"marketing_link": marketing}, fields=["company"]
    )


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

    visited = set()
    users = []
    current_employee = assign_to

    while current_employee and current_employee not in visited:
        visited.add(current_employee)

        nxt = frappe.db.sql(
            """
            SELECT t.assigned_to AS assigned_employee
            FROM `tabEmployee Assignment Detail` t
            WHERE t.parent = %s
              AND t.department = 'Marketing'
            LIMIT 1
            """,
            (current_employee,),
            as_dict=True,
        )

        if not nxt or not nxt[0].assigned_employee:
            break

        next_employee = nxt[0].assigned_employee
        next_user = frappe.db.get_value("Employee", next_employee, "user")

        if next_user:
            users.append(next_user)

        current_employee = next_employee

    if current_user in users:
        return {
            "can_edit": True,
            "can_delete": True,
            "can_add": True,
        }

    return {
        "can_edit": False,
        "can_delete": False,
        "can_add": False,
    }

@frappe.whitelist()
def can_edit_job_application_date(assign_to=None):
    current_user = frappe.session.user

    # Administrator can edit date
    if current_user == "Administrator":
        return {"can_edit_date": True}

    if not assign_to:
        return {"can_edit_date": False}

    assign_to_user = frappe.db.get_value("Employee", assign_to, "user")

    # ❌ assign_to cannot edit date
    if current_user == assign_to_user:
        return {"can_edit_date": False}

    # 🔁 Marketing Chain
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
