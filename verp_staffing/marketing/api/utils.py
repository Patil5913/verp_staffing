import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names

def get_employee_hierarchy_condition(alias="m", field="employee"):
    """
    Returns SQL condition + values for hierarchy filtering.
    alias: table alias in SQL
    field: employee field name
    """

    user = frappe.session.user

    if user == "Administrator":
        return "", {}

    employees = get_visible_employee_names(user)

    if not employees:
        # Block everything if no access
        return " AND 1=0", {}

    placeholders = ", ".join([f"%({i})s" for i in range(len(employees))])

    condition = f" AND {alias}.{field} IN ({placeholders})"

    values = {str(i): emp for i, emp in enumerate(employees)}

    return condition, values
