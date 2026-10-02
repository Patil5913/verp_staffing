import json

import frappe


@frappe.whitelist()
def create_lead_details(
    doctype,
    docname,
    first_name,
    custom_values=None,
):
    if not docname:
        return

    # fast existence check
    existing = frappe.db.get_value(
        "Doctype Reference",
        {
            "reference_doctype": doctype,
            "reference_person": docname,
        },
        "parent",
    )

    if existing:
        return existing

    if isinstance(custom_values, str):
        custom_values = json.loads(custom_values)

    lead_detail = frappe.new_doc("Lead Detail Form")

    lead_detail.first_name = first_name

    # cache valid fields once
    valid_fields = lead_detail.meta._fields

    if custom_values:
        for key, value in custom_values.items():

            if key in valid_fields:
                lead_detail.set(key, value)

    lead_detail.append(
        "reference_table",
        {
            "reference_doctype": doctype,
            "reference_person": docname,
        },
    )

    lead_detail.insert(ignore_permissions=True)

    return lead_detail.name