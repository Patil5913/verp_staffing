import frappe


@frappe.whitelist()
def unlink_and_clean_lead_detail(
    doctype,
    docname,
    lead_details_field="lead_details",
):
    lead_details_name = frappe.db.get_value(
        doctype,
        docname,
        lead_details_field,
    )

    if not lead_details_name:
        return

    # unlink from parent
    frappe.db.set_value(
        doctype,
        docname,
        lead_details_field,
        None,
        update_modified=False,
    )

    # delete matching child rows directly
    frappe.db.delete(
        "Lead Detail Reference",
        {
            "parent": lead_details_name,
            "reference_doctype": doctype,
            "reference_person": docname,
        },
    )