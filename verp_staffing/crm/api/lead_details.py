import frappe

@frappe.whitelist()
def create_lead_details(doctype, docname, first_name, custom_values=None):
    import json
    if not docname:
        return
    
        # prevent duplicate
    if frappe.db.exists("Doctype Reference", {
        "reference_doctype": doctype,
        "reference_person": docname
    }):
        return
    
    lead_detail = frappe.new_doc("Lead Details")
    
    lead_detail.first_name = first_name
    
    if custom_values:
        if isinstance(custom_values, str):
            custom_values = json.loads(custom_values)

        for key, value in custom_values.items():
            if lead_detail.meta.has_field(key):
                lead_detail.set(key, value)
                
    # Link back to the parent
    lead_detail.append("reference_table", {
        "reference_doctype": doctype,
        "reference_person": docname
    })

    lead_detail.insert(ignore_permissions=True)
    return lead_detail.name