# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PartyType(Document):
    pass


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_party_type(doctype, txt, searchfield, start, page_len, filters):
    account_type = None

    params = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    }

    conditions = ["name LIKE %(txt)s"]

    if filters:
        if filters.get("account_type"):
            account_type = filters.get("account_type")

        elif filters.get("account"):
            account_type = frappe.db.get_value(
                "Account",
                filters.get("account"),
                "account_type",
            )

        if account_type:
            params["account_type"] = account_type

            if account_type in ("Receivable", "Payable"):
                conditions.append(
                    "(account_type = %(account_type)s OR name = 'Employee')"
                )
            else:
                conditions.append("account_type = %(account_type)s")

    query = (
        "SELECT name "
        "FROM `tabParty Type` "
        "WHERE "
        + " AND ".join(conditions)
        + " ORDER BY name "
        "LIMIT %(page_len)s OFFSET %(start)s"
    )

    result = frappe.db.sql(query, params)

    return result or []