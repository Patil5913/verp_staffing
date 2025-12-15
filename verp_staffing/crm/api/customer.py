import frappe

def get_department_info(customer, doctype, assign_field="assign_to"):
    docs = frappe.get_all(
        doctype,
        filters={"customer": customer},
        fields=["name", assign_field, "status", "modified"],
        order_by="modified desc",
        limit=1,
    )

    if not docs:
        return None

    doc = docs[0]

    employee_name = None
    if doc.get(assign_field):
        employee_name = frappe.db.get_value(
            "Employee",
            doc[assign_field],
            "employee_name"
        )

    return {
        "docname": doc.name,
        "assigned_to": doc.get(assign_field),
        "assigned_to_name": employee_name,
        "status": doc.get("status"),
        "last_updated": doc.get("modified"),
    }

@frappe.whitelist()
def get_customer_department_panels(customer):
    return {
        "resume": get_department_info(
            customer=customer,
            doctype="Resume",
            assign_field="assign_to",
        ),
        "technical": get_department_info(
            customer=customer,
            doctype="RUC",
            assign_field="assign_to",
        ),
    }
