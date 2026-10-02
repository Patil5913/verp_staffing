import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names_cached

@frappe.whitelist()
def _build_in_placeholders(prefix, items, values_dict):
    """
    Adds items to values_dict as %(prefix_0)s … %(prefix_N)s and returns the
    placeholder string for use inside an IN (...) clause.

    Handles the single-item tuple trailing-comma bug that breaks frappe.db.sql
    when you do `tuple([x])` → `('x',)` but MySQL sees `IN ('x',)`.
    """
    keys = []
    for i, item in enumerate(items):
        key = f"{prefix}_{i}"
        values_dict[key] = item
        keys.append(f"%({key})s")
    return ", ".join(keys)


@frappe.whitelist()
def get_lead_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    """
    Link field search for the employee filter.
    Restricts to Lead department employees visible to the current user.
    Non-admin sees only their visible hierarchy.
    """
    values = {
        "txt": f"%{txt}%",
        "start": int(start),       
        "page_len": int(page_len),
        "dept": ["Lead", "Sales"],
    }

    conditions = [
        "tabEmployee.name LIKE %(txt)s",
        """
        EXISTS (
            SELECT 1
            FROM `tabEmployee Assignment Detail` d
            WHERE d.parent = tabEmployee.name
              AND d.department in %(dept)s
        )
        """,
    ]

    if frappe.session.user != "Administrator":
        allowed = get_visible_employee_names_cached()
        if not allowed:
            return []
        placeholders = _build_in_placeholders("se", allowed, values)
        conditions.append(f"tabEmployee.name IN ({placeholders})")
        
    query = """
        SELECT
            tabEmployee.name,
            tabEmployee.employee_name
        FROM `tabEmployee`
        WHERE
    """

    query += " AND ".join(conditions)

    query += """
        ORDER BY tabEmployee.employee_name
        LIMIT %(start)s, %(page_len)s
    """

    return frappe.db.sql(query, values)