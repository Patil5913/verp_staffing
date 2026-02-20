# import frappe
# import json


# @frappe.whitelist()
# def create_sales_order(opportunity, opportunity_from, party_name, data):
#     import json

#     # Parse JSON
#     try:
#         data = json.loads(data)
#     except Exception:
#         frappe.throw("Invalid JSON data received")

#     data = frappe._dict(data)

#     # Try to find customer linked with this opportunity
#     customer_name = frappe.db.get_value(
#         "Customer", {"opportunity": opportunity}, ["name", "title"], as_dict=True
#     )

#     if customer_name:
#         # Load existing customer to use its fields
#         customer_doc = frappe.get_doc("Customer", customer_name["name"])

#     else:
#         # No customer → create new
#         customer_doc = frappe.get_doc(
#             {
#                 "doctype": "Customer",
#                 "opportunity": opportunity,
#                 "customer_name": party_name or f"Customer-{frappe.utils.now()}",
#             }
#         )
#         customer_doc.insert(ignore_permissions=True)
#         customer_name = {"title": customer_doc.title, "name": customer_doc.name}
#     services = []

#     for service in data.services or []:
#         services.append({
#             "service": service
#         })
#     # -------- CREATE SALES ORDER -------- #
#     so = frappe.get_doc(
#         {
#             "doctype": "Sales Order",
#             "title": f"SO-{customer_name['title']}-{data.date}",
#             "customer": customer_name["name"],
#             "date": data.date,
#             "opportunity": opportunity,
#             "payment_terms": data.payment_terms,
#             "services": services
#         }
#     )

#     so.insert(ignore_permissions=True)

#     # -------- UPDATE STATUS -------- #
#     frappe.db.set_value("Opportunity", opportunity, "status", "Converted")

#     if opportunity_from == "Lead":
#         frappe.db.set_value("Lead", party_name, "status", "Won")

#     frappe.db.commit()

#     return {"sales_order": so.name, "customer": customer_name["name"]}

import frappe
import json

@frappe.whitelist()
def create_sales_order(opportunity, opportunity_from, party_name, data):
    # Parse JSON safely
    try:
        data = json.loads(data)
    except Exception:
        frappe.throw("Invalid JSON data received")

    data = frappe._dict(data)

    # Try to find an existing customer linked with this opportunity
    customer_doc = None
    customer_name = None

    existing_customer = frappe.db.get_value(
        "Customer", {"opportunity": opportunity}, ["name", "title"], as_dict=True
    )

    if existing_customer:
        # Use existing customer
        customer_doc = frappe.get_doc("Customer", existing_customer["name"])
        customer_name = {"name": customer_doc.name, "title": customer_doc.title}
    else:
        # Create new customer
        opportunity_doc = frappe.get_doc("Opportunity", opportunity)

        # Decide base_name
        base_name = (
            opportunity_doc.title
            or opportunity_doc.name1
            or party_name
            or f"Customer-{frappe.utils.now()}"
        )

        customer_data = {
            "doctype": "Customer",
            "opportunity": opportunity,
            "customer_from": opportunity_doc.opportunity_from or "Opportunity",
            "name1": base_name,
        }

        # Only set party_name if it exists and is valid
        if opportunity_doc.opportunity_from and opportunity_doc.party_name:
            customer_data["party_name"] = opportunity_doc.party_name

        # Insert new customer
        customer_doc = frappe.get_doc(customer_data)
        customer_doc.insert(ignore_permissions=True)
        customer_name = {"name": customer_doc.name, "title": customer_doc.name1 or customer_doc.name}

    # -------- CREATE SALES ORDER -------- #
    services = []
    for service in data.services or []:
        services.append({"service": service})

    so_title = f"SO-{customer_name['title']}-{data.date}"
    so = frappe.get_doc(
        {
            "doctype": "Sales Order",
            "title": so_title,
            "customer": customer_name["name"],
            "date": data.date,
            "opportunity": opportunity,
            "payment_terms": data.payment_terms,
            "services": services,
        }
    )
    so.insert(ignore_permissions=True)

    # -------- UPDATE STATUS -------- #
    frappe.db.set_value("Opportunity", opportunity, "status", "Converted")

    if opportunity_from == "Lead" and party_name:
        frappe.db.set_value("Lead", party_name, "status", "Won")

    frappe.db.commit()

    return {"sales_order": so.name, "customer": customer_name["name"]}