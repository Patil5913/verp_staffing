import frappe
import json


@frappe.whitelist()
def create_sales_order(opportunity, opportunity_from, party_name, data):
    import json

    # Parse JSON
    try:
        data = json.loads(data)
    except Exception:
        frappe.throw("Invalid JSON data received")

    data = frappe._dict(data)

    # Try to find customer linked with this opportunity
    customer_name = frappe.db.get_value(
        "Customer", {"opportunity": opportunity}, ["name", "title"], as_dict=True
    )

    if customer_name:
        # Load existing customer to use its fields
        customer_doc = frappe.get_doc("Customer", customer_name["name"])

    else:
        # No customer → create new
        customer_doc = frappe.get_doc(
            {
                "doctype": "Customer",
                "opportunity": opportunity,
                "customer_name": party_name or f"Customer-{frappe.utils.now()}",
            }
        )
        customer_doc.insert(ignore_permissions=True)
        customer_name = {"title": customer_doc.title, "name": customer_doc.name}
    services = []

    for service in data.services or []:
        services.append({
            "service": service
        })
    # -------- CREATE SALES ORDER -------- #
    so = frappe.get_doc(
        {
            "doctype": "Sales Order",
            "title": f"SO-{customer_name['title']}-{data.date}",
            "customer": customer_name["name"],
            "date": data.date,
            "opportunity": opportunity,
            "payment_terms": data.payment_terms,
            "services": services
        }
    )

    so.insert(ignore_permissions=True)

    # -------- UPDATE STATUS -------- #
    frappe.db.set_value("Opportunity", opportunity, "status", "Converted")

    if opportunity_from == "Lead":
        frappe.db.set_value("Lead", party_name, "status", "Won")

    frappe.db.commit()

    return {"sales_order": so.name, "customer": customer_name["name"]}
