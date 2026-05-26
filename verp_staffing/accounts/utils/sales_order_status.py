# verp_staffing/vrugle_staffing_erp/utils/sales_order_status.py

import frappe

# ---------------------------------------------------------------------------
# Static map: service name (lowercase) → DocType
# ---------------------------------------------------------------------------
SERVICE_DOCTYPE_MAP = {
    "ruc": "RUC",
    "resume": "Resume",
    "jdc": "JDC",
    "training": "Training",
    "cover letter": "Cover Letter",
    "marketing": "Marketing",
}

# ---------------------------------------------------------------------------
# Department fallback map: department name (lowercase) → DocType
# ---------------------------------------------------------------------------
DEPARTMENT_FALLBACK_MAP = {
    "technical": "Technical Other Services",
    "marketing": "Marketing Other Services",
}

DEFAULT_FALLBACK_DOCTYPE = "Other Services"

FALLBACK_DOCTYPES = {
    "Technical Other Services",
    "Marketing Other Services",
    "Other Services",
}


# ---------------------------------------------------------------------------
# Core: resolve which DocType handles a given service name
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Check: are all services on a Sales Order completed?
# ---------------------------------------------------------------------------
def _are_all_services_completed(sales_order_doc) -> bool:
    customer = sales_order_doc.customer

    # ------------------------------------------------------------------
    # 1. Fetch all active service items from SO
    # ------------------------------------------------------------------
    service_items = frappe.db.sql(
        """
        SELECT i.name
        FROM `tabItems Table` soi
        INNER JOIN `tabItem` i
            ON i.name = soi.item
        WHERE
            soi.parent = %s
            AND soi.parenttype = 'Sales Order'
            AND i.is_service = 1
            AND i.disabled = 0
        """,
        (sales_order_doc.name,),
        pluck=True,
    )

    if not service_items:
        return True

    # ------------------------------------------------------------------
    # 2. Build service → department map once
    # ------------------------------------------------------------------
    department_rows = frappe.db.sql(
        """
        SELECT
            ds.service_name,
            d.name AS department
        FROM `tabDepartment Service` ds
        INNER JOIN `tabDepartment` d
            ON d.name = ds.parent
        """,
        as_dict=True,
    )

    service_to_department = {
        row.service_name: row.department
        for row in department_rows
    }

    # ------------------------------------------------------------------
    # 3. Resolve service → target doctype
    # ------------------------------------------------------------------

    resolved_services = []

    for service in service_items:

        key = (service or "").strip().lower()

        # Direct mapping
        if key in SERVICE_DOCTYPE_MAP:
            resolved_services.append(
                {
                    "service": service,
                    "doctype": SERVICE_DOCTYPE_MAP[key],
                }
            )
            continue

        # Department fallback
        department = service_to_department.get(service)

        if department:
            dept_key = department.strip().lower()

            resolved_services.append(
                {
                    "service": service,
                    "doctype": DEPARTMENT_FALLBACK_MAP.get(
                        dept_key,
                        DEFAULT_FALLBACK_DOCTYPE,
                    ),
                }
            )
            continue

        # Default fallback
        resolved_services.append(
            {
                "service": service,
                "doctype": DEFAULT_FALLBACK_DOCTYPE,
            }
        )


    # ------------------------------------------------------------------
    # 4. Validate completion
    # ------------------------------------------------------------------
    for row in resolved_services:

        filters = {
            "customer": customer,
            "status": "Completed",
        }

        # Shared doctypes require service filter
        if row["doctype"] in FALLBACK_DOCTYPES:
            filters["service"] = row["service"]

        record = frappe.db.exists(
            row["doctype"],
            filters,
        )

        # No record found
        if not record:
            return False

    return True

# ---------------------------------------------------------------------------
# Check: are all payment terms completed?
# ---------------------------------------------------------------------------
def _are_all_payments_completed(sales_order_doc) -> bool:
    """
    All rows in payment_terms child table must have
    payment_status == 'Verified'. Empty table → False.
    """
    if not sales_order_doc.payment_terms:
        return False

    return all(
        (row.payment_status or "").strip() == "Verified"
        for row in sales_order_doc.payment_terms
    )


# ---------------------------------------------------------------------------
# Main: evaluate and update Sales Order status if needed
# ---------------------------------------------------------------------------
def evaluate_sales_order_status(sales_order_name: str) -> None:
    """
    Re-evaluate the status of a Sales Order and update it if changed.

    Closed  → both services completed AND all payments completed
    Open    → any service is Pending/Request For Update OR any payment pending
    """
    if not sales_order_name:
        return

    so = frappe.get_cached_doc("Sales Order", sales_order_name)

    services_done = _are_all_services_completed(so)
    payments_done = _are_all_payments_completed(so)
    new_status = "Closed" if (services_done and payments_done) else "Open"
    if so.status != new_status:
        # Use db_set to avoid triggering a full save/recursion
        so.db_set("status", new_status, notify=True, commit=True)
        frappe.publish_realtime(
            "sales_order_status_updated",
            {"sales_order": sales_order_name, "status": new_status},
            doctype="Sales Order",
            docname=sales_order_name,
        )


# ---------------------------------------------------------------------------
# Entry point: called from service DocType on_update hooks
# Finds all Open Sales Orders for this customer and re-evaluates them
# ---------------------------------------------------------------------------
def on_service_update(customer: str) -> None:
    """
    Called from any service DocType's on_update.
    Finds all Sales Orders for the customer and re-evaluates each.
    """
    if not customer:
        return

    open_orders = frappe.get_all(
        "Sales Order",
        filters={"customer": customer, "docstatus": 1},
        fields=["name"],
    )

    for order in open_orders:
        evaluate_sales_order_status(order.name)


# ---------------------------------------------------------------------------
# Hook shims (called by Frappe doc_events, receive the doc object)
# ---------------------------------------------------------------------------
from verp_staffing.crm.api.customer_overall_status import compute_customer_status
def on_service_update_hook(doc, method=None):
    """Shim for doc_events — extracts customer and delegates."""
    on_service_update(doc.customer)
     # unified status update 
    try:
        status = compute_customer_status(doc.customer)
        frappe.db.set_value("Customer", doc.customer, "overall_status", status)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Status Update Failed")


def on_sales_order_update_hook(doc, method=None):
    """
    Triggered on Sales Order save.
    Re-evaluates status based on current payment terms and services.
    We pass the doc directly to avoid a redundant frappe.get_doc() call.
    """
    services_done = _are_all_services_completed(doc)
    payments_done = _are_all_payments_completed(doc)

    new_status = "Closed" if (services_done and payments_done) else "Open"
    if doc.status != new_status:
        doc.db_set("status", new_status, notify=True, commit=True)
        frappe.publish_realtime(
            "sales_order_status_updated",
            {"sales_order": doc.name, "status": new_status},
            doctype="Sales Order",
            docname=doc.name,
        )
