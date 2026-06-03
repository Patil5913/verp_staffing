# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, cint
from verp_staffing.crm.api.helpers import get_visible_employee_names_cached


def execute(filters=None):
    filters = filters or {}

    today = getdate()

    limit = cint(filters.get("limit") or 25)
    limit = min(limit, 500)
    year = filters.get("year") or today.year

    conditions = " AND ir.date_of_interview > %(today)s"

    values = {"today": today, "limit": limit, "year": year}

    hierarchy_clause = ""

    if frappe.session.user != "Administrator":
        allowed_employees = get_visible_employee_names_cached()

        if not allowed_employees:
            return [], [], None, {}

        placeholders = []

        for idx, emp in enumerate(allowed_employees):
            key = f"emp_{idx}"
            placeholders.append(f"%({key})s")
            values[key] = emp

        hierarchy_clause = f" AND m.assign_to IN ({', '.join(placeholders)})"

    # ------------------------------------------------------------------
    # REPORT DATA
    # ------------------------------------------------------------------

    periodicity = filters.get("periodicity")

    if periodicity == "Monthly":
        return build_periodic_report(
            values=values,
            hierarchy_clause=hierarchy_clause,
            select_clause="""
            DATE_FORMAT(
                ir.date_of_interview,
                '%%b %%Y'
            ) AS period,
            COUNT(ir.name) AS interviews
        """,
            group_by_clause="""
            YEAR(ir.date_of_interview),
            MONTH(ir.date_of_interview)
        """,
            order_by_clause="""
            YEAR(ir.date_of_interview),
            MONTH(ir.date_of_interview)
        """,
            period_label="Month",
        )

    elif periodicity == "Quarterly":
        quarter_labels = {
            1: "Jan-Mar",
            2: "Apr-Jun",
            3: "Jul-Sep",
            4: "Oct-Dec",
        }

        def formatter(rows):
            return [
                {
                    "period": (f"{quarter_labels[row.quarter]} {row.year}"),
                    "interviews": row.interviews,
                }
                for row in rows
            ]

        return build_periodic_report(
            values=values,
            hierarchy_clause=hierarchy_clause,
            select_clause="""
                YEAR(ir.date_of_interview) AS year,
                QUARTER(ir.date_of_interview) AS quarter,
                COUNT(ir.name) AS interviews
            """,
            group_by_clause="""
                YEAR(ir.date_of_interview),
                QUARTER(ir.date_of_interview)
            """,
            order_by_clause="""
                YEAR(ir.date_of_interview),
                QUARTER(ir.date_of_interview)
            """,
            period_label="Quarter",
            formatter=formatter,
        )

    elif periodicity == "Yearly":
        return build_periodic_report(
            values=values,
            hierarchy_clause=hierarchy_clause,
            select_clause="""
            YEAR(ir.date_of_interview) AS period,
            COUNT(ir.name) AS interviews
        """,
            group_by_clause="""
            YEAR(ir.date_of_interview)
        """,
            order_by_clause="""
            YEAR(ir.date_of_interview)
        """,
            period_label="Year",
        )

    return get_customer_report(filters, values, hierarchy_clause, conditions)


def build_periodic_report(
    values,
    hierarchy_clause,
    select_clause,
    group_by_clause,
    order_by_clause,
    period_label,
    formatter=None,
):
    data = frappe.db.sql(
        f"""
        SELECT
            {select_clause}
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        WHERE YEAR(ir.date_of_interview) = %(year)s
        {hierarchy_clause}
        GROUP BY
            {group_by_clause}
        ORDER BY
            {order_by_clause}
        """,
        values,
        as_dict=True,
    )

    if formatter:
        data = formatter(data)

    columns = [
        {
            "label": period_label,
            "fieldname": "period",
            "fieldtype": "Data",
        },
        {
            "label": "Interviews",
            "fieldname": "interviews",
            "fieldtype": "Int",
        },
    ]

    chart = {
        "data": {
            "labels": [d["period"] if isinstance(d, dict) else d.period for d in data],
            "datasets": [
                {
                    "name": "Upcoming Interviews",
                    "values": [
                        d["interviews"] if isinstance(d, dict) else d.interviews
                        for d in data
                    ],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

    return columns, data, None, chart


def get_customer_report(
    filters,
    values,
    hierarchy_clause,
    conditions=" AND ir.date_of_interview > %(today)s",
):
    if filters.get("to_date"):
        conditions += " AND ir.date_of_interview <= %(to_date)s"
        values["to_date"] = filters["to_date"]

    if filters.get("customer"):
        conditions += " AND c.name = %(customer)s"
        values["customer"] = filters["customer"]

    data = frappe.db.sql(
        f"""
        SELECT
            c.name AS customer,
            c.name1 AS name1,
            c.creation,
            COUNT(ir.name) AS upcoming_interviews
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        INNER JOIN `tabCustomer` c
            ON c.name = m.customer
        WHERE 1=1
        {conditions}
        {hierarchy_clause}
        GROUP BY
            c.name,
            c.name1,
            c.creation
        ORDER BY
            c.creation DESC
        LIMIT %(limit)s
        """,
        values,
        as_dict=True,
    )

    columns = [
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
        },
        {
            "label": "Customer Name",
            "fieldname": "name1",
            "fieldtype": "Data",
        },
        {
            "label": "Upcoming Interviews",
            "fieldname": "upcoming_interviews",
            "fieldtype": "Int",
        },
    ]

    chart_rows = data[:25]

    chart = {
        "data": {
            "labels": [d.name1 for d in chart_rows],
            "datasets": [
                {
                    "name": "Upcoming Interviews",
                    "values": [d.upcoming_interviews for d in chart_rows],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

    return columns, data, None, chart

