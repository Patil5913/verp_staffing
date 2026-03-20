import json
import frappe
from frappe.utils import now_datetime
from verp_staffing.crm.api.helpers import send_notification


@frappe.whitelist()
def get_auto_assign_employee(
    *,
    department: str,
    target_doctype: str,
    owner_field: str,
    extra_filters: dict | None = None,
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
        limit=1,
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

    employees = get_employees_with_role(role, department)
    if not employees:
        frappe.throw("No employees available for auto assignment")

    load = []
    for emp in employees:
        filters = {owner_field: emp}
        if extra_filters:
            filters.update(extra_filters)

        count = frappe.db.count(target_doctype, filters=filters)
        load.append({"employee": emp, "count": count})

    load.sort(key=lambda x: x["count"])
    return load[0]["employee"]


def get_employees_with_role(role, department=None):
    users = frappe.get_all(
        "User",
        filters={
            "enabled": 1,
            "name": [
                "in",
                frappe.get_all("Has Role", filters={"role": role}, pluck="parent"),
            ],
        },
        pluck="name",
    )

    if not users:
        return []

    employees = frappe.get_all(
        "Employee", filters={"user": ["in", users]}, pluck="name"
    )

    if not department:
        return employees

    return frappe.get_all(
        "Employee Assignment Detail",
        filters={"parent": ["in", employees], "department": department},
        pluck="parent",
        distinct=True,
    )

from verp_staffing.install import SERVICE_DOCTYPE_MAP

@frappe.whitelist()
def forward_candidate(customer, service, interview=None):

    customer_doc = frappe.get_doc("Customer", customer)
    service_key = service.strip().lower()

    try:
        stage = json.loads(customer_doc.stage) if customer_doc.stage else {}
    except Exception:
        stage = {}

    if service_key in ["cr", "onboarding"]:
        department = "CR" if service_key == "cr" else "Onboarding"

        return handle_CR_Onboarding_forward(
            customer=customer,
            department=department,
            manual_assign=frappe.form_dict.get("manual_assign"),
            assign_employee=frappe.form_dict.get("assign_employee")
        )

    if service_key in stage:

        doctype = SERVICE_DOCTYPE_MAP.get(service_key, "Other Services")
        department = stage[service_key][0].get("department")

        if doctype == "Other Services":
            if department == "Technical":
                doctype = "Technical Other Services"
            elif department == "Marketing":
                doctype = "Marketing Other Services"

        docs = frappe.get_all(
            doctype, filters={"customer": customer}, fields=["name", "assign_to"]
        )

        if not docs:
            return None

        if service_key == "jdc" and interview:
            frappe.db.set_value(doctype, docs[0].name, "interview", interview)

        if department == "Marketing":
            if doctype == "Marketing Other Services":
                for d in docs:
                    if d.assign_to:
                        fake_doc = frappe._dict({"assign_to": d.assign_to})
                        frappe.enqueue(
                            "verp_staffing.crm.api.auto_assign.notify_assignees",
                            queue="short",
                            doc=fake_doc,
                            service=service,
                            customer=customer,
                        )

                    stage[service_key].append(
                        {"department": department, "timestamp": str(now_datetime())}
                    )

                    frappe.db.set_value(
                        "Customer", customer, "stage", json.dumps(stage)
                    )

                    frappe.msgprint(f"Candidate is reforwarded for {service}. ")
                    
                    for d in docs:
                        frappe.db.set_value(doctype, d.name, "status", "Request for Update")

                return {"reforward": True, "doctype": doctype, "name": docs[0].name}

            for d in docs:
                if d.assign_to:
                    fake_doc = frappe._dict({"assign_to": d.assign_to})
                    frappe.enqueue(
                        "verp_staffing.crm.api.auto_assign.notify_assignees",
                        queue="short",
                        doc=fake_doc,
                        service=service,
                        customer=customer,
                    )

                stage[service_key].append(
                    {"department": department, "timestamp": str(now_datetime())}
                )

                frappe.db.set_value("Customer", customer, "stage", json.dumps(stage))

                frappe.msgprint(f"Candidate is reforwarded for {service}. ")

            return {"reforward": True, "doctype": doctype, "name": docs[0].name}

        for d in docs:
            frappe.db.set_value(doctype, d.name, "status", "Request for Update")

        stage[service_key].append(
            {"department": department, "timestamp": str(now_datetime())}
        )

        frappe.db.set_value("Customer", customer, "stage", json.dumps(stage))

        frappe.msgprint(
            f"Candidate is reforwarded for {service}. "
            f"Status updated to 'Request for Update'."
        )

        return {"reforward": True, "doctype": doctype, "name": docs[0].name}

    parents = frappe.db.sql(
        """
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name = %s
        """,
        (service,),
        as_dict=True,
    )

    if not parents:
        frappe.throw(f"No department found for service {service}")

    department = parents[0].parent

    doctype = SERVICE_DOCTYPE_MAP.get(service_key, "Other Services")

    if doctype == "Other Services":
        if department == "Technical":
            doctype = "Technical Other Services"
        elif department == "Marketing":
            doctype = "Marketing Other Services"

    assignee = get_auto_assign_employee(
        department=department, target_doctype=doctype, owner_field="assign_to"
    )

    service_doc = frappe.get_doc(
        {
            "doctype": doctype,
            "customer": customer,
            "service": service if "Other Services" in doctype else None,
            "department": department if doctype == "Other Services" else None,
            "assign_to": assignee,
            "status": "Pending",
            "forwarded_on": now_datetime() if "Other Services" in doctype else None,
        }
    )

    if service_key == "jdc" and interview:
        service_doc.interview = interview

    service_doc.insert(ignore_permissions=True)

    stage[service_key] = [{"department": department, "timestamp": str(now_datetime())}]

    frappe.db.set_value("Customer", customer, "stage", json.dumps(stage))

    frappe.enqueue(
        "verp_staffing.crm.api.auto_assign.notify_assignees",
        queue="short",
        doc=service_doc,
        service=service,
        customer=customer,
    )

    return {"reforward": False, "doctype": doctype, "name": service_doc.name}


def notify_assignees(doc, service, customer):

    emp_user = frappe.db.get_value("Employee", doc.assign_to, "user")
    if not emp_user:
        return

    send_notification(
        recipients=[emp_user],
        subject=f"New Candidate Assigned ({service})",
        message=(
            f"You have been assigned a new candidate.\n\n"
            f"Customer: {customer}\n"
            f"Service: {service}"
        ),
        send_email=1,
        send_system=1,
    )


@frappe.whitelist()
def get_customer_interviews(customer):

    if not customer:
        return []

    marketing_list = frappe.get_all(
        "Marketing", filters={"customer": customer}, pluck="name"
    )

    if not marketing_list:
        return []

    interviews = frappe.get_all(
        "Interview",
        filters={"marketing_link": ["in", marketing_list]},
        fields=["name", "company"],
    )

    formatted = []

    for d in interviews:
        if d.company:
            formatted.append(
                {
                    "label": d.company,
                    "value": d.name,
                }
            )
        else:
            formatted.append({"label": d.name, "value": d.name})

    return formatted

# CR/Onboarding Load analyzer
def get_department_load_employee(department):
    hierarchy = frappe.get_all(
        "Hierarchy",
        filters={"department": department},
        fields=["auto_assign_config"],
        limit=1,
    )

    if not hierarchy:
        frappe.throw(f"Hierarchy not configured for {department}")

    config = json.loads(hierarchy[0].auto_assign_config or "{}")
    role = config.get("role")

    if not role:
        frappe.throw("Auto assign role missing")

    employees = get_employees_with_role(role, department)

    if not employees:
        frappe.throw("No employees found")

    load = []

    for emp in employees:
        count = frappe.db.count(
            "Customer Department Route",
            filters={
                "assigned_to": emp,
                "department": department,
                "status": "Active",
            },
        )

        load.append({"employee": emp, "count": count})

    load.sort(key=lambda x: x["count"])

    return load[0]["employee"]

def handle_CR_Onboarding_forward(customer, department, manual_assign=0, assign_employee=None):
    
    existing = frappe.db.exists(
        "Customer Department Route",
        {
            "customer": customer,
            "department": department,
            "status": "Active",
        },
    )

    if existing:
        frappe.throw(f"Customer already forwarded to {department}")

    # 2. determine assignee
    if manual_assign:
        if not assign_employee:
            frappe.throw("Employee required for manual assignment")
        assignee = assign_employee
    else:
        assignee = get_department_load_employee(department)

    # Get current employee
    employee = frappe.get_all(
        "Employee",
        filters={"user": ["=", frappe.session.user]},
        pluck="name",
        distinct=True,
    )

    # 3. create new route
    route = frappe.get_doc({
        "doctype": "Customer Department Route",
        "customer": customer,
        "department": department,
        "status": "Active",
        "assigned_to": assignee,
        "forwarded_by": employee[0],
        "forwarded_on": now_datetime(),
    })

    route.insert(ignore_permissions=True)

    frappe.enqueue(
        "verp_staffing.crm.api.auto_assign.notify_assignees",
        queue="short",
        doc=customer,
        service=department,
        customer=customer,
    )

    return {
        "reforward": False,
        "doctype": "Customer",
        "name": customer
    }