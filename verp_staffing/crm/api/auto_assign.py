# import json
# import frappe
# from verp_staffing.crm.api.helpers import send_notification

# @frappe.whitelist()
# def get_auto_assign_employee(
#     *,
#     department: str,
#     target_doctype: str,
#     owner_field: str,
#     extra_filters: dict | None = None
# ):
#     """
#     Generic auto-assign resolver.

#     department     -> Department name
#     target_doctype -> DocType to count load from (Opportunity, Customer, Ticket, etc.)
#     owner_field    -> Fieldname that stores Employee link
#     extra_filters  -> Optional additional filters for load calculation
#     """
#     # 1. Fetch hierarchy config
#     hierarchy = frappe.get_all(
#         "Hierarchy",
#         filters={"department": department},
#         fields=["auto_assign_config"],
#         limit=1
#     )

#     if not hierarchy:
#         frappe.throw(f"Hierarchy not configured for department {department}")

#     try:
#         config = json.loads(hierarchy[0].auto_assign_config or "{}")
#     except Exception:
#         frappe.throw("Invalid auto assign config")

#     role = config.get("role")
#     if not role:
#         frappe.throw("Auto assign role missing in hierarchy")

#     # 2. Resolve employees eligible for this role
#     employees = get_employees_with_role(role, department)
#     if not employees:
#         frappe.throw("No employees available for auto assignment")

#     # 3. Calculate load
#     load = []

#     for emp in employees:
#         filters = {owner_field: emp}

#         if extra_filters:
#             filters.update(extra_filters)

#         count = frappe.db.count(target_doctype, filters=filters)

#         load.append({
#             "employee": emp,
#             "count": count
#         })

#     # 4. Pick least loaded
#     load.sort(key=lambda x: x["count"])
#     return load[0]["employee"]

# def get_employees_with_role(role, department=None):
#     # Get users with role
#     users = frappe.get_all(
#         "User",
#         filters={
#             "enabled": 1,
#             "name": ["in", frappe.get_all(
#                 "Has Role",
#                 filters={"role": role},
#                 pluck="parent"
#             )]
#         },
#         pluck="name"
#     )
#     if not users:
#         return []

#     # Get employees linked to those users
#     employees = frappe.get_all(
#         "Employee",
#         filters={"user": ["in", users]},
#         pluck="name"
#     )
#     if not employees:
#         return []

#     # If department filter is NOT required
#     if not department:
#         return employees

#     # Filter via child table
#     assigned_employees = frappe.get_all(
#         "Employee Assignment Detail",
#         filters={
#             "parent": ["in", employees],
#             "department": department
#         },
#         pluck="parent",
#         distinct=True
#     )
#     return assigned_employees

# SERVICE_DOCTYPE_MAP = {
#     # Technical
#     "ruc": "RUC",
#     "resume": "Resume",
#     "jdc":"JDC",
#     "training":"Training",
#     "cover letter": "Cover Letter",

#     # Marketing
#     "marketing": "Marketing",

#     # Add more explicit mappings here
# }

# @frappe.whitelist()
# def forward_candidate(customer, service):
#     from frappe.utils import now_datetime
#     doc = frappe.get_doc("Customer", customer)
#     count = 1


#     service_key = service.strip().lower()


#     # ---- parse stage safely ----
#     try:
#         stage = json.loads(doc.stage) if doc.stage else {}
#         frappe.errprint(f"stage {stage}")
#         frappe.errprint(f"servie key : {stage[service_key]}")
#     except Exception:
#         stage = {}

#     # ---- prevent duplicate forwarding (service-level) ----
#     # if service_key in stage:

#     #     doctype = SERVICE_DOCTYPE_MAP.get(service_key, "Other Services")
#     #     department = stage[service_key].get("department")

#     #     if doctype == "Other Services":
#     #         if department == "Technical":
#     #             doctype = "Technical Other Services"
#     #         elif department == "Marketing":
#     #             doctype = "Marketing Other Services"

#     #     names = frappe.get_all(
#     #         doctype,
#     #         filters={"customer": customer},
#     #         pluck="name"
#     #     )

#     #     if not names:
#     #         return

#     #     for name in names:
#     #         frappe.db.set_value(
#     #             doctype,
#     #             name,
#     #             "status",
#     #             "Request for Update"
#     #         )

#     #     stage[service_key]["count"] = stage[service_key].get("count", 0) + 1
#     #     existing_stage = stage or {}

#     #     if service_key not in existing_stage:
#     #         existing_stage[service_key] = {
#     #             "department": department,
#     #             "timestamp": str(now_datetime()),
#     #             "count": 0
#     #         }

#     #     doc.stage = json.dumps(existing_stage)
#     #     doc.save(ignore_permissions=True)

#     #     frappe.msgprint(f"Candidate is reforwarded for {service}. Status updated to 'Request for Update'.")

#     #     return
#     if service_key in stage:

#         doctype = SERVICE_DOCTYPE_MAP.get(service_key, "Other Services")
#         department = stage[service_key].get("department")

#         if doctype == "Other Services":
#             if department == "Technical":
#                 doctype = "Technical Other Services"
#             elif department == "Marketing":
#                 doctype = "Marketing Other Services"

#         names = frappe.get_all(
#             doctype,
#             filters={"customer": customer},
#             pluck="name"
#         )

#         if not names:
#             return

#         for name in names:
#             frappe.db.set_value(
#                 doctype,
#                 name,
#                 "status",
#                 "Request for Update"
#             )

#         # ✅ increment only
#         stage[service_key]["count"] = stage[service_key].get("count", 0) + 1
        
#         stage[service_key] = {
#             "department": department,
#             "timestamp": str(now_datetime()),
#             "count" : stage[service_key]["count"]
#         }

#         doc.stage = json.dumps(stage)
#         doc.save(ignore_permissions=True)

#         frappe.msgprint(
#             f"Candidate is re-forwarded for {service}. "
#             f"Count: {stage[service_key]['count']}"
#         )

#         return


#     parents = frappe.db.sql("""
#         SELECT parent FROM `tabDepartment Service`
#         WHERE service_name=%s
#         """, (service), as_dict=True)
    
#     department = parents[0].parent

#     doctype = SERVICE_DOCTYPE_MAP.get(service_key.lower(), "Other Services")
#     frappe.errprint(f"{doctype} , {service_key} ")
#     if(department == "Technical" and doctype == "Other Services"):
#         doctype = "Technical Other Services"
#     elif(department == "Marketing" and doctype == "Other Services"):
#         doctype = "Marketing Other Services"

#     frappe.errprint(f"Department fetch result: {parents[0].parent}")
#     # fetch department of the
#     assignee = get_auto_assign_employee(
#         department=parents[0].parent,
#         target_doctype=doctype,
#         owner_field="assign_to"
#     )
#     service_doc = None
#     if doctype == "Other Services":
#         service_doc = frappe.get_doc({
#             "doctype": "Other Services",
#             "customer": customer,
#             "department": department,
#             "service": service,
#             "assign_to": assignee,
#             "status": "Pending",
#             "forwarded_on": now_datetime(),
#             })
#     elif doctype == "Marketing Other Services":
#         service_doc = frappe.get_doc({
#             "doctype": "Marketing Other Services",
#             "customer": customer,
#             "service": service,
#             "assign_to": assignee,
#             "status": "Pending",
#             })
#     elif doctype == "Technical Other Services":
#         frappe.errprint(f"service:{service}, customer: {customer}, assignee: {assignee}")
#         service_doc = frappe.get_doc({
#             "doctype": "Technical Other Services",
#             "customer": customer,
#             "service": service,
#             "assign_to": assignee,
#             "status": "Pending",
#             })
#     else:
#         service_doc = frappe.get_doc({
#             "doctype": doctype,
#             "customer": customer,
#             "assign_to": assignee,
#             "status": "Pending",
#         })
#     service_doc.insert(ignore_permissions=True)
    
    
#     # ---- update stage ----
#     stage[service_key] = {
#         "department": department,
#         "timestamp": str(now_datetime()),
#         "count" : count
#     }

#     doc.stage = json.dumps(stage)
#     doc.save(ignore_permissions=True)

#     # ---- notify all assignees ----
#     notify_assignees(service_doc, service, doc.name)

#     return service_doc

# def notify_assignees(doc, service, customer):
#     assignees = set()

#     emp_user = frappe.db.get_value("Employee", doc.assign_to, "user")
#     if emp_user:
#             assignees.add(emp_user)

#     for user in assignees:
#         send_notification(
#             recipients=[user],
#             subject=f"New Candidate Assigned for ({service})",
#             message=(
#                 f"You have been assigned a new candidate.\n\n"
#                 f"Customer: {customer}\n"
#                 f"Service: {service}"
#             ),
#             send_email=1,
#             send_system=1,
#         )

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
            "name": ["in", frappe.get_all(
                "Has Role",
                filters={"role": role},
                pluck="parent"
            )]
        },
        pluck="name"
    )

    if not users:
        return []

    employees = frappe.get_all(
        "Employee",
        filters={"user": ["in", users]},
        pluck="name"
    )

    if not department:
        return employees

    return frappe.get_all(
        "Employee Assignment Detail",
        filters={
            "parent": ["in", employees],
            "department": department
        },
        pluck="parent",
        distinct=True
    )


SERVICE_DOCTYPE_MAP = {
    "ruc": "RUC",
    "resume": "Resume",
    "jdc": "JDC",
    "training": "Training",
    "cover letter": "Cover Letter",
    "marketing": "Marketing",
}


@frappe.whitelist()
def forward_candidate(customer, service):

    customer_doc = frappe.get_doc("Customer", customer)
    service_key = service.strip().lower()

    try:
        stage = json.loads(customer_doc.stage) if customer_doc.stage else {}
    except Exception:
        stage = {}

    if service_key in stage:

            doctype = SERVICE_DOCTYPE_MAP.get(service_key, "Other Services")
            department = stage[service_key][0].get("department")

            if doctype == "Other Services":
                if department == "Technical":
                    doctype = "Technical Other Services"
                elif department == "Marketing":
                    doctype = "Marketing Other Services"

            docs = frappe.get_all(
                doctype,
                filters={"customer": customer},
                fields=["name", "assign_to"]
            )

            if not docs:
                return None
            
            if department == "Marketing" :
                for d in docs:
                    if d.assign_to:
                        fake_doc = frappe._dict({"assign_to": d.assign_to})
                        # notify_assignees(fake_doc, service, customer)
                        frappe.enqueue(
                            "verp_staffing.crm.api.auto_assign.notify_assignees",
                            queue="short",
                            doc=fake_doc,
                            service=service,
                            customer=customer
                        )
                        
                    stage[service_key].append({
                        "department": department,
                        "timestamp": str(now_datetime())
                    })

                    frappe.db.set_value(
                        "Customer",
                        customer,
                        "stage",
                        json.dumps(stage)
                    )

                    frappe.msgprint(
                        f"Candidate is reforwarded for {service}. "
                    )
                return {
                    "reforward": True,
                    "doctype": doctype,
                    "name": docs[0].name
                    }
                

            for d in docs:
                frappe.db.set_value(
                    doctype,
                    d.name,
                    "status",
                    "Request for Update"
                )

                if d.assign_to:
                    fake_doc = frappe._dict({"assign_to": d.assign_to})
                    frappe.enqueue(
                        "verp_staffing.crm.api.auto_assign.notify_assignees",
                        queue="short",
                        doc=fake_doc,
                        service=service,
                        customer=customer
                    )

            stage[service_key].append({
                "department": department,
                "timestamp": str(now_datetime())
            })

            frappe.db.set_value(
                "Customer",
                customer,
                "stage",
                json.dumps(stage)
            )

            frappe.msgprint(
                f"Candidate is reforwarded for {service}. "
                f"Status updated to 'Request for Update'."
            )
            return {
                "reforward": True,
                "doctype": doctype,
                "name": docs[0].name
            }

    parents = frappe.db.sql(
            """
            SELECT parent FROM `tabDepartment Service`
            WHERE service_name = %s
            """,
            (service,),
            as_dict=True
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
            else:
                doctype = "Other Services"

    assignee = get_auto_assign_employee(
            department=department,
            target_doctype=doctype,
            owner_field="assign_to"
        )
    service_doc = frappe.get_doc({
            "doctype": doctype,
            "customer": customer,
            "service": service if "Other Services" in doctype else None,
            "department": department if doctype == "Other Services" else None,
            "assign_to": assignee,
            "status": "Pending",
            "forwarded_on": now_datetime() if "Other Services" in doctype else None,
        })

    service_doc.insert(ignore_permissions=True)

    stage[service_key] = [{
        "department": department,
        "timestamp": str(now_datetime())
    }]
    frappe.db.set_value(
            "Customer",
            customer,
            "stage",
            json.dumps(stage)
        )

    # notify_assignees(service_doc, service, customer)
    frappe.enqueue(
        "verp_staffing.crm.api.auto_assign.notify_assignees",
        queue="short",
        doc=service_doc,
        service=service,
        customer=customer
    )

    return {
        "reforward": False,
        "doctype": doctype,
        "name": service_doc.name
    }


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
