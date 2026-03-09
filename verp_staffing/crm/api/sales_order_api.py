import frappe
import json


@frappe.whitelist()
def create_sales_order(**kwargs):

    opportunity = kwargs.get("opportunity")
    opportunity_from = kwargs.get("opportunity_from")
    party_name = kwargs.get("party_name")
    data = kwargs.get("data")

    if not opportunity:
        frappe.throw("Opportunity is required")

    # Parse JSON safely
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            frappe.throw("Invalid JSON data received")

    data = frappe._dict(data or {})

    customer_doc = None
    customer_name = None

    existing_customer = frappe.db.get_value(
        "Customer",
        {"opportunity": opportunity},
        ["name", "title"],
        as_dict=True,
    )

    if existing_customer:
        customer_doc = frappe.get_doc("Customer", existing_customer["name"])
        customer_name = {"name": customer_doc.name, "title": customer_doc.title}

    else:
        opportunity_doc = frappe.get_doc("Opportunity", opportunity)

        base_name = (
            opportunity_doc.title
            or opportunity_doc.name1
            or party_name
            or f"Customer-{frappe.utils.now()}"
        )

        customer_data = {
            "doctype": "Customer",
            "opportunity": opportunity,
            "customer_from": "Opportunity",
            "party_name": opportunity,
            "name1": base_name,
        }

        if opportunity_doc.opportunity_from and opportunity_doc.party_name:
            customer_data["party_name"] = opportunity_doc.party_name

        customer_doc = frappe.get_doc(customer_data)
        customer_doc.insert(ignore_permissions=True)

        customer_name = {
            "name": customer_doc.name,
            "title": customer_doc.name1 or customer_doc.name,
        }

    services = []

    for service in data.get("services", []):
        services.append({"service": service})

    so_title = f"SO-{customer_name['title']}-{data.get('date')}"

    so = frappe.get_doc(
        {
            "doctype": "Sales Order",
            "title": so_title,
            "customer": customer_name["name"],
            "date": data.get("date"),
            "opportunity": opportunity,
            "payment_terms": data.get("payment_terms", []),
            "services": services,
        }
    )

    so.insert(ignore_permissions=True)

    frappe.db.set_value("Opportunity", opportunity, "status", "Converted")

    if opportunity_from == "Lead" and party_name:
        frappe.db.set_value("Lead", party_name, "status", "Won")

    frappe.db.commit()

    return {"sales_order": so.name, "customer": customer_name["name"]}
