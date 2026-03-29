import frappe
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from verp_staffing.crm.api.helpers import get_visible_employee_names


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    return columns, data, None, chart


def get_columns():
    return [
        {
            "label": "Employee",
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 180,
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Marketing Start Date",
            "fieldname": "start_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Target Based On",
            "fieldname": "target_based_on",
            "fieldtype": "Data",
            "width": 120,
        },
        {"label": "Target", "fieldname": "target", "fieldtype": "Int", "width": 90},
        {
            "label": "Interview Count",
            "fieldname": "completed_target",
            "fieldtype": "Int",
            "width": 220,
        },
        {
            "label": "Highlight",
            "fieldname": "to_highlight",
            "fieldtype": "Data",
            "hidden": 1,
        },
    ]


def get_all_subordinates_by_assignment(root_employee, department=None):
    """
    Recursively get all subordinates using Employee Assignment Detail.
    assigned_to field mein parent employee hota hai.
    """
    collected = set()
    stack = [root_employee]

    while stack:
        current = stack.pop()

        filters = {"assigned_to": current}
        if department:
            filters["department"] = department

        children = frappe.db.get_all(
            "Employee Assignment Detail",
            filters=filters,
            pluck="parent",
        )

        for emp in children:
            if emp and emp not in collected:
                collected.add(emp)
                stack.append(emp)

    return collected


def filter_marketing_employees(employee_list):
    """Filter employees who belong to Marketing department."""
    if not employee_list:
        return []

    data = frappe.db.sql(
        """
        SELECT DISTINCT e.name
        FROM `tabEmployee` e
        INNER JOIN `tabEmployee Assignment Detail` d
            ON d.parent = e.name
        WHERE e.name IN %(emp_list)s
          AND d.department = 'Marketing'
        """,
        {"emp_list": tuple(employee_list)},
        as_dict=True,
    )

    return [row.name for row in data]


def get_employee_from_user(user):
    """Get Employee name linked to a user."""
    return frappe.db.get_value("Employee", {"user": user}, "name")


def get_data(filters):

    if not filters or not filters.get("from_date"):
        return []

    selected_date = frappe.utils.getdate(filters["from_date"])
    user = frappe.session.user
    employee_filter = filters.get("employee")

    values = {}
    conditions = ["m.docstatus < 2"]

    if employee_filter:
        # Selected employee + all subordinates recursively
        subordinates = get_all_subordinates_by_assignment(
            employee_filter, department="Marketing"
        )

        # Include the selected employee itself
        subordinates.add(employee_filter)

        # Filter only Marketing dept employees
        valid_employees = filter_marketing_employees(list(subordinates))

    else:
        if user == "Administrator":
            data = frappe.db.sql(
                """
                SELECT DISTINCT e.name
                FROM `tabEmployee` e
                INNER JOIN `tabEmployee Assignment Detail` d
                    ON d.parent = e.name
                WHERE d.department = 'Marketing'
                """,
                as_dict=True,
            )
            valid_employees = [row.name for row in data]

        else:
            # Use existing utility — it already handles hierarchy via Employee Assignment Detail
            employee_names = (
                get_visible_employee_names(user, department="Marketing") or []
            )
            valid_employees = filter_marketing_employees(employee_names)

    if not valid_employees:
        return []

    placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(valid_employees))])
    conditions.append(f"m.assign_to IN ({placeholders})")

    for i, emp in enumerate(valid_employees):
        values[f"emp_{i}"] = emp

    where_clause = " AND ".join(conditions)

    marketing_records = frappe.db.sql(
        f"""
    SELECT
        m.name,
        m.assign_to,
        IFNULL(c.name, m.customer) AS customer_name,
        m.start_date,
        m.target_based_on,
        m.target
    FROM `tabMarketing` m
    LEFT JOIN `tabCustomer` c ON c.name = m.customer
    WHERE {where_clause}
    ORDER BY m.assign_to, m.start_date DESC
    """,
        values,
        as_dict=True,
    )
    final_data = []

    for m in marketing_records:

        if not m.start_date or selected_date < m.start_date:
            continue

        completed_target = 0

        if m.target_based_on == "Weekly":
            days_passed = (selected_date - m.start_date).days
            week_number = days_passed // 7
            period_start = m.start_date + timedelta(days=week_number * 7)
            period_end = period_start + timedelta(days=6)
            period_to = min(selected_date, period_end)

        elif m.target_based_on == "Monthly":
            months_passed = (selected_date.year - m.start_date.year) * 12 + (
                selected_date.month - m.start_date.month
            )
            period_start = m.start_date + relativedelta(months=months_passed)
            period_end = period_start + relativedelta(months=1) - timedelta(days=1)
            period_to = min(selected_date, period_end)

        elif m.target_based_on == "Daily":
            period_start = selected_date
            period_to = selected_date

        else:
            period_start = m.start_date
            period_to = selected_date

        completed_target = (
            frappe.db.sql(
                """
                SELECT COUNT(name)
                FROM `tabInterview`
                WHERE marketing_link = %s
                  AND DATE(creation) BETWEEN %s AND %s
                """,
                (m.name, period_start, period_to),
            )[0][0]
            or 0
        )

        row_data = {
            "employee": m.assign_to,
            "customer_name": m.customer_name,
            "start_date": m.start_date,
            "target_based_on": m.target_based_on,
            "target": m.target,
            "completed_target": completed_target,
            "to_highlight": None,
        }

        if completed_target < (m.target or 0):
            row_data["to_highlight"] = True

        final_data.append(row_data)

    return final_data


def get_chart(data):
    if not data:
        return {}

    labels = []
    values = []

    for row in data:
        employee = row.get("employee", "")
        customer = row.get("customer_name", "")
        start_date = row.get("start_date")
        completed = row.get("completed_target", 0)
        target = row.get("target", 0)

        formatted_date = (
            frappe.utils.formatdate(start_date, "dd-MM-yyyy") if start_date else ""
        )

        label = f" {customer} | {employee} | {formatted_date} ({completed}/{target})"
        labels.append(label)
        values.append(completed)

    return {
        "data": {
            "labels": labels,
            "datasets": [{"values": values}],
        },
        "type": "bar",
        "colors": ["#28a745"],
    }

@frappe.whitelist()
def get_marketing_hierarchy_employees(
    doctype, txt, searchfield, start, page_len, filters
):
    """
    Link field search — shows Marketing dept employees only.
    Non-admin sees only self + subordinates via Employee Assignment Detail.
    """
    user = frappe.session.user

    values = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
        "dept": "Marketing",
    }

    conditions = [
        f"tabEmployee.{searchfield} LIKE %(txt)s",
        """
        EXISTS (
            SELECT 1
            FROM `tabEmployee Assignment Detail` d
            WHERE d.parent = tabEmployee.name
              AND d.department = %(dept)s
        )
        """,
    ]

    if user != "Administrator":
        current_employee = get_employee_from_user(user)

        if not current_employee:
            return []

        # Get full hierarchy
        subordinates = get_all_subordinates_by_assignment(
            current_employee, department="Marketing"
        )
        subordinates.add(current_employee)
        all_emps = list(subordinates)

        if not all_emps:
            return []

        placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(all_emps))])
        conditions.append(f"tabEmployee.name IN ({placeholders})")

        for i, emp in enumerate(all_emps):
            values[f"emp_{i}"] = emp

    return frappe.db.sql(
        f"""
        SELECT tabEmployee.name, tabEmployee.employee_name
        FROM `tabEmployee`
        WHERE {" AND ".join(conditions)}
        ORDER BY tabEmployee.name
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )


def get_employee_from_user(user):
    return frappe.db.get_value("Employee", {"user": user}, "name")
