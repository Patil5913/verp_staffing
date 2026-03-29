# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series


class Interview(Document):
    def autoname(self):
        if not self.marketing_link:
            frappe.throw("Marketing is required")

        customer = frappe.db.get_value("Marketing", self.marketing_link, "customer")
        customer_name = frappe.db.get_value("Customer", customer, "name1")

        self.name = generate_name_series("Interview", customer_name)

KANBAN_NAME = "Interview"

def add_to_kanban(doc, method):
    kb = frappe.get_doc("Kanban Board", KANBAN_NAME)

    if any(c.column_name == doc.status_name for c in kb.columns):
        return

    kb.append("columns", {
        "column_name": doc.status_name,
        "indicator": "Blue",
        "status": "Active",
    })

    kb.save(ignore_permissions=True)


def remove_from_kanban(doc, method):
    kb = frappe.get_doc("Kanban Board", KANBAN_NAME)

    kb.columns = [
        c for c in kb.columns if c.column_name != doc.status_name
    ]

    kb.save(ignore_permissions=True)


def sync_kanban(doc, method):
    kb = frappe.get_doc("Kanban Board", KANBAN_NAME)

    for col in kb.columns:
        if col.column_name == doc.get_db_value("status_name"):
            col.column_name = doc.status_name

    kb.save(ignore_permissions=True)


# UTILS
def get_logged_in_employee():
    """
    Returns Employee ID linked to logged-in user
    """
    if frappe.session.user == "Administrator":
        return None

    return frappe.db.get_value(
        "Employee",
        {"user": frappe.session.user},
        "name"
    )


# CORE LOGIC (ASSIGNED_TO TREE)
def get_reporting_subtree(root_employee, department):
    """
    Returns root employee + all downstream employees
    via Employee Assignment Detail.assigned_to chain
    """
    result = {root_employee}
    stack = [root_employee]

    while stack:
        current = stack.pop()

        children = frappe.db.get_all(
            "Employee Assignment Detail",
            filters={
                "assigned_to": current,
                "department": department
            },
            pluck="parent"
        )

        for emp in children:
            if emp not in result:
                result.add(emp)
                stack.append(emp)

    return list(result)


def get_allowed_employee_ids(department):
    """
    Administrator → all employees
    Normal user → self + reporting subtree
    """
    if frappe.session.user == "Administrator":
        return frappe.db.get_all("Employee", pluck="name")

    employee = get_logged_in_employee()
    if not employee:
        return []

    return get_reporting_subtree(employee, department)


# FINAL API FOR LINK FIELD
@frappe.whitelist()
def get_marketing_customer_options():
    department = "Marketing"

    # ADMIN
    if frappe.session.user == "Administrator":
        query = """
            SELECT
                m.name AS value,
                c.name AS label
            FROM `tabMarketing` m
            LEFT JOIN `tabCustomer` c ON c.name = m.customer
            ORDER BY c.name
        """
        return frappe.db.sql(query, as_dict=True)

    # NON-ADMIN
    allowed_employees = get_allowed_employee_ids(department)

    if not allowed_employees:
        return []

    placeholders = ", ".join(["%s"] * len(allowed_employees))

    query = f"""
        SELECT
            m.name AS value,
            c.name AS label
        FROM `tabMarketing` m
        LEFT JOIN `tabCustomer` c ON c.name = m.customer
        WHERE m.assign_to IN ({placeholders})
        ORDER BY c.name
    """

    return frappe.db.sql(query, allowed_employees, as_dict=True)

