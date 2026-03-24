import frappe
import json

@frappe.whitelist()
def create_sales_order(**kwargs):

    opportunity = kwargs.get("opportunity")
    opportunity_from_lead = kwargs.get("opportunity_from_lead")
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

    # Get opportunity_owner to set as customer_owner
    opportunity_owner = frappe.db.get_value(
        "Opportunity", opportunity, "opportunity_owner"
    )

    # Check if Customer already exists for this Opportunity
    existing_customer = frappe.db.get_value(
        "Customer",
        {
            "customer_from": "Opportunity",
            "party_name": opportunity,
        },
        ["name", "name1"],
        as_dict=True,
    )

    if existing_customer:
        customer_doc = frappe.get_doc("Customer", existing_customer["name"])
        customer_name = {
            "name": customer_doc.name,
            "title": customer_doc.name1 or customer_doc.name,
        }

        # Fix customer_owner if it was not set before
        if not customer_doc.customer_owner and opportunity_owner:
            frappe.db.set_value(
                "Customer", customer_doc.name, "customer_owner", opportunity_owner
            )
            customer_doc.customer_owner = opportunity_owner

    else:
        opportunity_doc = frappe.get_doc("Opportunity", opportunity)

        base_name = (
            opportunity_doc.title
            or getattr(opportunity_doc, "name1", None)
            or opportunity_from_lead
            or f"Customer-{frappe.utils.now()}"
        )

        customer_data = {
            "doctype": "Customer",
            "customer_from": "Opportunity",
            "party_name": opportunity,
            "name1": base_name,
            # ── Set customer_owner from opportunity_owner ──
            "customer_owner": opportunity_owner or None,
        }

        customer_doc = frappe.get_doc(customer_data)
        customer_doc.insert(ignore_permissions=True)

        customer_name = {
            "name": customer_doc.name,
            "title": customer_doc.name1 or customer_doc.name,
        }

    # Build services list
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

    # ── Link Sales Order to Lead Detail Form ──
    lead_detail_name = frappe.db.get_value(
        "Customer", customer_doc.name, "lead_details"
    )

    if lead_detail_name:
        frappe.db.set_value(
            "Lead Detail Form", lead_detail_name, "sales_order", so.name
        )
    else:
        # Fallback: find Lead Detail Form via Lead
        if opportunity_from_lead:
            lead_detail_name = frappe.db.get_value(
                "Lead", opportunity_from_lead, "lead_details"
            )
            if lead_detail_name:
                frappe.db.set_value(
                    "Lead Detail Form", lead_detail_name, "sales_order", so.name
                )

    frappe.db.set_value("Opportunity", opportunity, "status", "Converted")

    if opportunity_from_lead:
        frappe.db.set_value("Lead", opportunity_from_lead, "status", "Won")

    frappe.db.commit()

    return {
        "sales_order": so.name,
        "customer": customer_name["name"],
    }


@frappe.whitelist()
def get_sales_order_services(sales_order):
    """
    Returns list of service names from a Sales Order.
    Uses ignore_permissions on child table fetch to avoid
    ERP Configuration permission error.
    """
    services = frappe.db.get_all(
        "SalesOrderServices",
        filters={
            "parent": sales_order,
            "parenttype": "Sales Order",
        },
        fields=["service"],
        ignore_permissions=True,
    )
    return [row.service for row in services if row.service]
