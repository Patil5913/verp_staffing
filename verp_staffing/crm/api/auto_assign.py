import json
import frappe

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
    import json
    from frappe.utils import now_datetime

    doc = frappe.get_doc("Customer", customer)

    stage = json.loads(doc.stage or "{}")
    DEPARTMENT_ASSIGN_FIELD_MAP = {
        "sales": "resume_assign_to",        # example if sales forwards to resume
        "resume": "resume_assign_to",
        "technical": "technical_assign_to",
        "marketing": "marketing_assign_to",
    }
    dept_key = department.strip().lower()
    if dept_key not in DEPARTMENT_ASSIGN_FIELD_MAP:
        frappe.throw(f"Unsupported department: {department}")

    assign_field = DEPARTMENT_ASSIGN_FIELD_MAP.get(dept_key)

    # 1. Auto assign employee
    assignee = get_auto_assign_employee(
        department=department,
        target_doctype="Customer",
        owner_field=assign_field
    )

    # 2. Update stage
    stage[department] = {
        "status": "pending",
        "assigned_to": assignee,
        "timestamp": str(now_datetime())
    }

    # 3. Write assignment field
    doc.set(assign_field, assignee)
    doc.stage = json.dumps(stage)

    doc.save(ignore_permissions=True)

    return {
        "assigned_to": assignee,
        "department": department
    }
