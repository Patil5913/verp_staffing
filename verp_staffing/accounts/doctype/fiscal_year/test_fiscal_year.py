# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFiscalYear(FrappeTestCase):
    pass


def create_fiscal_year_if_not_exists(
    fiscal_year,
    company,
    start_date,
    end_date,
    **overrides,
):
    """
    Ensure an active Fiscal Year exists and is linked to the company.

    Flow:
    1. If active FY exists by name:
        - append company if missing
        - return FY
    2. Else if company already belongs to active FY:
        - return that FY
    3. Else create new FY

    Extra kwargs apply only during NEW Fiscal Year creation.
    """

    if not company:
        frappe.throw("Company is required")

    # ------------------------------------------------------------------
    # 1. Existing ACTIVE Fiscal Year by name
    # ------------------------------------------------------------------
    if frappe.db.exists("Fiscal Year", {"name": fiscal_year, "disabled": 0}):
        fy = frappe.get_doc("Fiscal Year", fiscal_year)

        existing_companies = {
            row.company for row in fy.get("included_companies", [])
        }

        if company not in existing_companies:
            fy.append("included_companies", {"company": company})
            fy.save(ignore_permissions=True)

        return fy

    # ------------------------------------------------------------------
    # 2. Existing ACTIVE Fiscal Year for company
    # ------------------------------------------------------------------
    existing_fy = frappe.db.sql(
        """
        SELECT fy.name
        FROM `tabFiscal Year` fy
        INNER JOIN `tabFiscal Year Company` fyc
            ON fyc.parent = fy.name
        WHERE
            fy.disabled = 0
            AND fyc.company = %(company)s
        LIMIT 1
        """,
        {"company": company},
        as_dict=True,
    )

    if existing_fy:
        return frappe.get_doc("Fiscal Year", existing_fy[0].name)

    # ------------------------------------------------------------------
    # 3. Create new Fiscal Year
    # ------------------------------------------------------------------
    fy = frappe.get_doc(
        {
            "doctype": "Fiscal Year",
            "year": fiscal_year,
            "year_start_date": start_date,
            "year_end_date": end_date,
            "disabled": 0,
            **overrides,
        }
    )

    fy.append("included_companies", {"company": company})

    fy.insert(ignore_permissions=True)

    return fy