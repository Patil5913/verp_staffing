# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names_cached
from verp_staffing.crm.api.report_helper import _build_in_placeholders



def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    return columns, data, None, chart


def get_columns():
    return [
        {
            "label": "Stage",
            "fieldname": "stage",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Count",
            "fieldname": "count",
            "fieldtype": "Int",
            "width": 120,
        },
    ]


def get_data(filters=None):
    """
    All four funnel counts are computed in a single SQL query using
    conditional aggregation (SUM + CASE WHEN).  This replaces four
    sequential round-trips to the DB with one.

    Query shape:
        COUNT(*)                                    → total leads
        COUNT(DISTINCT CASE WHEN o.name IS NOT NULL)→ leads with any opportunity
        SUM(CASE WHEN o.status = 'Converted')       → converted opps
        SUM(CASE WHEN o.status = 'Lost')            → lost opps

    The Lead table is the driving table; Opportunity is LEFT JOINed so leads
    with no opportunity still count in the first stage.

    The lead-owner filter and date filter are applied in ONE WHERE clause —
    no string.replace() hacks needed because both tables are always present.
    """
    filters = filters or {}
    user = frappe.session.user
    conditions = []
    values = {}

    # -- Date range on lead creation ----------------------------------------
    if filters.get("from_date"):
        conditions.append("l.creation >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        # Inclusive upper bound: add one day so "to_date = today" includes
        # records created at any time today, since creation is a DATETIME.
        conditions.append("l.creation < DATE_ADD(%(to_date)s, INTERVAL 1 DAY)")
        values["to_date"] = filters["to_date"]

    # -- Employee / hierarchy filter ----------------------------------------
    # Explicit filter takes priority; otherwise scope to visible hierarchy.
    if filters.get("employee"):
        # Validate: non-admin cannot request an employee outside their scope.
        if user != "Administrator":
            allowed = get_visible_employee_names_cached()
            if filters["employee"] not in allowed:
                return _empty_funnel()
        conditions.append("l.lead_owner = %(employee)s")
        values["employee"] = filters["employee"]

    elif user != "Administrator":
        allowed = get_visible_employee_names_cached()
        if not allowed:
            return _empty_funnel()
        placeholders = _build_in_placeholders("emp", allowed, values)
        conditions.append(f"l.lead_owner IN ({placeholders})")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    row = frappe.db.sql(
        f"""
        SELECT
            COUNT(l.name)                                           AS total_leads,

            COUNT(DISTINCT
                CASE WHEN o.name IS NOT NULL THEN l.name END
            )                                                       AS leads_with_opportunity,

            SUM(CASE WHEN o.status = 'Converted' THEN 1 ELSE 0 END)
                                                                    AS converted,

            SUM(CASE WHEN o.status = 'Lost'      THEN 1 ELSE 0 END)
                                                                    AS lost

        FROM `tabLead` l
        LEFT JOIN `tabOpportunity` o
            ON o.opportunity_from_lead = l.name
        {where_clause}
        """,
        values,
        as_dict=True,
    )

    if not row:
        return _empty_funnel()

    r = row[0]
    return [
        {"stage": "Total Leads",              "count": r.total_leads or 0},
        {"stage": "Leads with Opportunity",   "count": r.leads_with_opportunity or 0},
        {"stage": "Converted Opportunities",  "count": r.converted or 0},
        {"stage": "Lost Opportunities",       "count": r.lost or 0},
    ]


def _empty_funnel():
    return [
        {"stage": "Total Leads",             "count": 0},
        {"stage": "Leads with Opportunity",  "count": 0},
        {"stage": "Converted Opportunities", "count": 0},
        {"stage": "Lost Opportunities",      "count": 0},
    ]


def get_chart(data):
    if not data:
        return {}
    return {
        "data": {
            "labels": [row["stage"] for row in data],
            "datasets": [
                {
                    "name": "Lead Conversion Funnel",
                    "values": [row["count"] for row in data],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }


@frappe.whitelist()
def get_lead_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    """
    Link field search for lead_owner filter.
    Non-admin sees only their visible hierarchy (same rule as the report).
    Admin sees all employees.
    """
    user = frappe.session.user
    values = {
        "txt": f"%{txt}%",
        "start": int(start),
        "page_len": int(page_len),
    }
    conditions = [f"(name LIKE %(txt)s OR employee_name LIKE %(txt)s)"]

    if user != "Administrator":
        allowed = get_visible_employee_names_cached()
        if not allowed:
            return []
        placeholders = _build_in_placeholders("se", allowed, values)
        conditions.append(f"name IN ({placeholders})")

    where = " AND ".join(conditions)
    return frappe.db.sql(
        f"""
        SELECT name, employee_name
        FROM `tabEmployee`
        WHERE {where}
        ORDER BY name
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )