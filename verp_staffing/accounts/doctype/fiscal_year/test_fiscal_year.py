# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFiscalYear(FrappeTestCase):
    pass


def create_fiscal_year_if_not_exists(
    fiscal_year,
    companies,
    start_date,
    end_date,
    **overrides,
):
    if not companies:
        frappe.throw("At least one company is required")

    overrides.pop("year", None)
    overrides.pop("year_start_date", None)
    overrides.pop("year_end_date", None)
    overrides.pop("included_companies", None)

    # 1. If Fiscal Year exists by name
    if frappe.db.exists("Fiscal Year", fiscal_year):
        fy = frappe.get_doc("Fiscal Year", fiscal_year)

        # Ensure all companies are linked
        existing_companies = {c.company for c in fy.included_companies}

        for company in companies:
            if company not in existing_companies:
                fy.append("included_companies", {"company": company})

        fy.save(ignore_permissions=True)
        return fy

    # 2. Check if FY exists for any company
    for company in companies:
        existing = frappe.db.get_value(
            "Fiscal Year Company",
            {"company": company},
            "parent",
        )
        if existing:
            return frappe.get_doc("Fiscal Year", existing)

    # 3. Create new Fiscal Year
    fy = frappe.get_doc(
        {
            "doctype": "Fiscal Year",
            "year": fiscal_year,
            "year_start_date": start_date,
            "year_end_date": end_date,
            **overrides,
        }
    )

    for company in companies:
        fy.append("included_companies", {"company": company})

    fy.insert(ignore_permissions=True)

    return fy
