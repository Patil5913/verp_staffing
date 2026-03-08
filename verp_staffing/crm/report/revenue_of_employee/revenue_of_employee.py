import frappe
from datetime import date
from dateutil.relativedelta import relativedelta


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
            "fieldtype": "Data",
            "width": 250,
        },
        {
            "label": "Total Revenue",
            "fieldname": "total_revenue",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Target Based On",
            "fieldname": "target_based_on",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Target Start Date",
            "fieldname": "start_date",
            "fieldtype": "Date",
            "width": 150,
        },
        {
            "label": "Target",
            "fieldname": "target",
            "fieldtype": "Currency",
            "width": 150,
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


def filter_sales_employees(employee_list):
    """Filter employees who belong to Sales department."""
    if not employee_list:
        return []

    data = frappe.db.sql(
        """
        SELECT DISTINCT e.name
        FROM `tabEmployee` e
        INNER JOIN `tabEmployee Assignment Detail` d
            ON d.parent = e.name
        WHERE e.name IN %(emp_list)s
          AND d.department = 'Sales'
        """,
        {"emp_list": tuple(employee_list)},
        as_dict=True,
    )

    return [row.name for row in data]


def get_employee_from_user(user):
    return frappe.db.get_value("Employee", {"user": user}, "name")


def employees_to_users(employee_list):
    """Get user IDs linked to given employees in Sales department."""
    if not employee_list:
        return []

    data = frappe.db.sql(
        """
        SELECT DISTINCT e.user
        FROM `tabEmployee` e
        INNER JOIN `tabEmployee Assignment Detail` d
            ON d.parent = e.name
        WHERE e.name IN %(emp_list)s
          AND d.department = 'Sales'
        """,
        {"emp_list": tuple(employee_list)},
        as_dict=True,
    )

    return [row.user for row in data if row.user]


def get_data(filters):
    conditions = []
    values = {}

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    timeline = filters.get("timeline")

    if timeline and not start_date:
        today = frappe.utils.getdate()

        if timeline == "Monthly":
            start_date = today - relativedelta(months=1)
        elif timeline == "3 Months":
            start_date = today - relativedelta(months=3)
        elif timeline == "6 Months":
            start_date = today - relativedelta(months=6)
        elif timeline == "Yearly":
            start_date = today - relativedelta(years=1)

        end_date = today

    if start_date:
        conditions.append("so.creation >= %(start_date)s")
        values["start_date"] = start_date

    if end_date:
        conditions.append("so.creation <= %(end_date)s")
        values["end_date"] = end_date

    user = frappe.session.user
    employee_filter = filters.get("employee")


    if employee_filter:
        # Selected employee + all subordinates recursively
        subordinates = get_all_subordinates_by_assignment(employee_filter, department="Sales")
        subordinates.add(employee_filter)

        # Filter only Sales dept employees
        valid_employees = filter_sales_employees(list(subordinates))
        users = employees_to_users(valid_employees)

    else:
        if user == "Administrator":
            # Admin — all Sales employees
            data = frappe.db.sql(
                """
                SELECT DISTINCT e.user
                FROM `tabEmployee` e
                INNER JOIN `tabEmployee Assignment Detail` d
                    ON d.parent = e.name
                WHERE d.department = 'Sales'
                """,
                as_dict=True,
            )
            users = [row.user for row in data if row.user]

        else:
            # Non-admin — own hierarchy only
            current_employee = get_employee_from_user(user)

            if not current_employee:
                return []

            subordinates = get_all_subordinates_by_assignment(current_employee, department="Sales")
            subordinates.add(current_employee)
            valid_employees = filter_sales_employees(list(subordinates))
            users = employees_to_users(valid_employees)

    if not users:
        return []

    placeholders = ", ".join([f"%(user_{i})s" for i in range(len(users))])
    conditions.append(f"so.owner IN ({placeholders})")

    for i, u in enumerate(users):
        values[f"user_{i}"] = u

    where_clause = " AND ".join(["so.owner IS NOT NULL"] + conditions)

    query = f"""
    SELECT
        so.owner AS employee,
        SUM(cpt.amount) AS total_revenue,
        e.target AS target,
        e.target_based_on,
        e.start_date
    FROM `tabCustomer Payment Terms` cpt
    JOIN `tabSales Order` so
        ON cpt.parent = so.name
    LEFT JOIN `tabEmployee` e
        ON e.user = so.owner
    WHERE {where_clause}
    GROUP BY so.owner
    ORDER BY total_revenue DESC
"""

    return frappe.db.sql(query, values, as_dict=True)


def get_chart(data):
    if not data:
        return {}

    return {
        "data": {
            "labels": [row["employee"] for row in data],
            "datasets": [
                {
                    "name": "Revenue per Employee",
                    "values": [row["total_revenue"] for row in data],
                }
            ],
        },
        "type": "bar",
    }


@frappe.whitelist()
def get_sales_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    """
    Link field search — shows Sales dept employees only.
    Non-admin sees only self + subordinates via Employee Assignment Detail.
    """
    user = frappe.session.user

    values = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
        "dept": "Sales",
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
        subordinates = get_all_subordinates_by_assignment(current_employee, department="Sales")
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