# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names_cached
from verp_staffing.crm.api.report_helper import _build_in_placeholders

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
            "width": 250,
        },
        {
            "label": "Lead Count",
            "fieldname": "lead_count",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": "Visa Breakdown",
            "fieldname": "visa_summary",
            "fieldtype": "Data",
            "width": 320,
        },
    ]
    
def get_data(filters):
    conditions = ["l.lead_owner IS NOT NULL"]
    values = {}

    # -- Date range ----------------------------------------------------------
    if filters.get("from_date"):
        conditions.append("l.creation >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        # Inclusive upper bound for a DATETIME column.
        conditions.append("l.creation < DATE_ADD(%(to_date)s, INTERVAL 1 DAY)")
        values["to_date"] = filters["to_date"]

    # -- Visa status filter --------------------------------------------------
    if filters.get("visa_status"):
        conditions.append("ldf.current_visa_status = %(visa_status)s")
        values["visa_status"] = filters["visa_status"]

    # -- Employee / hierarchy scope ------------------------------------------
    if filters.get("employee"):
        # Validate: non-admin cannot request an employee outside their scope.
        if frappe.session.user != "Administrator":
            allowed = get_visible_employee_names_cached()
            if filters["employee"] not in allowed:
                return []
        conditions.append("l.lead_owner = %(employee)s")
        values["employee"] = filters["employee"]

    elif frappe.session.user != "Administrator":
        allowed = get_visible_employee_names_cached()
        if not allowed:
            return []
        placeholders = _build_in_placeholders("emp", allowed, values)
        conditions.append(f"l.lead_owner IN ({placeholders})")

    where_clause = "WHERE " + " AND ".join(conditions)

    # -----------------------------------------------------------------------
    # Single query — one join, one GROUP BY, one GROUP_CONCAT.
    #
    # visa_summary: counts each visa status in the employee's filtered lead
    # set. Format: "Status A: 12 | Status B: 4".
    #
    # We compute the per-status counts using a conditional COUNT inside
    # GROUP_CONCAT via an inline subquery is NOT needed — instead we run a
    # second lightweight aggregation query for the breakdown (see below).
    # This keeps the main query clean and avoids GROUP_CONCAT size limits
    # on large employee sets.
    # -----------------------------------------------------------------------
    main_query = """
        SELECT
            l.lead_owner           AS employee,
            COUNT(DISTINCT l.name) AS lead_count
        FROM `tabLead` l
        LEFT JOIN `tabLead Detail Form` ldf
            ON ldf.name = l.lead_details
    """

    main_query += where_clause
    main_query += """
        GROUP BY l.lead_owner
        ORDER BY lead_count DESC
    """

    data = frappe.db.sql(
        main_query,
        values,
        as_dict=True,
    )

    if not data:
        return []

    # -----------------------------------------------------------------------
    # Second focused query — visa breakdown per employee.
    #
    # Rationale: keeping this separate from the main query avoids
    # GROUP_CONCAT on a potentially wide result set and makes the main
    # query's GROUP BY simpler for MySQL's optimizer. Both queries share
    # the same WHERE clause and values dict so results are always consistent.
    #
    # Result shape: { employee_name: "Visa A: 3 | Visa B: 1", ... }
    # -----------------------------------------------------------------------
    breakdown_query = """
        SELECT
            l.lead_owner            AS employee,
            ldf.current_visa_status AS visa_status,
            COUNT(DISTINCT l.name)  AS cnt
        FROM `tabLead` l
        LEFT JOIN `tabLead Detail Form` ldf
            ON ldf.name = l.lead_details
    """

    breakdown_query += where_clause
    breakdown_query += """
        AND ldf.current_visa_status IS NOT NULL
        GROUP BY
            l.lead_owner,
            ldf.current_visa_status
        ORDER BY
            l.lead_owner,
            cnt DESC
    """

    breakdown_rows = frappe.db.sql(
        breakdown_query,
        values,
        as_dict=True,
    )

    # Build lookup: employee → "Status A: N | Status B: M"
    visa_map = {}
    for row in breakdown_rows:
        emp = row.employee
        entry = f"{row.visa_status}: {row.cnt}"
        if emp not in visa_map:
            visa_map[emp] = []
        visa_map[emp].append(entry)

    visa_summary_map = {emp: " | ".join(parts) for emp, parts in visa_map.items()}

    # Attach visa_summary to each data row in Python — no extra DB round trip.
    for row in data:
        row["visa_summary"] = visa_summary_map.get(row["employee"], "")

    return data

def get_chart(data):
    """
    Bar chart: lead count per employee.
    Labels use employee name only — visa breakdown is shown in the table.
    Frappe's chart engine does not render \\n in bar labels; putting the
    visa_summary in the label produced broken display in the original.
    """
    if not data:
        return {}

    return {
        "data": {
            "labels": [row["employee"] for row in data],
            "datasets": [
                {
                    "name": "Leads per Employee",
                    "values": [row["lead_count"] for row in data],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

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
        "dept": "Lead",
    }

    conditions = [
        "tabEmployee.name LIKE %(txt)s",
        """
        EXISTS (
            SELECT 1
            FROM `tabEmployee Assignment Detail` d
            WHERE d.parent = tabEmployee.name
              AND d.department = %(dept)s
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