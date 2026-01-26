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
    frappe.errprint(f"Employees: {employees}, with role {role} in department : {department}")
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
    # Get users with role
    users = frappe.get_all(
        "User",
        filters={
            "enabled": 1,
            "name": ["in", frappe.get_all(
                "Has Role",
                filters={"role": role},
                pluck="parent"
            )]
        },
        pluck="name"
    )
    frappe.errprint(f"Users with role {role}: {users}")
    if not users:
        return []

    # Get employees linked to those users
    employees = frappe.get_all(
        "Employee",
        filters={"user": ["in", users]},
        pluck="name"
    )
    frappe.errprint(f"Employees with role {role}: {employees}")
    if not employees:
        return []

    # If department filter is NOT required
    if not department:
        return employees

    # Filter via child table
    assigned_employees = frappe.get_all(
        "Employee Assignment Detail",
        filters={
            "parent": ["in", employees],
            "department": department
        },
        pluck="parent",
        distinct=True
    )
    frappe.errprint(f"Assigned employees in dept {department}: {assigned_employees}")
    return assigned_employees

SERVICE_DOCTYPE_MAP = {
    # Technical
    "ruc": "RUC",
    "resume": "Resume",

    # Marketing
    "marketing": "Marketing",

    # Add more explicit mappings here
}

@frappe.whitelist()
def forward_candidate(customer, service):
    from frappe.utils import now_datetime
    frappe.errprint(f"Forwarding candidate for customer {customer}, service {service}")
    doc = frappe.get_doc("Customer", customer)

    service_key = service.strip().lower()

    # ---- parse stage safely ----
    try:
        stage = json.loads(doc.stage) if doc.stage else {}
    except Exception:
        stage = {}

    # ---- prevent duplicate forwarding (service-level) ----
    if service_key in stage:
        frappe.throw(f"Candidate already forwarded for {service}")
    
    doctype = SERVICE_DOCTYPE_MAP.get(service_key, "Other Services")

    parents = frappe.db.sql("""
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name=%s
        """, (service), as_dict=True)
    department = parents[0].parent
    frappe.errprint(f"Department fetch result: {parents[0].parent}")
    # fetch department of the
    assignee = get_auto_assign_employee(
        department=parents[0].parent,
        target_doctype=doctype,
        owner_field="assign_to"
    )
    service_doc = None
    if doctype == "Other Services":
        service_doc = frappe.get_doc({
            "doctype": "Other Services",
            "customer": customer,
            "department": department,
            "service": service,
            "assign_to": assignee,
            "status": "Pending",
            "forwarded_on": now_datetime(),
            })
    else:
        service_doc = frappe.get_doc({
            "doctype": doctype,
            "customer": customer,
            "assign_to": assignee,
            "status": "Pending",
        })
    service_doc.insert(ignore_permissions=True)


    # ---- update stage ----
    stage[service_key] = {
        "department": department,
        "timestamp": str(now_datetime())
    }

    doc.stage = json.dumps(stage)
    doc.save(ignore_permissions=True)

    # ---- notify all assignees ----
    notify_assignees(service_doc, service, doc.name)

    return service_doc

def notify_assignees(doc, service, customer):
    assignees = set()

    emp_user = frappe.db.get_value("Employee", doc.assign_to, "user")
    if emp_user:
            assignees.add(emp_user)

    for user in assignees:
        send_notification(
            recipients=[user],
            subject=f"New Candidate Assigned for ({service})",
            message=(
                f"You have been assigned a new candidate.\n\n"
                f"Customer: {customer}\n"
                f"Service: {service}"
            ),
            send_email=1,
            send_system=1,
        )
