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


# ---------------------------------------------------------------------------
# Core: resolve which DocType handles a given service name
# ---------------------------------------------------------------------------
def _get_service_doctype(service_name: str) -> str:
    """
    Resolve the target DocType for a service name.

    Resolution order:
      1. Direct match in SERVICE_DOCTYPE_MAP
      2. Find which Department this service belongs to via
         Department → services (Table MultiSelect) → service_name
         then map that department to a fallback DocType
      3. DEFAULT_FALLBACK_DOCTYPE if nothing matches
    """
    key = (service_name or "").strip().lower()

    # 1. Direct map
    if key in SERVICE_DOCTYPE_MAP:
        return SERVICE_DOCTYPE_MAP[key]

    # 2. Department-based fallback
    # Find departments whose services table contains this service
    matches = frappe.get_all(
        "Department",  # parent DocType
        filters={"service_name": service_name},  # child table filter
        fields=["name"],
        limit=1,
    )

    if matches:
        dept_name = matches[0].name.strip().lower()
        return DEPARTMENT_FALLBACK_MAP.get(dept_name, DEFAULT_FALLBACK_DOCTYPE)

    # 3. Absolute fallback
    return DEFAULT_FALLBACK_DOCTYPE


# ---------------------------------------------------------------------------
# Check: are all services on a Sales Order completed?
# ---------------------------------------------------------------------------
def _are_all_services_completed(sales_order_doc) -> bool:
    """
    For each service row in sales_order_doc.services:
      - Resolve its DocType
      - Query all records of that DocType for the same customer
      - If ANY record has status 'Request For Update' → False immediately
      - If ALL records are 'Completed' → that service passes
      - If NO records exist yet → treat as Pending → False
    """
    customer = sales_order_doc.customer

    for row in sales_order_doc.services:
        service_name = row.service
        if not service_name:
            continue

        target_doctype = _get_service_doctype(service_name)

        records = frappe.get_all(
            target_doctype,
            filters={"customer": customer},
            fields=["status"],
        )

        if not records:
            # Service work hasn't started yet
            return False

        for record in records:
            status = (record.status or "").strip()
            if status != "Completed":
                return False

    return True


# ---------------------------------------------------------------------------
# Check: are all payment terms completed?
# ---------------------------------------------------------------------------
def _are_all_payments_completed(sales_order_doc) -> bool:
    """
    All rows in payment_terms child table must have
    payment_status == 'Completed'. Empty table → False.
    """
    if not sales_order_doc.payment_terms:
        return False

    return all(
        (row.payment_status or "").strip() == "Completed"
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

    so = frappe.get_doc("Sales Order", sales_order_name)

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
        filters={"customer": customer},
        fields=["name"],
    )

    for order in open_orders:
        evaluate_sales_order_status(order.name)


# ---------------------------------------------------------------------------
# Hook shims (called by Frappe doc_events, receive the doc object)
# ---------------------------------------------------------------------------
def on_service_update_hook(doc, method=None):
    """Shim for doc_events — extracts customer and delegates."""
    on_service_update(doc.customer)


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
