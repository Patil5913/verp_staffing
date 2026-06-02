# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, cint
from verp_staffing.crm.api.helpers import get_visible_employee_names


def execute(filters=None):
    filters = filters or {}

    today = getdate()

    limit = cint(filters.get("limit") or 25)
    limit = min(limit, 500)
    year = filters.get("year") or today.year

    conditions = " AND ir.date_of_interview > %(today)s"

    values = {"today": today, "limit": limit, "year": year}

    user = frappe.session.user
    hierarchy_clause = ""

    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)

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
        return get_monthly_report(filters, values, hierarchy_clause)

    elif periodicity == "Quarterly":
        return get_quarterly_report(filters, values, hierarchy_clause)

    elif periodicity == "Yearly":
        return get_yearly_report(filters, values, hierarchy_clause)

    return get_customer_report(filters, values, hierarchy_clause, conditions)


def get_monthly_report(
    filters,
    values,
    hierarchy_clause,
):
    data = frappe.db.sql(
        f"""
        SELECT
            TO_CHAR(ir.date_of_interview, 'MON-YYYY') AS period,
            COUNT(ir.name) AS interviews
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        WHERE YEAR(ir.date_of_interview) = %(year)s
        {hierarchy_clause}
        GROUP BY
            YEAR(ir.date_of_interview),
            MONTH(ir.date_of_interview)
        ORDER BY
            YEAR(ir.date_of_interview),
            MONTH(ir.date_of_interview)
        """,
        values,
        as_dict=True,
    )

    columns = [
        {
            "label": "Month",
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
            "labels": [d.period for d in data],
            "datasets": [
                {
                    "name": "Upcoming Interviews",
                    "values": [d.interviews for d in data],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

    return columns, data, None, chart


def get_quarterly_report(
    filters,
    values,
    hierarchy_clause,
):
    raw_data = frappe.db.sql(
        f"""
        SELECT
            YEAR(ir.date_of_interview) AS year,
            QUARTER(ir.date_of_interview) AS quarter,
            COUNT(ir.name) AS interviews
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        WHERE YEAR(ir.date_of_interview) = %(year)s
        {hierarchy_clause}
        GROUP BY
            YEAR(ir.date_of_interview),
            QUARTER(ir.date_of_interview)
        ORDER BY
            YEAR(ir.date_of_interview),
            QUARTER(ir.date_of_interview)
        """,
        values,
        as_dict=True,
    )

    quarter_labels = {
        1: "Jan-Mar",
        2: "Apr-Jun",
        3: "Jul-Sep",
        4: "Oct-Dec",
    }

    data = []

    for row in raw_data:
        data.append(
            {
                "period": (f"{quarter_labels[row.quarter]} {row.year}"),
                "interviews": row.interviews,
            }
        )

    columns = [
        {
            "label": "Quarter",
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
            "labels": [d["period"] for d in data],
            "datasets": [
                {
                    "name": "Upcoming Interviews",
                    "values": [d["interviews"] for d in data],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

    return columns, data, None, chart


def get_yearly_report(
    filters,
    values,
    hierarchy_clause,
):
    data = frappe.db.sql(
        f"""
        SELECT
            YEAR(ir.date_of_interview) AS period,
            COUNT(ir.name) AS interviews
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        WHERE YEAR(ir.date_of_interview) = %(year)s
        {hierarchy_clause}
        GROUP BY
            YEAR(ir.date_of_interview)
        ORDER BY
            YEAR(ir.date_of_interview)
        """,
        values,
        as_dict=True,
    )

    columns = [
        {
            "label": "Year",
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
            "labels": [str(d.period) for d in data],
            "datasets": [
                {
                    "name": "Upcoming Interviews",
                    "values": [d.interviews for d in data],
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
    conditions="",
):
    # Date filters
    if filters.get("from_date"):
        conditions += " AND ir.date_of_interview >= %(from_date)s"
        values["from_date"] = filters["from_date"]
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


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_customers_with_interviews(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters,
):
    return frappe.db.sql(
        """
        SELECT DISTINCT
            c.name,
            c.name1
        FROM `tabCustomer` c
        INNER JOIN `tabMarketing` m
            ON m.customer = c.name
        INNER JOIN `tabInterview` i
            ON i.marketing_link = m.name
        WHERE c.name LIKE %(txt)s
        ORDER BY c.creation DESC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )
