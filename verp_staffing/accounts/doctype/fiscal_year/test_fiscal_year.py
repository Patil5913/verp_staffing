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
    """
    Ensure an active Fiscal Year exists and is linked to given companies.
    Extra kwargs apply only when a NEW Fiscal Year is being created.
    """

    if not companies:
        frappe.throw("At least one company is required")

    companies = list(dict.fromkeys(companies))
    
    # 1. Check ACTIVE FY by name
    if frappe.db.exists("Fiscal Year", {"name": fiscal_year, "disabled": 0}):
        fy = frappe.get_doc("Fiscal Year", fiscal_year)

        existing_companies = {row.company for row in fy.included_companies}
        added = False

        for company in companies:
            if company not in existing_companies:
                fy.append("included_companies", {"company": company})
                added = True

        if added:
            fy.save(ignore_permissions=True)

        return fy
    
    # 2. Check existing ACTIVE FY for companies
    for company in companies:
        fy_name = frappe.db.get_value(
            "Fiscal Year Company",
            {"company": company, "parenttype": "Fiscal Year"},
            "parent",
        )

        if fy_name:
            fy_disabled = frappe.db.get_value("Fiscal Year", fy_name, "disabled")
            if not fy_disabled:
                return frappe.get_doc("Fiscal Year", fy_name)

    # 3. Create new Fiscal Year
    defaults = {
        "doctype": "Fiscal Year",
        "year": fiscal_year,
        "year_start_date": start_date,
        "year_end_date": end_date,
        "disabled": 0,
        **overrides,
    }

    fy = frappe.get_doc(defaults)

    for company in companies:
        fy.append("included_companies", {"company": company})

    fy.insert(ignore_permissions=True)
    return fy
