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

def get_or_create_lead_detail(reference_doctype, reference_person):
    """The Lead Detail Form a Lead / Opportunity / Customer is linked to
    (through its Doctype Reference row), creating and linking one first if the
    record predates that link or lost it.

    A Lead's form is normally made on insert (Lead.after_insert), and the
    Opportunity / Customer raised from it just append their own reference row
    to that same form — so "no form found" only happens to a record whose form
    was never created. Rather than refuse to convert it, give it one now: the
    same create_lead_details call a fresh Lead would have made, keyed to the
    source record so the chain (Lead -> Opportunity -> Customer) stays on one
    form.
    """
    if not (reference_doctype and reference_person):
        return None

    existing = frappe.db.get_value(
        "Doctype Reference",
        {"reference_doctype": reference_doctype, "reference_person": reference_person},
        "parent",
    )
    if existing:
        return existing

    title = frappe.db.get_value(reference_doctype, reference_person, "name1") or reference_person
    name = create_lead_details(reference_doctype, reference_person, title)

    if name and frappe.get_meta(reference_doctype).has_field("lead_details"):
        frappe.db.set_value(reference_doctype, reference_person, "lead_details", name, update_modified=False)

    return name
