import json
import frappe
from frappe.utils import now_datetime
from verp_staffing.crm.api.helpers import send_notification
from verp_staffing.accounts.utils.sales_order_status import _get_department_map
from frappe import _


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
        is_admin = frappe.session.user == "Administrator"

        admin_msg = f"""
            <b>No employees available for auto assignment.</b><br><br>

            The <b>{department}</b> department is not assigned to any employee.<br><br>

            Please do one of the following:<br>

            1. Update Employee Assignment Details.<br>
            2. Assign the department to an employee.<br>
            3. Create a new employee and configure the assignment.<br><br>

            <a href="/app/employee"
            class="btn btn-primary btn-sm">
            Open Employee List
            </a>
        """

        user_msg = """
            Unable to process the request because no employee is currently available
            for assignment.

            Please contact your system administrator or reporting manager
            to complete the required configuration.
        """

        frappe.throw(
            msg=admin_msg if is_admin else user_msg,
            title="Employee Assignment Required",
        )

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
def forward_candidate(customer, service, interview_round=None):

    customer_doc = frappe.get_doc("Customer", customer)
    service_key = service.strip().lower()

    try:
        stage = json.loads(customer_doc.stage) if customer_doc.stage else {}
    except Exception:
        stage = {}

    if service_key == "cr":
        return handle_cr_forward(
            customer=customer,
            from_service_name=frappe.form_dict.get("from_service_name"),
            reason_for_forwarding=frappe.form_dict.get("reason_for_forwarding"),
            assign_employee=frappe.form_dict.get("assign_employee"),
        )

    if service_key == "onboarding":
        return handle_onboarding_forward(
            customer=customer,
            from_service_name=frappe.form_dict.get("from_service_name"),
            interview=frappe.form_dict.get("interview"),
            email=frappe.form_dict.get("email"),
            password=frappe.form_dict.get("password"),
            assign_employee=frappe.form_dict.get("assign_employee"),
        )

    if service_key in stage:
        doctype = SERVICE_DOCTYPE_MAP.get(service_key, "Other Services")
        department = stage[service_key][0].get("department")
        if doctype == "Other Services":
            if department == "Technical":
                doctype = "Technical Other Services"
            elif department == "Marketing":
                doctype = "Marketing Other Services"
        filters = {"customer": customer}
        if service_key == "jdc" or service_key == "interview support":
            filters["interview_round"] = interview_round

        docs = frappe.get_all(doctype, filters=filters, fields=["name", "assign_to"])

        if not docs and (service_key == "jdc" or service_key == "interview support"):
            assignee = get_auto_assign_employee(
                department=department, target_doctype=doctype, owner_field="assign_to"
            )
            service_doc = frappe.get_doc(
                {
                    "doctype": doctype,
                    "customer": customer,
                    "assign_to": assignee,
                    "status": "Pending",
                    "interview_round": interview_round,
                }
            )
            service_doc.insert(ignore_permissions=True)
            stage[service_key].append(
                {
                    "department": department,
                    "timestamp": str(now_datetime()),
                    "interview_round": interview_round,
                }
            )
            frappe.db.set_value("Customer", customer, "stage", json.dumps(stage))

            return {"reforward": False, "doctype": doctype, "name": service_doc.name}

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
                        frappe.db.set_value(
                            doctype, d.name, "status", "Request for Update"
                        )
                frappe.msgprint(f"reforward doctype: {doctype}, name:{docs[0].name}")
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

        stage_entry = {
            "department": department,
            "timestamp": str(now_datetime()),
        }

        if interview_round:
            stage_entry["interview_round"] = interview_round

        stage[service_key].append(stage_entry)

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

    if (service_key == "jdc" or service_key == "interview support") and interview_round:
        service_doc.interview_round = interview_round

    service_doc.insert(ignore_permissions=True)

    stage_entry = {
        "department": department,
        "timestamp": str(now_datetime()),
    }

    if interview_round:
        stage_entry["interview_round"] = interview_round

    stage[service_key] = [stage_entry]

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

    subject = f"New Candidate Assigned ({service})"
    message = (
        "You have been assigned a new candidate.<br><br>"
        f"<strong>Customer:</strong> {customer}<br>"
        f"<strong>Service:</strong> {service}"
    )

    template = frappe.db.get_value(
        "Email Template",
        "New Candidate Assigned",
        ["subject", "response_html", "response"],
        as_dict=True,
    )
    if template:
        context = {
            "service": service,
            "customer": customer,
        }

        subject = frappe.render_template(template.subject, context)
        message = frappe.render_template(
            template.response_html or template.response,
            context,
        )

    send_notification(
        recipients=[emp_user],
        subject=subject,
        message=message,
        send_email=1,
        send_system=1,
    )


@frappe.whitelist()
def get_customer_interviews(customer, service=None):
    if not customer:
        return []

    marketing = frappe.get_cached_value("Marketing", {"customer": customer}, "name")
    if not marketing:
        return []

    base_select = """
		SELECT
			ir.name AS value,
			CONCAT(ir.round, ' (', i.company, ')') AS label
		FROM `tabInterview` i
		INNER JOIN `tabInterview Round` ir ON ir.parent = i.name
	"""

    if service == "jdc":
        query = (
            base_select
            + """
			LEFT JOIN `tabJDC` jdc ON jdc.interview_round = ir.name
			WHERE i.marketing_link = %(marketing)s
			AND jdc.name IS NULL
		"""
        )
    elif service == "interview support":
        query = (
            base_select
            + """
			WHERE i.marketing_link = %(marketing)s
			AND ir.support = 0
		"""
        )
    elif service == "onboarding":
        query = """
            SELECT  
                CONCAT(i.company, ' (', i.role, ')') AS label,
                i.name AS value
            FROM `tabInterview` i
                WHERE i.marketing_link = %(marketing)s
            """

    else:
        query = (
            base_select
            + """
			WHERE i.marketing_link = %(marketing)s
		"""
        )

    interviews = frappe.db.sql(query, {"marketing": marketing}, as_dict=True)

    return interviews


# CR/Onboarding Load analyzer
def get_department_load_employee(department, target_doctype):
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
        count = 0
        count = frappe.db.count(
            target_doctype,
            filters={
                "assign_to": emp,
                "status": "Active",
            },
        )

        load.append({"employee": emp, "count": count})

    load.sort(key=lambda x: x["count"])

    return load[0]["employee"]

    # Map department name to its doctype


DEPARTMENT_DOCTYPE = {
    "CR": "CR",
    "Onboarding": "Onboardings",
}
CR_BLOCKING_STATUS = "Dispute Pending"


def _resolve_forwarded_from_department(from_service_name):
    if not from_service_name:
        frappe.throw("Source service is required to forward to CR")

    if from_service_name.strip().lower() == "sales":
        return "Sales"

    department = _get_department_map().get(from_service_name)
    if not department:
        frappe.throw(_(f"No department found for service {from_service_name}"))

    return department


def handle_cr_forward(
    customer, from_service_name, reason_for_forwarding, assign_employee=None
):
    if not reason_for_forwarding:
        frappe.throw(_("Reason for forwarding is required for CR"))

    forwarded_from_department = _resolve_forwarded_from_department(from_service_name)

    existing_cr_name = frappe.db.get_value("CR", {"customer": customer}, "name")

    if existing_cr_name:
        current_status = frappe.db.get_value("CR", existing_cr_name, "status")
        if current_status == CR_BLOCKING_STATUS:
            frappe.throw(
                f"Customer already has an active CR case in '{CR_BLOCKING_STATUS}' status. "
                f"It must be resolved or refunded before forwarding again."
            )

    assignee = assign_employee or get_department_load_employee("CR", "CR")

    history_row = {
        "reason_for_forwarding": reason_for_forwarding,
        "forwarded_by": frappe.session.user,
        "forwarded_from_department": forwarded_from_department,
        "status": CR_BLOCKING_STATUS,
        "forwarded_on": now_datetime(),
        "assign_to": assignee,
    }

    if existing_cr_name:
        cr_doc = frappe.get_doc("CR", existing_cr_name)
        cr_doc.append("cr_history", history_row)
        cr_doc.save(ignore_permissions=True)
    else:
        cr_doc = frappe.get_doc(
            {
                "doctype": "CR",
                "customer": customer,
                "cr_history": [history_row],
            }
        )
        cr_doc.insert(ignore_permissions=True)

    emp_user = frappe.db.get_value("Employee", assignee, "user") if assignee else None
    if emp_user:
        send_notification(
            recipients=[emp_user],
            subject="New Candidate Assigned",
            message=(
                f"You have been assigned a new CR case.\n\n"
                f"Customer: {customer}\n"
                f"Forwarded from: {forwarded_from_department}"
            ),
            send_email=0,
            send_system=1,
        )

    return {"reforward": bool(existing_cr_name), "doctype": "CR", "name": cr_doc.name}


def handle_onboarding_forward(
    customer,
    from_service_name,
    interview,
    email=None,
    password=None,
    assign_employee=None,
):
    if not interview:
        frappe.throw(_("Interview is required for Onboarding"))
    if not email or not password:
        frappe.throw(_("Candidate Email and Password are required"))

    forwarded_from_department = _resolve_forwarded_from_department(from_service_name)

    interview_doc = frappe.db.get_value(
        "Interview", interview, ["company", "role"], as_dict=True
    )
    if not interview_doc:
        frappe.throw(f"Interview {interview} not found")

    existing_name = frappe.db.get_value("Onboardings", {"customer": customer}, "name")

    if existing_name:
        current_status = frappe.db.get_value("Onboardings", existing_name, "status")
        if current_status in ["Active", "Completed"]:
            frappe.throw(
                f"Customer is forwarded for onboarding."
                f"status: {current_status}. so cannot forward further untill it is returned."
            )

    assignee = assign_employee or get_department_load_employee(
        "Onboarding", "Onboardings"
    )

    history_row = {
        "company": interview_doc.company,
        "role": interview_doc.role,
        "assign_to": assignee,
        "forwarded_by": frappe.session.user,
        "forwarded_from": forwarded_from_department,
        "forwarded_on": now_datetime(),
        "status": "Active",
    }

    frappe.flags.cr_system_action = True
    try:
        if existing_name:
            onboarding_doc = frappe.get_doc("Onboardings", existing_name)
            onboarding_doc.append("onboarding_history", history_row)
            onboarding_doc.status = "Active"
            onboarding_doc.assign_to = assignee
            onboarding_doc.save(ignore_permissions=True)
        else:
            onboarding_doc = frappe.get_doc(
                {
                    "doctype": "Onboardings",
                    "customer": customer,
                    "status": "Active",
                    "assign_to": assignee,
                    "onboarding_history": [history_row],
                }
            )
            onboarding_doc.insert(ignore_permissions=True)
    finally:
        frappe.flags.cr_system_action = False

    emp_user = frappe.db.get_value("Employee", assignee, "user") if assignee else None
    if emp_user:
        send_notification(
            recipients=[emp_user],
            subject="New Candidate Assigned",
            message=(
                f"You have been assigned a new Onboarding case.\n\n"
                f"Customer: {customer}\n"
                f"Forwarded from: {forwarded_from_department}"
            ),
            send_email=0,
            send_system=1,
        )

    return {
        "reforward": bool(existing_name),
        "doctype": "Onboardings",
        "name": onboarding_doc.name,
    }
