import json
import frappe
from verp_staffing.crm.api.helpers import send_notification

@frappe.whitelist()
def get_auto_assign_employee(
    *,
    department: str,
    target_doctype: str,
    owner_field: str,
    extra_filters: dict | None = None
):
    """
    Generic auto-assign resolver.

    department     -> Department name
    target_doctype -> DocType to count load from (Opportunity, Customer, Ticket, etc.)
    owner_field    -> Fieldname that stores Employee link
    extra_filters  -> Optional additional filters for load calculation
    """

    # 1. Fetch hierarchy config
    hierarchy = frappe.get_all(
        "Hierarchy",
        filters={"department": department},
        fields=["auto_assign_config"],
        limit=1
    )

    if not hierarchy:
        frappe.throw(f"Hierarchy not configured for department {department}")

    try:
        config = json.loads(hierarchy[0].auto_assign_config or "{}")
    except Exception:
        frappe.throw("Invalid auto assign config")

    role = config.get("role")
    if not role:
        frappe.throw("Auto assign role missing in hierarchy")

    # 2. Resolve employees eligible for this role
    employees = get_employees_with_role(role, department)

    if not employees:
        frappe.throw("No employees available for auto assignment")

    # 3. Calculate load
    load = []

    for emp in employees:
        filters = {owner_field: emp}

        if extra_filters:
            filters.update(extra_filters)

        count = frappe.db.count(target_doctype, filters=filters)

        load.append({
            "employee": emp,
            "count": count
        })

    # 4. Pick least loaded
    load.sort(key=lambda x: x["count"])
    return load[0]["employee"]

def get_employees_with_role(role, department=None):
    users = frappe.get_all(
        "Has Role",
        filters={"role": role},
        pluck="parent"
    )

    if not users:
        return []

    filters = {"user": ["in", users]}
    if department:
        filters["department"] = department

    return frappe.get_all(
        "Employee",
        filters=filters,
        pluck="name"
    )

@frappe.whitelist()
def forward_candidate(customer, department):
    from frappe.utils import now_datetime

    doc = frappe.get_doc("Customer", customer)

    dept_key = department.strip().lower()

    DEPARTMENT_DOC_MAP = {
        "resume": "Resume",
        "technical": "RUC",
    }

    doctype = DEPARTMENT_DOC_MAP.get(dept_key)
    if not doctype:
        frappe.throw("Invalid department")

    # ---- parse stage safely ----
    try:
        stage = json.loads(doc.stage) if doc.stage else {}
    except Exception:
        stage = {}

    # ---- prevent duplicate forwarding ----
    if dept_key in stage:
        frappe.throw(f"Candidate already forwarded to {dept_key.title()} department")
    # Parse existing stage safely
    try:
        stage = json.loads(doc.stage) if doc.stage else {}
    except Exception:
        stage = {}

    assignee = get_auto_assign_employee(
        department=department,
        target_doctype=doctype,
        owner_field="assign_to"
    )
    frappe.errprint(f"Auto-assigned to {assignee}")
    # ---- create department document ----
    dept_doc = frappe.get_doc({
        "doctype": doctype,
        "customer": customer,
        "assign_to": assignee,
        "status": "Pending",
    })
    frappe.errprint(f"dept_doc {dept_doc}")

    dept_doc.insert(ignore_permissions=True)

    stage[dept_key] = {
        "assigned_to": assignee,
        "timestamp": str(now_datetime())
    }

    doc.stage = json.dumps(stage)

    doc.save(ignore_permissions=True)

    # ---- send notification ----
     # Resolve assignee user email
    assignee_user = frappe.db.get_value("Employee", assignee, "user")

    if assignee_user:
        send_notification(
            recipients=[assignee_user],
            subject=f"New Candidate Assigned ({department})",
            message=(
                f"You have been assigned a new candidate.\n\n"
                f"Customer: {doc.name}\n"
                f"Department: {department}\n"
                f"Status: Pending"
            ),
            reference_doctype=doctype,
            reference_name=dept_doc.name,
            send_email=1,
            send_system=1,
        )

    return dept_doc