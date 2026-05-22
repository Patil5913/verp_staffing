import frappe
from frappe.desk.reportview import get as original_get


# get employee name from user
def get_employee_name(user):
    try:
        return frappe.db.get_value("Employee", {"user": user}, "name")
    except Exception:
        return None


# get user from employee
def get_user(employee_name):
    if not employee_name:
        return None

    try:
        user = frappe.db.get_value("Employee", employee_name, "user")
        if user:
            if frappe.db.exists("User", user):
                return user
    except Exception:
        return None

    return None


# function to get all subordinate Employee names under root_employee
def get_all_subordinates(root_employee: str, department: str | None = None) -> set[str]:

    collected = set()
    stack = [root_employee]

    while stack:
        current = stack.pop()

        filters = {"assigned_to": current}
        if department:
            filters["department"] = department

        children = frappe.db.get_all(
            "Employee Assignment Detail",
            filters=filters,
            pluck="parent",
        )

        for emp in children:
            if emp and emp not in collected:
                collected.add(emp)
                stack.append(emp)

    return collected


# function to filter out only subordinate employees
@frappe.whitelist()
def get_subordinate_employees(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user

    department = filters.get("department") if filters else None

    if user == "Administrator":
        if department:
            return frappe.db.sql(
                """
                SELECT DISTINCT e.name
                FROM `tabEmployee` e
                INNER JOIN `tabEmployee Assignment Detail` d
                    ON d.parent = e.name
                WHERE d.department = %s
                AND e.name LIKE %s
                ORDER BY e.name
                LIMIT %s OFFSET %s
                """,
                (department, f"%{txt}%", page_len, start),
            )

        return frappe.db.sql(
            """
            SELECT name
            FROM `tabEmployee`
            WHERE name LIKE %s
            ORDER BY name
            LIMIT %s OFFSET %s
            """,
            (f"%{txt}%", page_len, start),
        )

    employee = get_employee_name(user)
    if not employee:
        return []

    allowed_set = get_all_subordinates(employee, department)

    if not allowed_set:
        return []

    allowed = list(allowed_set)  # THIS is the missing piece

    placeholders = ", ".join(["%s"] * len(allowed))

    return frappe.db.sql(
        f"""
        SELECT name
        FROM `tabEmployee`
        WHERE name IN ({placeholders})
          AND name LIKE %s
        ORDER BY name
        LIMIT %s OFFSET %s
        """,
        allowed + [f"%{txt}%", page_len, start],
    )


@frappe.whitelist()
def get_all_superiors_with_roles(employee: str, department: str | None = None):
    result = []
    visited = set()
    current = employee

    while current:
        filters = {"parent": current}
        if department:
            filters["department"] = department

        # Get manager (assigned_to)
        manager = frappe.db.get_value(
            "Employee Assignment Detail", filters, "assigned_to"
        )

        if not manager or manager in visited:
            break

        visited.add(manager)

        # Get linked User for this manager Employee
        manager_user = frappe.db.get_value("Employee", manager, "user")

        # Get all Frappe roles assigned to that user
        roles = []
        if manager_user:
            roles = frappe.db.get_all(
                "Has Role",
                filters={"parent": manager_user, "parenttype": "User"},
                pluck="role",
            )

        result.append({"employee": manager, "roles": roles})

        current = manager  # move upward

    return result


SERVICE_DEPARTMENT_MAP = {
    "resume": "Technical",
    "jdc": "Technical",
    "ruc": "Technical",
    "cover letter": "Technical",
    "training": "Technical",
    "technical other services": "Technical",
    "marketing": "Marketing",
    "marketing other services": "Marketing",
}


def _resolve_department_from_service(extra_info):
    if not extra_info:
        return None

    mapped = SERVICE_DEPARTMENT_MAP.get(extra_info.strip().lower())
    if mapped:
        return mapped

    dept = frappe.db.get_value("Other Services", {"service": extra_info}, "department")
    return dept


def _get_employee_roles(employee_name):
    """Get Frappe system roles for an employee via their linked User."""
    user = frappe.db.get_value("Employee", employee_name, "user")
    if not user:
        return []
    roles = frappe.db.get_all(
        "Has Role",
        filters={"parent": user, "parenttype": "User"},
        pluck="role",
    )
    return roles or []


def _find_employee_with_role_in_dept(required_role, target_dept):
    """
    Find ALL employees who:
    1. Have an assignment row with target_dept
    2. Have the required_role in their Frappe user roles

    Returns the first match found.
    """
    # Get all employees who have an assignment in target_dept
    dept_employees = frappe.db.get_all(
        "Employee Assignment Detail",
        filters={"department": target_dept},
        fields=["parent", "assigned_to"],
        order_by="idx asc",
    )

    for row in dept_employees:
        emp = row.get("parent")
        if not emp:
            continue
        emp_roles = _get_employee_roles(emp)
        if required_role in emp_roles:

            return emp

    return None


def get_approver_by_department(employee_name, service_doctype=None, extra_info=None):
    """
    Finds the correct approver based on the required role for a department.
    """
    try:
        erp_config = frappe.get_single("ERP Configuration")
    except Exception:
        frappe.throw("ERP Configuration not found.")

    # Build dept → role map from ERP Configuration child table
    dept_role_map = {}
    for row in erp_config.get("table_tpxt") or []:
        if row.department and row.role:
            dept_role_map[row.department] = row.role

    # Get ALL assignment rows for this employee
    assignment_rows = frappe.db.get_all(
        "Employee Assignment Detail",
        filters={"parent": employee_name},
        fields=["department", "designation", "assigned_to"],
        order_by="idx asc",
    )

    if not assignment_rows:
        return None

    direct_manager = next(
        (r.get("assigned_to") for r in assignment_rows if r.get("assigned_to")),
        None,
    )

    # ── CASE 1: Request from Other Services ───────────────────────────────
    if service_doctype == "Other Services" and extra_info:
        target_dept = _resolve_department_from_service(extra_info)

        if not target_dept:
            return direct_manager

        # Get required role for this department from ERP Config
        dept_key = next(
            (
                k
                for k in dept_role_map
                if k.strip().lower() == target_dept.strip().lower()
            ),
            None,
        )
        required_role = dept_role_map.get(dept_key) if dept_key else None

        if not required_role:
            return direct_manager

        # Override direct_manager from matching dept row
        matching_row = next(
            (
                r
                for r in assignment_rows
                if (r.get("department") or "").strip().lower()
                == target_dept.strip().lower()
            ),
            None,
        )
        if matching_row and matching_row.get("assigned_to"):
            direct_manager = matching_row.get("assigned_to")

        approver = _find_employee_with_role_in_dept(
            required_role, dept_key or target_dept
        )
        if approver and approver != employee_name:
            return approver

        if direct_manager:
            starting_roles = _get_employee_roles(direct_manager)
            if required_role in starting_roles:
                return direct_manager

            superiors = get_all_superiors_with_roles(direct_manager)
            for superior in superiors:
                if required_role in superior.get("roles", []):
                    return superior.get("employee")

        return direct_manager

    else:
        required_roles = []
        dept_keys = []
        for row in assignment_rows:
            dept = row.get("department")
            if not dept:
                continue
            dept_key = next(
                (k for k in dept_role_map if k.strip().lower() == dept.strip().lower()),
                None,
            )
            if dept_key and dept_role_map[dept_key]:
                role = dept_role_map[dept_key]
                if role not in required_roles:
                    required_roles.append(role)
                    dept_keys.append(dept_key)

        if not required_roles:
            return direct_manager

        for i, role in enumerate(required_roles):
            dept_key = dept_keys[i] if i < len(dept_keys) else None
            if dept_key:
                approver = _find_employee_with_role_in_dept(role, dept_key)
                if approver and approver != employee_name:
                    return approver

        superiors = get_all_superiors_with_roles(employee_name)
        for superior in superiors:
            sup_roles = superior.get("roles", [])
            matched = next((r for r in required_roles if r in sup_roles), None)
            if matched:
                return superior.get("employee")

        return direct_manager


# to get visible employee names for a user
def get_visible_employee_names(user, department=None):
    root_employee = get_employee_name(user)
    if not root_employee:
        return []

    users = get_all_subordinates(
        root_employee=root_employee,
        department=department,
    )

    users.add(root_employee)
    return list(users)


# get allowed leads for sales person
def get_allowed_leads(user):
    root_employee = get_employee_name(user)
    if not root_employee:
        return []

    users = get_visible_employee_names(user)

    own_leads = frappe.db.get_all(
        "Lead",
        filters={"lead_owner": ["in", users]},
        pluck="name",
    )

    opp_leads = frappe.db.get_all(
        "Opportunity",
        filters={"opportunity_owner": ["in", users]},
        pluck="opportunity_from_lead",
    )

    return list(set(own_leads + opp_leads))


# to add list view restriction based on employee hierarchy
# @frappe.whitelist()
# def secure_get(**kwargs):
#     user = frappe.session.user
#     doctype = frappe.local.form_dict.get("doctype")

#     if user == "Administrator":
#         return original_get(**frappe.local.form_dict)

#     if doctype == "Lead":
#         allowed_leads = get_allowed_leads(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Lead", "name", "in", allowed_leads]]
#         )
#         return original_get(**frappe.local.form_dict)

#     if doctype == "Opportunity":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Opportunity", "opportunity_owner", "in", owners]]
#         )
#         return original_get(**frappe.local.form_dict)

#     if doctype == "Resume" or doctype == "RUC":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Resume","assign_to","in",owners]]
#         )

#     if doctype == "Marketing":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Marketing","assign_to","in",owners]]
#         )

#     if doctype == "Training":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Training","assign_to","in",owners]]
#         )

#     if doctype == "RUC":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["RUC","assign_to","in",owners]]
#         )

#     if doctype == "JDC":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["JDC","assign_to","in",owners]]
#         )

#     if doctype == "Cover Letter":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Cover Letter","assign_to","in",owners]]
#         )

#     if doctype == "Technical Other Services":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Technical Other Services","assign_to","in",owners]]
#         )

#     if doctype == "Marketing Other Services":
#         owners = get_visible_employee_names(user)
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Marketing Other Services","assign_to","in",owners]]
#         )

# return original_get(**frappe.local.form_dict)

import json


# def send_system_notification(
#     *,
#     user,
#     subject,
#     message,
#     reference_doctype=None,
#     reference_name=None,
# ):
#     frappe.get_doc(
#         {
#             "doctype": "Notification Log",
#             "subject": subject,
#             "email_content": message,
#             "for_user": user,
#             "document_type": reference_doctype,
#             "document_name": reference_name,
#             "type": "Alert",
#         }
#     ).insert(ignore_permissions=True)


def send_system_notification(
    user, subject, message, reference_doctype=None, reference_name=None
):
    # user here must be the User 'name' field (login id), not email
    # Verify the user actually exists before inserting
    if not frappe.db.exists("User", user):
        frappe.log_error(
            f"send_system_notification: User '{user}' not found, skipping notification.",
            "Notification Error",
        )
        return

    doc = frappe.get_doc(
        {
            "doctype": "Notification Log",
            "for_user": user,
            "from_user": frappe.session.user,
            "subject": subject,
            "email_content": message,
            "type": "Alert",
            "document_type": reference_doctype,
            "document_name": reference_name,
        }
    )
    doc.insert(ignore_permissions=True)


def send_email(recipients, subject, message, attachments=None, now=None):
    sender = None

    # Check if the logged-in user has a sendable email account
    logged_in_user = frappe.session.user
    if logged_in_user and logged_in_user != "Guest":
        user_email_accounts = frappe.get_all(
            "Email Account",
            filters={
                "email_id": logged_in_user,
                "enable_outgoing": 1,
            },
            fields=["email_id"],
            limit=1,
        )
        if user_email_accounts:
            sender = user_email_accounts[0].email_id

    # sender=None will fall back to Frappe's default outgoing email account
    frappe.sendmail(
        sender=sender,
        recipients=recipients,
        subject=subject,
        message=message,
        attachments=attachments,
        delayed=(not now) if now is not None else True,
        retry=3,
    )


def notify(
    *,
    recipients,
    subject,
    message,
    reference_doctype=None,
    reference_name=None,
    send_email_flag=True,
    send_system_flag=True,
    attachments=None,
    now=False,
):
    """
    Internal dispatcher
    """

    if not recipients:
        return

    if send_system_flag:
        for user in recipients:
            send_system_notification(
                user=user,
                subject=subject,
                message=message,
                reference_doctype=reference_doctype,
                reference_name=reference_name,
            )

    if send_email_flag:
        send_email(
            recipients=recipients,
            subject=subject,
            message=message,
            attachments=attachments,
            now=now,
        )


@frappe.whitelist()
def send_notification(**kwargs):

    # if frappe.session.user == "Guest":
    #     frappe.throw("Authentication required")

    recipients = kwargs.get("recipients")
    subject = kwargs.get("subject")
    message = kwargs.get("message")

    reference_doctype = kwargs.get("reference_doctype")
    reference_name = kwargs.get("reference_name")
    attachments = kwargs.get("attachments")  # FIXED
    send_email_flag = int(kwargs.get("send_email", 1))
    send_system_flag = int(kwargs.get("send_system", 1))
    now = kwargs.get("now", False)
    # ---- Validation ----
    if not recipients:
        frappe.throw("recipients is required")

    if not subject:
        frappe.throw("subject is required")

    if not message:
        frappe.throw("message is required")

    if isinstance(recipients, str):
        recipients = json.loads(recipients)

    if not isinstance(recipients, list):
        frappe.throw("recipients must be a list")

    # ---- Dispatch ----
    notify(
        recipients=recipients,
        subject=subject,
        message=message,
        attachments=attachments,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        send_email_flag=bool(send_email_flag),
        send_system_flag=bool(send_system_flag),
        now=now,
    )

    return {
        "status": "success",
        "recipients": recipients,
    }


# permission query
def generic_assign_query(user):

    doctype = frappe.local.form_dict.get("doctype")

    if user == "Administrator":
        return ""

    employee = frappe.db.get_value("Employee", {"user": user}, "name")
    if not employee:
        return "1=0"

    team = get_visible_employee_names(user)

    if not team:
        return "1=0"

    team_sql = ",".join([frappe.db.escape(x) for x in team])

    return f"`tab{doctype}`.assign_to IN ({team_sql})"


def opportunity_query(user):

    if user == "Administrator":
        return ""

    team = get_visible_employee_names(user)

    if not team:
        return "1=0"

    team_sql = ",".join([frappe.db.escape(x) for x in team])

    return f"`tabOpportunity`.opportunity_owner IN ({team_sql})"


from verp_staffing.employee.doctype.employee.employee import get_user_departments


def lead_query(user):

    if user == "Administrator":
        return ""

    team = get_visible_employee_names(user)

    if not team:
        return "1=0"

    departments = get_user_departments(user)

    team_sql = ",".join([frappe.db.escape(x) for x in team])
    conditions = []

    # -------------------------
    # SALES LOGIC
    # -------------------------
    if "Sales" in departments:

        conditions.append(
            f"""
            `tabLead`.lead_owner IN ({team_sql})
        """
        )

        conditions.append(
            f"""
            `tabLead`.name IN (
                SELECT `tabOpportunity`.party_name
                FROM `tabOpportunity`
                WHERE `tabOpportunity`.opportunity_owner IN ({team_sql})
            )
        """
        )

    # -------------------------
    # NON-SALES LOGIC (fallback)
    # -------------------------
    else:
        # optional: restrict completely OR allow hierarchy
        conditions.append(
            f"""
            `tabLead`.lead_owner IN ({team_sql})
        """
        )

    return "(" + " OR ".join(conditions) + ")"


def customer_query(user):

    if user == "Administrator":
        return ""

    # 1. get employee
    employee = frappe.db.get_value("Employee", {"user": user}, "name")

    if not employee:
        return "1=0"

    # 2. get departments
    departments = frappe.get_all(
        "Employee Assignment Detail", filters={"parent": employee}, pluck="department"
    )

    # 3. get team
    team = get_visible_employee_names(user)

    if not team:
        return "1=0"

    team_sql = ",".join([frappe.db.escape(x) for x in team])

    conditions = []

    # -------------------------
    # SALES LOGIC
    # -------------------------
    if "Sales" in departments:
        conditions.append(
            f"""
            `tabCustomer`.customer_owner IN ({team_sql})
        """
        )

    # -------------------------
    # CR / ONBOARDING LOGIC
    # -------------------------
    routing_departments = []

    if "CR" in departments:
        routing_departments.append("CR")

    if "Onboarding" in departments:
        routing_departments.append("Onboarding")

    if routing_departments:

        dept_sql = ",".join([frappe.db.escape(d) for d in routing_departments])

        conditions.append(
            f"""
            EXISTS (
                SELECT 1
                FROM `tabCustomer Department Route`
                WHERE
                    `tabCustomer Department Route`.customer = `tabCustomer`.name
                    AND `tabCustomer Department Route`.department IN ({dept_sql})
                    AND `tabCustomer Department Route`.assigned_to IN ({team_sql})
            )
        """
        )

    # -------------------------
    # FINAL CONDITION
    # -------------------------
    if not conditions:
        return "1=0"

    return "(" + " OR ".join(conditions) + ")"
