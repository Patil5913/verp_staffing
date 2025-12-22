# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt


from frappe.model.document import Document


import frappe
class Interview(Document):
	pass



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
    """
    Returns marketing customer options.
    Administrator:
      - Sees ALL customers
      - Gets an extra 'ALL' option at top
    Others:
      - Sees customers based on hierarchy visibility
    """

    department = "Marketing"

    # ----------------------------
    # ADMINISTRATOR: FULL ACCESS
    # ----------------------------
    if frappe.session.user == "Administrator":
        query = """
            SELECT
                m.name AS value,
                CONCAT(
                    c.title,
                    ' (',
                    m.assigned_to,
                    ')'
                ) AS label
            FROM `tabMarketing` m
            INNER JOIN `tabCustomer` c
                ON c.name = m.customer
            ORDER BY c.title
        """

        return frappe.db.sql(query, as_dict=True)

    # ----------------------------
    # NON-ADMIN: RESTRICTED ACCESS
    # ----------------------------
    allowed_employees = get_allowed_employee_ids(department)

    if not allowed_employees:
        return []

    placeholders = ", ".join(["%s"] * len(allowed_employees))

    query = f"""
        SELECT
            m.name AS value,
            CONCAT(
                c.title,
                ' (',
                m.assigned_to,
                ')'
            ) AS label
        FROM `tabMarketing` m
        INNER JOIN `tabCustomer` c
            ON c.name = m.customer
        WHERE m.assigned_to IN ({placeholders})
        ORDER BY c.title
    """

    return frappe.db.sql(query, allowed_employees, as_dict=True)

