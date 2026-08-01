# vrugle_staffing_erp/utils/sales_order_status.py

import frappe

SERVICE_DOCTYPE_MAP = {
    "ruc": "RUC",
    "resume": "Resume",
    "jdc": "JDC",
    "training": "Training",
    "cover letter": "Cover Letter",
    "marketing": "Marketing",
}

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

DEPARTMENT_MAP_CACHE_KEY = "service_department_map"
DEPARTMENT_MAP_TTL = 3600  # department/service mapping changes rarely


def _get_department_map():
    cached = frappe.cache().get_value(DEPARTMENT_MAP_CACHE_KEY)
    if cached is not None:
        return cached

    rows = frappe.db.sql(
        """
        SELECT ds.service_name, d.name AS department
        FROM `tabDepartment Service` ds
        INNER JOIN `tabDepartment` d ON d.name = ds.parent
        """,
        as_dict=True,
    )
    mapping = {row.service_name: row.department for row in rows}
    frappe.cache().set_value(
        DEPARTMENT_MAP_CACHE_KEY, mapping, expires_in_sec=DEPARTMENT_MAP_TTL
    )
    return mapping


def invalidate_department_map_cache(doc=None, method=None):
    frappe.cache().delete_value(DEPARTMENT_MAP_CACHE_KEY)


def _resolve_doctype(service, department_map):
    key = (service or "").strip().lower()
    if key in SERVICE_DOCTYPE_MAP:
        return SERVICE_DOCTYPE_MAP[key]

    department = department_map.get(service)
    if department:
        return DEPARTMENT_FALLBACK_MAP.get(
            department.strip().lower(), DEFAULT_FALLBACK_DOCTYPE
        )

    return DEFAULT_FALLBACK_DOCTYPE


# ---------------------------------------------------------------------------
# Fetch service items for ALL of the customer's orders in ONE query
# ---------------------------------------------------------------------------
def _get_service_items_by_order(order_names):
    if not order_names:
        return {}

    rows = frappe.db.sql(
        """
        SELECT soi.parent AS sales_order, i.name AS service
        FROM `tabItems Table` soi
        INNER JOIN `tabItem` i ON i.name = soi.item
        WHERE soi.parent IN %(orders)s
            AND soi.parenttype = 'Sales Order'
            AND i.is_service = 1
            AND i.disabled = 0
        """,
        {"orders": order_names},
        as_dict=True,
    )

    by_order = {}
    for row in rows:
        by_order.setdefault(row.sales_order, []).append(row.service)
    return by_order


# ---------------------------------------------------------------------------
# Build ONE completion map covering every doctype/service combo needed
# across ALL orders — replaces the per-order, per-service exists() calls
# ---------------------------------------------------------------------------
def _build_completion_map(customer, service_items_by_order, department_map):
    needed_simple_doctypes = set()
    needed_fallback = {}  # doctype -> set(service)
    resolved_by_order = {}

    for order, services in service_items_by_order.items():
        resolved = []
        for service in services:
            doctype = _resolve_doctype(service, department_map)
            resolved.append((service, doctype))
            if doctype in FALLBACK_DOCTYPES:
                needed_fallback.setdefault(doctype, set()).add(service)
            else:
                needed_simple_doctypes.add(doctype)
        resolved_by_order[order] = resolved

    # 1 query per DISTINCT simple doctype for this customer (not per order)
    simple_completed = {}
    for doctype in needed_simple_doctypes:
        simple_completed[doctype] = bool(
            frappe.db.exists(doctype, {"customer": customer, "status": "Completed"})
        )

    # 1 query per DISTINCT fallback doctype, batched over every service needed
    fallback_completed = {}
    for doctype, services in needed_fallback.items():
        completed_services = set(
            frappe.get_all(
                doctype,
                filters={
                    "customer": customer,
                    "status": "Completed",
                    "service": ["in", list(services)],
                },
                pluck="service",
            )
        )
        for service in services:
            fallback_completed[(doctype, service)] = service in completed_services

    return resolved_by_order, simple_completed, fallback_completed


def _is_order_services_completed(
    order, resolved_by_order, simple_completed, fallback_completed
):
    resolved = resolved_by_order.get(order, [])
    if not resolved:
        return True
    for service, doctype in resolved:
        if doctype in FALLBACK_DOCTYPES:
            if not fallback_completed.get((doctype, service)):
                return False
        else:
            if not simple_completed.get(doctype):
                return False
    return True


def _are_all_payments_completed(sales_order_doc) -> bool:
    if not sales_order_doc.payment_terms:
        return False
    return all(
        (row.payment_status or "").strip() == "Verified"
        for row in sales_order_doc.payment_terms
    )

def on_service_update(customer: str) -> None:
    if not customer:
        return

    orders = frappe.get_all(
        "Sales Order",
        filters={"customer": customer, "docstatus": 1},
        pluck="name",
    )
    if not orders:
        return

    department_map = _get_department_map()
    service_items_by_order = _get_service_items_by_order(orders)
    resolved_by_order, simple_completed, fallback_completed = _build_completion_map(
        customer, service_items_by_order, department_map
    )

    for order in orders:
        so = frappe.get_cached_doc("Sales Order", order)
        services_done = _is_order_services_completed(
            order, resolved_by_order, simple_completed, fallback_completed
        )
        payments_done = _are_all_payments_completed(so)
        new_status = "Closed" if (services_done and payments_done) else "Open"

        if so.status != new_status:
            so.db_set("status", new_status, notify=True, commit=True)
            frappe.publish_realtime(
                "sales_order_status_updated",
                {"sales_order": order, "status": new_status},
                doctype="Sales Order",
                docname=order,
            )


# ---------------------------------------------------------------------------
# Hook shims
# ---------------------------------------------------------------------------
from verp_staffing.crm.api.customer_overall_status import compute_customer_status


def on_service_update_hook(doc, method=None):
    on_service_update(doc.customer)
    try:
        status = compute_customer_status(doc.customer)
        frappe.db.set_value("Customer", doc.customer, "overall_status", status)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Customer Status Update Failed")


def on_sales_order_update_hook(doc, method=None):
    """Single-order path — reuses the same batching machinery for consistency,
    trivially cheap since it's just one order."""
    department_map = _get_department_map()
    service_items_by_order = _get_service_items_by_order([doc.name])
    resolved_by_order, simple_completed, fallback_completed = _build_completion_map(
        doc.customer, service_items_by_order, department_map
    )
    services_done = _is_order_services_completed(
        doc.name, resolved_by_order, simple_completed, fallback_completed
    )
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
