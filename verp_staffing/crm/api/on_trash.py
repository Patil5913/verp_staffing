import frappe

@frappe.whitelist()
def unlink_and_clean_lead_detail(doctype, docname, lead_details_field="lead_details"):
    lead_details_name = frappe.db.get_value(doctype, docname, lead_details_field)

    if not lead_details_name:
        return

    frappe.db.set_value(doctype, docname, lead_details_field, None)

    try:
        lead_detail_doc = frappe.get_doc("Lead Detail Form", lead_details_name)

        if hasattr(lead_detail_doc, "reference_table"):
            rows_to_delete = [
                row for row in lead_detail_doc.reference_table
                if row.reference_doctype == doctype and row.reference_person == docname
            ]
            for row in rows_to_delete:
                lead_detail_doc.remove(row)

            lead_detail_doc.save(ignore_permissions=True)

    except frappe.DoesNotExistError:
        pass