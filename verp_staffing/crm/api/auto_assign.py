import json
import frappe

@frappe.whitelist()
def get_auto_assign_employee(department):
    import json

    hierarchy = frappe.get_all(
        "Hierarchy",
        filters={"department": department},
        fields=["auto_assign_config"],
        limit=1
    )

    if not hierarchy:
        frappe.throw("Hierarchy not configured")

    try:
        config = json.loads(hierarchy[0].auto_assign_config or "{}")
    except Exception:
        frappe.throw("Invalid auto assign config")

    role = config.get("role")
    if not role:
        frappe.throw("Auto assign role missing")

    employees = get_employees_with_role(role, department)

    if not employees:
        frappe.throw("No employees available for auto assignment")

    # Load balancing
    load = []
    for emp in employees:
        count = frappe.db.count(
            "Opportunity",
            filters={"opportunity_owner": emp}
        )
        load.append((emp, count))

    load.sort(key=lambda x: x[1])
    return load[0][0]

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
