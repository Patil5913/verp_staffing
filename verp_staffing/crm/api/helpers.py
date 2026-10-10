import frappe
from frappe.query_builder import DocType
from verp_staffing.accounts.utils.sales_order_status import _get_department_map


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
        if user and frappe.db.exists("User", user):
            return user
    except Exception:
        return None

    return None


# function to get all subordinate Employee names under root_employee
def get_all_subordinates(root_employee: str, department: str | None = None) -> set[str]:
    query = """
        SELECT DISTINCT parent, assigned_to
        FROM `tabEmployee Assignment Detail`
        WHERE assigned_to IS NOT NULL
    """

    params = {}

    if department:
        query += " AND department = %(department)s"
        params["department"] = department

    rows = frappe.db.sql(
        query,
        params,
        as_dict=True,
    )

    # reverse map: manager → [direct subordinates]
    reverse_map: dict[str, list[str]] = {}
    for r in rows:
        reverse_map.setdefault(r.assigned_to, []).append(r.parent)

    # BFS in Python — zero DB calls
    collected: set[str] = set()
    stack = [root_employee]
    while stack:
        current = stack.pop()
        for child in reverse_map.get(current, []):
            if child not in collected:
                collected.add(child)
                stack.append(child)

    return collected


@frappe.whitelist()
def get_assign_to_by_service(doctype, txt, searchfield, start, page_len, filters):
    """get service key from stag json and get department"""
    service = filters.get("service")
    customer = filters.get("customer")
    stage = frappe.get_value("Customer", customer, "stage")
    stage = json.loads(stage) if stage else {}
    service_key = service.strip().lower()
    department = stage[service_key][0].get("department")

    return get_subordinate_employees(
        doctype, txt, searchfield, start, page_len, filters={"department": department}
    )


# function to filter out only subordinate employees
@frappe.whitelist()
def get_subordinate_employees(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user
    department = filters.get("department") if filters else None

    allowed = get_allowed_employees(user, department)

    if not allowed:
        return []

    Employee = DocType("Employee")

    return (
        frappe.qb.from_(Employee)
        .select(Employee.name)
        .where(Employee.name.isin(allowed))
        .where(Employee.name.like(f"%{txt}%"))
        .orderby(Employee.name)
        .limit(page_len)
        .offset(start)
        .run()
    )


def get_allowed_employees(user, department=None):
    """
    Returns employees user is allowed to see.
    """

    if user == "Administrator":
        # admin sees all (optionally filtered by department)
        if department:
            return set(
                frappe.get_all(
                    "Employee Assignment Detail",
                    filters={"department": department},
                    pluck="parent",
                    distinct=True,
                )
            )
        return set(frappe.get_all("Employee", pluck="name"))

    employee = get_employee_name(user)
    if not employee:
        return set()

    return get_reporting_subtree(employee, department)


def get_reporting_subtree(root_employee, department=None):
    """
    Returns root employee + all downstream employees
    using Employee Assignment Detail hierarchy.
    """
    cache = frappe.cache()
    cache_key = f"emp_tree:{root_employee}:{department or 'all'}"

    cached = cache.get_value(cache_key)
    if cached:
        return set(cached)

    assignments = frappe.get_all(
        "Employee Assignment Detail",
        filters={"department": department} if department else {},
        fields=["parent", "assigned_to"],
    )

    children_map = {}

    for row in assignments:
        children_map.setdefault(row.assigned_to, []).append(row.parent)

    visited = set()
    stack = [root_employee]

    while stack:
        emp = stack.pop()
        if emp in visited:
            continue

        visited.add(emp)
        stack.extend(children_map.get(emp, []))

    result = list(visited)

    cache.set_value(cache_key, result, expires_in_sec=600)

    return visited


@frappe.whitelist()
def get_all_superiors_with_roles_cached(employee: str, department: str | None = None):
    cache = frappe.cache()
    key = f"superiors:{employee}:{department}"

    cached = cache.get_value(key)
    if cached:
        return cached

    query = """
        SELECT
            ead.parent,
            ead.assigned_to,
            e.user
        FROM `tabEmployee Assignment Detail` ead
        LEFT JOIN `tabEmployee` e
            ON e.name = ead.assigned_to
        WHERE ead.assigned_to IS NOT NULL
    """

    params = {}

    if department:
        query += " AND ead.department = %(department)s"
        params["department"] = department

    # Query 1: Fetch assignment hierarchy and linked users
    rows = frappe.db.sql(
        query,
        params,
        as_dict=True,
    )

    # employee -> (manager_employee, manager_user)
    chain_map = {row.parent: (row.assigned_to, row.user) for row in rows}

    # Walk up the hierarchy in memory
    visited = set()
    managers = []
    current = employee
    while current and current not in visited:
        visited.add(current)
        entry = chain_map.get(current)
        if not entry:
            break
        manager_emp, manager_user = entry
        managers.append((manager_emp, manager_user))
        current = manager_emp

    if not managers:
        return []

    # Query 2: all roles for all managers in one IN query
    all_users = [u for _, u in managers if u]
    roles_map = {}
    if all_users:
        role_rows = frappe.db.sql(
            """
            SELECT parent, role FROM `tabHas Role`
            WHERE parent IN %(users)s
              AND parenttype = 'User'
            """,
            {"users": all_users},
            as_dict=True,
        )
        for r in role_rows:
            roles_map.setdefault(r.parent, []).append(r.role)

    superiors_with_roles = [
        {
            "employee": emp,
            "user": user,
            "roles": roles_map.get(user, []),
        }
        for emp, user in managers
    ]

    cache.set_value(key, superiors_with_roles, expires_in_sec=600)

    return superiors_with_roles


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


def get_employee_roles_cached(employee_name):
    """Get Frappe system roles for an employee via their linked User."""
    cache = frappe.cache()
    key = f"roles:{employee_name}"

    cached = cache.get_value(key)
    if cached:
        return cached

    user = frappe.db.get_value("Employee", employee_name, "user")
    if not user:
        return []
    roles = frappe.db.get_all(
        "Has Role",
        filters={"parent": user, "parenttype": "User"},
        pluck="role",
    )

    employee_roles = roles or []

    cache.set_value(key, employee_roles, expires_in_sec=3600)

    return employee_roles


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
        emp_roles = get_employee_roles_cached(emp)
        if required_role in emp_roles:
            return emp

    return None


def get_dept_role_map_cached():
    cache = frappe.cache()
    key = "dept_role_map"

    cached = cache.get_value(key)
    if cached:
        return cached

    erp_config = frappe.get_single("ERP Configuration")

    dept_role_map = {}
    for row in erp_config.get("table_tpxt") or []:
        if row.department and row.role:
            dept_role_map[row.department.strip().lower()] = row.role

    cache.set_value(key, dept_role_map, expires_in_sec=3600)

    return dept_role_map


def get_approver_by_department(employee_name, service_doctype=None, extra_info=None):
    """
    Finds the correct approver based on the required role for a department.
    """

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

    # Build dept → role map from ERP Configuration child table
    dept_role_map = get_dept_role_map_cached()

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
            starting_roles = get_employee_roles_cached(direct_manager)
            if required_role in starting_roles:
                return direct_manager

            superiors = get_all_superiors_with_roles_cached(direct_manager)
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

        superiors = get_all_superiors_with_roles_cached(employee_name)
        for superior in superiors:
            sup_roles = superior.get("roles", [])
            matched = next((r for r in required_roles if r in sup_roles), None)
            if matched:
                return superior.get("employee")

        return direct_manager


def resolve_field_update_routing(employee_name, department):
    """
    Determines how a field-update request should route for this department,
    reusing the existing assign_to-chain infrastructure:
      - get_all_superiors_with_roles_cached: walks UP the chain for `department`
      - get_dept_role_map_cached / get_employee_roles_cached: same role lookups
        already used by get_approver_by_department

    No separate Hierarchy-doc parsing is needed — employee.js already
    enforces that an employee's `assigned_to` can only be the employee
    holding the exact parent role above them in that department's
    Hierarchy, so superiors[0] IS "one level up" by construction.

    Returns:
        {"mode": "direct"}                          — no superior recorded → save immediately
        {"mode": "escalate", "manager_employee": X}  — requester holds the configured role →
                                                        route to their direct superior
        {"mode": "normal"}                           — below the configured role →
                                                        caller should use get_approver_by_department as before
        {"mode": "unresolved"}                       — no ERP Configuration role set for this department
    """
    if not employee_name or not department:
        return {"mode": "unresolved"}

    dept_role_map = get_dept_role_map_cached()
    dept_key = next(
        (k for k in dept_role_map if k.strip().lower() == department.strip().lower()),
        None,
    )
    configured_role = dept_role_map.get(dept_key) if dept_key else None
    if not configured_role:
        return {"mode": "unresolved"}

    superiors = get_all_superiors_with_roles_cached(employee_name, department)

    # No one above them in this department's assign_to chain — top of hierarchy.
    if not superiors:
        return {"mode": "direct"}

    own_roles = get_employee_roles_cached(employee_name)

    # Requester already holds the configured approver role — escalate to
    # their direct superior, which is guaranteed to hold the next role up.
    if configured_role in own_roles:
        direct_superior = superiors[0].get("employee")
        if not direct_superior:
            return {"mode": "direct"}
        return {"mode": "escalate", "manager_employee": direct_superior}

    return {"mode": "normal"}


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


def get_visible_employee_names_cached(department=None, user=None):
    # `user` matters for has_permission checks made on someone else's behalf (frappe.has_permission(
    # ..., user=x), notifications, shares); it defaults to the session user like every other caller.
    user = user or frappe.session.user
    cache = frappe.cache()
    cache_key = f"Visible_Employee_Names:{user}:{department or 'all'}"

    cached = cache.get_value(cache_key)
    if cached:
        return set(cached)

    employees = get_visible_employee_names(
        user=user,
        department=department,
    )

    cache.set_value(cache_key, employees, expires_in_sec=600)
    return employees


def get_visible_user_names_cached(department=None, user=None):
    """Same visibility rule as get_visible_employee_names_cached, but
    resolves to User login ids instead of Employee names — Interview has
    no assign_to field to compare Employee names against; it only has the
    framework `owner` field, which stores a User.
    """
    user = user or frappe.session.user
    cache = frappe.cache()
    cache_key = f"Visible_User_Names:{user}:{department or 'all'}"

    cached = cache.get_value(cache_key)
    if cached:
        return set(cached)

    employee_names = get_visible_employee_names_cached(department=department, user=user)

    users = set()
    for emp in employee_names:
        user = get_user(emp)
        if user:
            users.add(user)

    users.add(user)  # always see your own docs

    cache.set_value(cache_key, list(users), expires_in_sec=600)
    return users


# get allowed leads for sales person
def get_allowed_leads(user):
    root_employee = get_employee_name(user)
    if not root_employee:
        return []

    users = get_visible_employee_names_cached()

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


import json


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

    frappe.get_doc(
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
    ).insert(ignore_permissions=True)


def send_email(
    recipients,
    subject,
    message,
    attachments=None,
    now=None,
    reference_doctype=None,
    reference_name=None,
):
    sender = None

    # Check if the logged-in user has a sendable email account
    logged_in_user = frappe.session.user

    if logged_in_user and logged_in_user != "Guest":
        email_account = frappe.get_all(
            "User Email",
            filters={
                "parent": logged_in_user,
                "parenttype": "User",
                "enable_outgoing": 1,
            },
            fields=["email_account"],
            order_by="creation desc",
            limit=1,
        )

        if email_account:
            sender = frappe.db.get_value(
                "Email Account",
                {
                    "name": email_account[0].email_account,
                    "enable_outgoing": 1,
                },
                "email_id",
            )
    if not sender:
        has_default_outgoing = frappe.db.exists(
            "Email Account",
            {
                "default_outgoing": 1,
                "enable_outgoing": 1,
            },
        )

        if not has_default_outgoing:
            if "System Manager" in frappe.get_roles():
                frappe.throw(
                    msg=(
                        "No default outgoing email account is configured.<br><br>"
                        "Please create an <b>Email Account</b>, enable <b>Outgoing</b>, "
                        "mark it as <b>Default Outgoing</b>, and optionally link it to users "
                        "from the <b>Email Accounts</b> section."
                    ),
                    primary_action={
                        "label": "Open Email Accounts",
                        "client_action": "frappe.set_route",
                        "args": ["List", "Email Account"],
                    },
                )
            else:
                frappe.throw(
                    "Unable to send email because no outgoing email account is configured. "
                    "Please contact your System Administrator to configure a default outgoing email account."
                )

    # sender=None will fall back to Frappe's default outgoing email account
    frappe.sendmail(
        sender=sender,
        recipients=recipients,
        subject=subject,
        message=message,
        attachments=attachments,
        delayed=False,
        retry=3,
        send_priority=5,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
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
            reference_doctype=reference_doctype,
            reference_name=reference_name,
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

    try:
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
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Notification failed | recipients: {recipients} | subject: {subject}",
        )

    return {
        "status": "success",
        "recipients": recipients,
    }


# permission query
def generic_assign_query(user, doctype=None):

    # Frappe passes the doctype being queried; the request's own `doctype` parameter is only a
    # fallback (it is missing when the query runs inside another API, e.g. the dashboard, and
    # the condition then read `tabNone`.assign_to).
    doctype = doctype or frappe.local.form_dict.get("doctype")

    if user == "Administrator":
        return ""

    employee = frappe.db.get_value("Employee", {"user": user}, "name")
    if not employee:
        return "1=0"

    team = get_visible_employee_names_cached(user=user)

    if not team:
        return "1=0"

    team_sql = ",".join([frappe.db.escape(x) for x in team])

    return f"`tab{doctype}`.assign_to IN ({team_sql})"


def generic_assign_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    # Same class of bug fixed in lead_has_permission below: this hook only
    # narrows access to an *existing* record down to its assignee — a
    # brand-new, unsaved doc has no assign_to yet, so the check always fell
    # through to False and blocked "create" for every non-admin user
    # regardless of their actual role-based create permission.
    if ptype == "create":
        return True

    team = get_visible_employee_names_cached(user=user)
    if not team:
        return False

    return doc.assign_to in team


RESUME_VIEWER_DOCTYPES = (
    "Marketing",
    "Interview Support",
    "RUC",
    "Training",
    "JDC",
    "Cover Letter",
    "Technical Other Services",
    "Marketing Other Services",
)


def resume_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    if ptype == "create":
        return True

    team = get_visible_employee_names_cached(user=user)
    if not team:
        return False

    if doc.assign_to in team:
        return True

    # The Resume is auto-assigned to whoever is next in the Technical
    # department's rotation when it's created, independently of who the
    # same customer's profile is later assigned to in Marketing/Interview
    # Support/etc. Those are separate, never-synced `assign_to` fields —
    # so a Marketing-stage recruiter viewing "their" candidate's resume
    # must also be let in via the assignment on their own department's
    # record for this customer, not just via Resume.assign_to.
    if not doc.customer:
        return False

    for viewer_doctype in RESUME_VIEWER_DOCTYPES:
        if frappe.db.exists(
            viewer_doctype,
            {"customer": doc.customer, "assign_to": ["in", team]},
        ):
            return True

    return False


# Services a department holds for a candidate; whoever they are assigned to (or, for the last two,
# who forwarded them) can see that candidate's Customer record too.
CUSTOMER_SERVICE_DOCTYPES = ("Resume", "CR", "Onboardings", *(d for d in RESUME_VIEWER_DOCTYPES if d != "Interview Support"))
CUSTOMER_REQUESTER_DOCTYPES = ("Interview Support", "Other Services")


def _customer_via_service(customer, team, creators) -> bool:
    for doctype in CUSTOMER_SERVICE_DOCTYPES:
        if team and frappe.db.exists(doctype, {"customer": customer, "assign_to": ["in", list(team)]}):
            return True
    for doctype in CUSTOMER_REQUESTER_DOCTYPES:
        if team and frappe.db.exists(doctype, {"customer": customer, "assign_to": ["in", list(team)]}):
            return True
        if creators and frappe.db.exists(doctype, {"customer": customer, "owner": ["in", list(creators)]}):
            return True
    return False


def is_customer_sales_owner(customer_owner, user=None):
    """Only the customer's owner or someone above them in the Sales hierarchy may act on the
    customer (edit it, create Sales Orders, portal access). Other departments' roles that can
    merely see the customer (e.g. Marketing, via a service) get view-only."""
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    if not customer_owner:
        return False
    return customer_owner in get_visible_employee_names_cached(department="Sales", user=user)


@frappe.whitelist()
def can_act_on_customer(customer):
    return is_customer_sales_owner(frappe.db.get_value("Customer", customer, "customer_owner"))


def customer_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    # See generic_assign_has_permission — a new Customer has no
    # customer_owner yet, so this must not gate "create".
    if ptype == "create":
        return True

    team = get_visible_employee_names_cached(user=user)
    if not team:
        return False

    if is_customer_sales_owner(doc.customer_owner, user):
        return True

    # Read only: a department working on the candidate may open the record, not edit it
    if ptype in ("read", "select", "print", "email", "report", "export", "share"):
        return _customer_via_service(doc.name, team, get_visible_user_names_cached(user=user))
    return False


def opportunity_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    # See generic_assign_has_permission — a new Opportunity has no
    # opportunity_owner yet (and no name for the Customer lookup below to
    # match against), so this must not gate "create".
    if ptype == "create":
        return True

    team = get_visible_employee_names_cached(user=user)
    if not team:
        return False

    if doc.opportunity_owner in team:
        return True

    departments = get_user_departments(user)

    return bool(
        "Sales" in departments
        and frappe.db.exists(
            "Customer",
            {"party_name": doc.name, "customer_owner": ["in", team]},
        )
    )


def lead_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    # This hook only narrows access to an *existing* Lead down to its team
    # (owner, or Sales users with a linked Opportunity) — it has nothing
    # meaningful to check on a brand-new, unsaved Lead (no owner set yet, no
    # Opportunity can reference a name that doesn't exist yet), so it always
    # fell through to False and blocked every "create" check regardless of
    # the user's actual Lead create permission (role-based DocPerms already
    # gate that separately). Blocked a Sales Master Manager who otherwise had
    # permission from ever creating a Lead.
    if ptype == "create":
        return True

    team = get_visible_employee_names_cached(user=user)
    if not team:
        return False

    if doc.lead_owner in team:
        return True

    departments = get_user_departments(user)

    return bool(
        "Sales" in departments
        and frappe.db.exists(
            "Opportunity",
            {"opportunity_from_lead": doc.name, "opportunity_owner": ["in", team]},
        )
    )


def sales_order_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    # See generic_assign_has_permission — a new Sales Order has no `customer`
    # linked yet to resolve an owner/assignment through, so this must not
    # gate "create".
    if ptype == "create":
        return True

    departments = get_user_departments(user)

    # Accounting sees everything
    if "Accounting" in departments:
        return True

    team = get_visible_employee_names_cached(user=user)
    if not team:
        return False

    if "Sales" in departments:
        customer_owner = frappe.db.get_value("Customer", doc.customer, "customer_owner")
        if customer_owner in team:
            return True

    if "CR" in departments:
        return frappe.db.exists(
            "CR",
            {
                "customer": doc.customer,
                "assign_to": ["in", team],
            },
        )

    if "Onboarding" in departments:
        return frappe.db.exists(
            "Onboardings",
            {
                "customer": doc.customer,
                "assign_to": ["in", team],
            },
        )

    return False


def interview_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    # See generic_assign_has_permission — a new Interview has no owner yet
    # (`doc.owner` only gets set on insert), so this must not gate "create".
    if ptype == "create":
        return True

    visible_users = get_visible_user_names_cached(user=user)
    if doc.owner in visible_users:
        return True

    # An Interview belongs to its Marketing record: whoever that is assigned to (or their managers)
    # works it too, even when someone else - e.g. a manager - created the Interview.
    marketing = doc.get("marketing_link")
    if not marketing:
        return False
    team = get_visible_employee_names_cached(user=user)
    if not team:
        return False
    if doc.get("assign_to") in team:
        return True
    return frappe.db.get_value("Marketing", marketing, "assign_to") in team


from frappe.utils import cint


@frappe.whitelist()
def get_next_permitted(
    doctype, value, prev, filters=None, sort_order="desc", sort_field="creation"
):
    prev = cint(prev)
    if not filters:
        filters = []
    if isinstance(filters, str):
        filters = json.loads(filters)

    current_sort_value = frappe.db.get_value(doctype, value, sort_field)
    is_ascending = sort_order.lower() == "asc"

    if prev == is_ascending:
        operator, order_by = "<", f"{sort_field} desc, name desc"
    else:
        operator, order_by = ">", f"{sort_field} asc, name asc"

    query_filters = list(filters) + [
        [doctype, sort_field, operator, current_sort_value]
    ]

    result = frappe.get_list(
        doctype,
        filters=query_filters,  # permission_query_conditions is applied here automatically
        fields=["name"],
        order_by=order_by,
        limit_page_length=1,
    )

    if result:
        return result[0]["name"]

    frappe.msgprint(frappe._("No further accessible records"))
    return None


from verp_staffing.employee.doctype.employee.employee import get_user_departments


def lead_query(user):
    if user == "Administrator":
        return ""

    team = get_visible_employee_names_cached(user=user)

    if not team:
        return "1=0"

    departments = get_user_departments(user)

    team_sql = ",".join([frappe.db.escape(x) for x in team])
    conditions = []

    conditions.append(
        f"""
        `tabLead`.lead_owner IN ({team_sql})
        """
    )
    # -------------------------
    # SALES LOGIC
    # -------------------------
    if "Sales" in departments:
        conditions.append(
            f"""
            `tabLead`.name IN (
                SELECT `tabOpportunity`.opportunity_from_lead
                FROM `tabOpportunity`
                WHERE `tabOpportunity`.opportunity_owner IN ({team_sql})
            )
        """
        )

    return "(" + " OR ".join(conditions) + ")"


def opportunity_query(user):
    if user == "Administrator":
        return ""

    team = get_visible_employee_names_cached(user=user)

    if not team:
        return "1=0"

    departments = get_user_departments(user)

    team_sql = ",".join([frappe.db.escape(x) for x in team])
    conditions = []

    # -------------------------
    # SALES LOGIC
    # -------------------------
    conditions.append(
        f"""
            `tabOpportunity`.opportunity_owner IN ({team_sql})
        """
    )

    if "Sales" in departments:
        conditions.append(
            f"""
            `tabOpportunity`.name IN (
                SELECT `tabCustomer`.party_name
                FROM `tabCustomer`
                WHERE `tabCustomer`.customer_owner IN ({team_sql})
            )
        """
        )

    if not conditions:
        return "1=0"

    return "(" + " OR ".join(conditions) + ")"


def customer_query(user):
    if user == "Administrator":
        return ""

    # 1. get employee
    employee = frappe.db.get_value("Employee", {"user": user}, "name")

    if not employee:
        return "1=0"

    # 3. get team
    team = get_visible_employee_names_cached(user=user)

    if not team:
        return "1=0"

    team_sql = ",".join([frappe.db.escape(x) for x in team])

    conditions = []

    conditions.append(
        f"""
            `tabCustomer`.customer_owner IN ({team_sql})
        """
    )

    # ...and the candidates their department holds a service for
    users_sql = ",".join([frappe.db.escape(x) for x in get_visible_user_names_cached(user=user)])
    for doctype in CUSTOMER_SERVICE_DOCTYPES:
        conditions.append(f"`tabCustomer`.name IN (SELECT `tab{doctype}`.customer FROM `tab{doctype}` WHERE `tab{doctype}`.assign_to IN ({team_sql}))")
    for doctype in CUSTOMER_REQUESTER_DOCTYPES:
        conditions.append(
            f"`tabCustomer`.name IN (SELECT `tab{doctype}`.customer FROM `tab{doctype}` "
            f"WHERE `tab{doctype}`.assign_to IN ({team_sql}) OR `tab{doctype}`.owner IN ({users_sql}))"
        )

    # -------------------------
    # FINAL CONDITION
    # -------------------------
    if not conditions:
        return "1=0"

    return "(" + " OR ".join(conditions) + ")"


def interview_query(user):
    if user == "Administrator":
        return ""

    visible_users = get_visible_user_names_cached(user=user)
    if not visible_users:
        return "1=0"

    users_sql = ", ".join([frappe.db.escape(u) for u in visible_users])
    conditions = [f"`tabInterview`.owner IN ({users_sql})"]

    # ...the interviews assigned to them or their team, and those of Marketing records assigned
    # inside their team (see interview_has_permission)
    team = get_visible_employee_names_cached(user=user)
    if team:
        team_sql = ", ".join([frappe.db.escape(e) for e in team])
        conditions.append(f"`tabInterview`.assign_to IN ({team_sql})")
        conditions.append(
            f"`tabInterview`.marketing_link IN (SELECT `tabMarketing`.name FROM `tabMarketing` "
            f"WHERE `tabMarketing`.assign_to IN ({team_sql}))"
        )
    return "(" + " OR ".join(conditions) + ")"


def sales_order_query(user):
    if user == "Administrator":
        return ""

    departments = get_user_departments(user)

    # Accounting sees everything
    if "Accounting" in departments:
        return ""

    team = get_visible_employee_names_cached(user=user)

    if not team:
        return "1=0"

    team_sql = ",".join([frappe.db.escape(x) for x in team])
    conditions = []

    if "Sales" in departments:
        conditions.append(
            f"""
            `tabSales Order`.customer IN (
                SELECT `tabCustomer`.name
                FROM `tabCustomer`
                WHERE `tabCustomer`.customer_owner IN ({team_sql})
            )
        """
        )

    if "CR" in departments:
        conditions.append(
            f"""
            `tabSales Order`.customer IN (
                SELECT `tabCR`.customer
                FROM `tabCR`
                WHERE `tabCR`.assign_to IN ({team_sql})
            )
        """
        )

    if "Onboarding" in departments:
        conditions.append(
            f"""
            `tabSales Order`.customer IN (
                SELECT `tabOnboardings`.customer
                FROM `tabOnboardings`
                WHERE `tabOnboardings`.assign_to IN ({team_sql})
            )
        """
        )

    if not conditions:
        return "1=0"

    return "(" + " OR ".join(conditions) + ")"


from pathlib import Path


@frappe.whitelist(allow_guest=True)
def _validate_site_file_path(file_path: str) -> Path:
    path = Path(file_path).resolve()

    allowed_dirs = (
        Path(frappe.get_site_path("public")).resolve(),
        Path(frappe.get_site_path("private")).resolve(),
    )

    if not any(
        path == directory or directory in path.parents for directory in allowed_dirs
    ):
        frappe.throw("Invalid file path.")

    if not path.is_file():
        frappe.throw("File not found.")

    return path


@frappe.whitelist()
def _is_superior_in_department(
    assign_to: str, current_user: str, department: str
) -> dict:
    """
    Returns True if current_user is anywhere above assign_to
    in the given department's assignment hierarchy.
    """
    if current_user == "Administrator":
        return {"is_superior": True}
    if current_user == frappe.db.get_value("Employee", assign_to, "user"):
        return {"is_superior": False}

    # Single query — entire chain at once
    rows = frappe.db.sql(
        """
        SELECT ead.parent, ead.assigned_to, e.user
        FROM `tabEmployee Assignment Detail` ead
        JOIN `tabEmployee` e ON e.name = ead.assigned_to
        WHERE ead.department = %(department)s
          AND ead.assigned_to IS NOT NULL
        """,
        {"department": department},
        as_dict=True,
    )
    chain_map = {r.parent: (r.assigned_to, r.user) for r in rows}

    visited = set()
    current = assign_to
    while current and current not in visited:
        visited.add(current)
        entry = chain_map.get(current)
        if not entry:
            break
        manager_emp, manager_user = entry
        if manager_user == current_user:
            return {"is_superior": True}
        current = manager_emp

    return {"is_superior": False}


def requester_or_assignee_query(user, doctype=None):
    """Interview Support / Other Services: the assignee's team sees them, and so does the side that
    forwarded them (their creator, and that person's managers) - a recruiter keeps seeing the
    support they asked for."""
    doctype = doctype or frappe.local.form_dict.get("doctype")
    if user == "Administrator":
        return ""

    team = get_visible_employee_names_cached(user=user)
    creators = get_visible_user_names_cached(user=user)
    conditions = []
    if team:
        team_sql = ",".join(frappe.db.escape(x) for x in team)
        conditions.append(f"`tab{doctype}`.assign_to IN ({team_sql})")
    if creators:
        users_sql = ",".join(frappe.db.escape(x) for x in creators)
        conditions.append(f"`tab{doctype}`.owner IN ({users_sql})")
    return "(" + " OR ".join(conditions) + ")" if conditions else "1=0"


def requester_or_assignee_has_permission(doc, ptype="read", user=None):
    user = user or frappe.session.user
    if user == "Administrator" or ptype == "create":
        return True

    if doc.assign_to and doc.assign_to in get_visible_employee_names_cached(user=user):
        return True
    return doc.owner in get_visible_user_names_cached(user=user)


def user_can_see_customer(customer, user=None) -> bool:
    """Whether `user` may see this candidate's data: the owner side (Customer's own permission),
    accounting, or a department that holds a service record for the customer assigned inside their
    visible team - the same reach the service pages already give them. Guards the whitelisted
    endpoints that read a customer's details by name."""
    user = user or frappe.session.user
    if not customer:
        return False
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True
    if not frappe.db.exists("Customer", customer):
        return False
    if frappe.has_permission("Customer", "read", doc=customer, user=user):
        return True
    if "Accounting" in get_user_departments(user):
        return True

    team = get_visible_employee_names_cached(user=user)
    if team:
        for doctype in ("Resume", "CR", "Onboardings", *(d for d in RESUME_VIEWER_DOCTYPES if d != "Interview Support")):
            if frappe.db.exists(doctype, {"customer": customer, "assign_to": ["in", list(team)]}):
                return True

    # Interview Support / Other Services: assigned to the team, or forwarded by it
    creators = get_visible_user_names_cached(user=user)
    for doctype in ("Interview Support", "Other Services"):
        if team and frappe.db.exists(doctype, {"customer": customer, "assign_to": ["in", list(team)]}):
            return True
        if creators and frappe.db.exists(doctype, {"customer": customer, "owner": ["in", list(creators)]}):
            return True
    return False


def require_customer_access(customer, user=None):
    if not user_can_see_customer(customer, user):
        frappe.throw(frappe._("You do not have permission to view this candidate."), frappe.PermissionError)


def _reporting_chain(employee, manager_of):
    """employee followed by each superior above them (cycle-safe), assignee first."""
    chain, seen, current = [], set(), employee
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        current = manager_of.get(current)
    return chain


def _assignee_periods(doctype, name):
    """[(assignee, start, end)] oldest first, from the record's Version log of assign_to changes
    (end is None for the current holder). Records never re-assigned give a single period."""
    doc = frappe.db.get_value(doctype, name, ["assign_to", "creation"], as_dict=True)
    changes = []
    for v in frappe.get_all(
        "Version",
        filters={"ref_doctype": doctype, "docname": name},
        fields=["creation", "data"],
        order_by="creation asc",
    ):
        try:
            data = json.loads(v.data or "{}")
        except Exception:
            continue
        for field, old, new in data.get("changed") or []:
            if field == "assign_to":
                changes.append((v.creation, old, new))

    periods, start = [], doc.creation
    for ts, old, _new in changes:
        if old:
            periods.append((old, start, ts))
        start = ts
    periods.append((doc.assign_to, start, None))
    return [p for p in periods if p[0]]


@frappe.whitelist()
def get_assignment_tree(doctype, name, department):
    """
    Reporting chain of a record's assignee in `department`: the assignee and
    every superior above them (Employee Assignment Detail.assigned_to) up to
    the department's highest level. Visible to anyone who can read the record.

    Also returns `history`: every team that held the record (from its assign_to
    changes), each with its chain, the job applications logged and the
    interviews raised while it held the record.
    """
    frappe.has_permission(doctype, "read", name, throw=True)

    assign_to = frappe.db.get_value(doctype, name, "assign_to")
    if not assign_to or not department:
        return {"nodes": [], "history": [], "assign_to": assign_to}

    rows = frappe.get_all(
        "Employee Assignment Detail",
        filters={"department": department},
        fields=["parent", "assigned_to", "designation"],
    )
    manager_of = {r.parent: r.assigned_to for r in rows if r.assigned_to}
    role_of = {r.parent: r.designation for r in rows}

    periods = _assignee_periods(doctype, name)
    chains = [_reporting_chain(p[0], manager_of) for p in periods]
    everyone = {e for c in chains for e in c}
    names = {
        e.name: e.employee_name
        for e in frappe.get_all(
            "Employee", filters={"name": ["in", list(everyone)]}, fields=["name", "employee_name"]
        )
    }

    def person(emp):
        return {"employee": emp, "employee_name": names.get(emp) or emp, "role": role_of.get(emp)}

    # current team, top -> assignee
    current = _reporting_chain(assign_to, manager_of)
    nodes = [
        {**person(emp), "parent": manager_of.get(emp) if emp != current[-1] else None}
        for emp in reversed(current)
    ]

    apps = frappe.get_all(
        "Job Application Count",
        filters={"parent": name, "parenttype": doctype},
        fields=["small_application", "large_application", "total_application", "creation", "owner"],
    )
    owner_employee = {
        e.user: e.name
        for e in frappe.get_all(
            "Employee", filters={"user": ["in", list({a.owner for a in apps}) or [""]]}, fields=["user", "name"]
        )
    }
    interviews = frappe.get_all(
        "Interview",
        filters={"marketing_link": name},
        fields=["name", "company", "role", "status", "creation", "assign_to"],
        order_by="creation asc",
    )

    def within(ts, start, end):
        return ts >= start and (end is None or ts < end)

    def period_of(iv):
        """Index of the period an interview belongs to: its own assignee's period (the one it was
        created in if they held the record twice), else whichever period it was created in."""
        mine = [k for k, p in enumerate(periods) if p[0] == iv.assign_to]
        if mine:
            return next((k for k in mine if within(iv.creation, periods[k][1], periods[k][2])), mine[-1])
        return next((k for k, p in enumerate(periods) if within(iv.creation, p[1], p[2])), None)

    interview_period = {iv.name: period_of(iv) for iv in interviews}

    def app_period(a):
        """A job application count belongs to the recruiter who created the row (its owner). If they held
        the record more than once, the stint it was created in; rows by someone who never held the
        record (e.g. a manager entering them) fall back to the period they were created in."""
        mine = [k for k, p in enumerate(periods) if p[0] == owner_employee.get(a.owner)]
        if mine:
            return next((k for k in mine if within(a.creation, periods[k][1], periods[k][2])), mine[-1])
        return next((k for k, p in enumerate(periods) if within(a.creation, p[1], p[2])), None)

    app_periods = [app_period(a) for a in apps]

    history = []
    for k, ((emp, start, end), chain) in enumerate(zip(periods, chains)):
        mine = [a for a, idx in zip(apps, app_periods) if idx == k]
        history.append(
            {
                **person(emp),
                "start": start,
                "end": end,
                "is_current": end is None,
                "team": [person(e) for e in reversed(chain)],
                "applications": {
                    "small": sum(cint(a.small_application) for a in mine),
                    "large": sum(cint(a.large_application) for a in mine),
                    "total": sum(cint(a.total_application) for a in mine),
                },
                "interviews": [i for i in interviews if interview_period[i.name] == k],
            }
        )
    return {"nodes": nodes, "history": history, "assign_to": assign_to}


def _auto_assign_role(department):
    cfg = frappe.db.get_value("Hierarchy", {"department": department}, "auto_assign_config")
    try:
        return (json.loads(cfg or "{}") or {}).get("role")
    except Exception:
        return None


def can_change_assign_to(assign_to, user, department):
    """
    Who may re-assign a record currently held by `assign_to` in `department`:
    the holder of the department's auto-assignment role that the record sits
    with (the lowest such person in the assignee's reporting chain), and
    anyone above them in that chain. Administrator always may.
    """
    if user == "Administrator":
        return True
    role = _auto_assign_role(department)
    if not role or not assign_to:
        return False

    rows = frappe.get_all(
        "Employee Assignment Detail",
        filters={"department": department},
        fields=["parent", "assigned_to"],
    )
    manager_of = {r.parent: r.assigned_to for r in rows if r.assigned_to}

    chain, seen, current = [], set(), assign_to
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        current = manager_of.get(current)

    users = {
        e.name: e.user
        for e in frappe.get_all("Employee", filters={"name": ["in", chain]}, fields=["name", "user"])
    }
    role_users = set(
        frappe.get_all("Has Role", filters={"role": role, "parenttype": "User", "parent": ["in", [u for u in users.values() if u]]}, pluck="parent")
    )

    for i, emp in enumerate(chain):
        if users.get(emp) in role_users:
            return user in {users.get(e) for e in chain[i:]}
    return False


def resolve_record_department(doc_or_values, doctype, service=None):
    """Department a service record belongs to: the department stored on the customer's stage for its
    service (the same one the Assign To picker uses), else the record's own `department`, else the
    service's default department."""
    get = (lambda k: doc_or_values.get(k)) if hasattr(doc_or_values, "get") else (lambda k: None)
    service = service or get("service") or doctype
    customer = get("customer")
    if customer:
        stage = frappe.db.get_value("Customer", customer, "stage")
        try:
            rows = (json.loads(stage) if stage else {}).get(service.strip().lower()) or []
            if rows and rows[0].get("department"):
                return rows[0]["department"]
        except Exception:
            pass
    return get("department") or SERVICE_DEPARTMENT_MAP.get(service.strip().lower()) or "Technical"


@frappe.whitelist()
def can_change_assign_to_for_record(doctype, name, service=None):
    frappe.has_permission(doctype, "read", name, throw=True)
    meta = frappe.get_meta(doctype)
    fields = [f for f in ("assign_to", "customer", "department", "service") if f == "assign_to" or meta.has_field(f)]
    doc = frappe.db.get_value(doctype, name, fields, as_dict=True)
    if not doc:
        return {"allowed": False}
    department = resolve_record_department(doc, doctype, service)
    return {"allowed": bool(can_change_assign_to(doc.assign_to, frappe.session.user, department))}


def validate_assign_to_change(doc, service=None):
    """Server-side guard for an existing record's assign_to edit: the user must be allowed to
    re-assign it (see can_change_assign_to) and may only pick from their own reporting subtree."""
    before = doc.get_doc_before_save()
    if doc.is_new() or not before or before.assign_to == doc.assign_to:
        return
    user = frappe.session.user
    if user == "Administrator":
        return
    department = resolve_record_department(before, doc.doctype, service)
    if not can_change_assign_to(before.assign_to, user, department):
        frappe.throw(
            frappe._("You are not allowed to change Assigned To on this record."),
            frappe.PermissionError,
        )
    me = get_employee_name(user)
    if doc.assign_to and doc.assign_to not in get_reporting_subtree(me, department):
        frappe.throw(
            frappe._("{0} is not in your reporting line.").format(doc.assign_to),
            frappe.PermissionError,
        )


# --- Interview assignee -----------------------------------------------------------------------


def _marketing_department(marketing):
    return resolve_record_department(
        frappe.db.get_value("Marketing", marketing, ["customer"], as_dict=True) or {}, "Marketing"
    )


def _marketing_holders(marketing):
    """Every employee who has held this Marketing record (oldest first)."""
    return [p[0] for p in _assignee_periods("Marketing", marketing)]


def is_marketing_top_authority(marketing, user):
    """Administrator, or the top of the reporting chain above the Marketing record's current assignee."""
    if user == "Administrator":
        return True
    assign_to = frappe.db.get_value("Marketing", marketing, "assign_to")
    if not assign_to:
        return False
    department = _marketing_department(marketing)
    rows = frappe.get_all(
        "Employee Assignment Detail", filters={"department": department}, fields=["parent", "assigned_to"]
    )
    manager_of = {r.parent: r.assigned_to for r in rows if r.assigned_to}
    top = _reporting_chain(assign_to, manager_of)[-1]
    return frappe.db.get_value("Employee", top, "user") == user


@frappe.whitelist()
def get_interview_assignee_options(marketing):
    """Earlier holders of this Marketing record (other than the current user) whose interviews the
    current team can still add on their behalf."""
    frappe.has_permission("Marketing", "read", marketing, throw=True)
    me = get_employee_name(frappe.session.user)
    holders = [e for e in dict.fromkeys(_marketing_holders(marketing)) if e != me]
    return [
        {"employee": e.name, "employee_name": e.employee_name or e.name}
        for e in frappe.get_all("Employee", filters={"name": ["in", holders]}, fields=["name", "employee_name"])
    ]


@frappe.whitelist()
def can_reassign_interview(name):
    frappe.has_permission("Interview", "read", name, throw=True)
    marketing = frappe.db.get_value("Interview", name, "marketing_link")
    return {"allowed": bool(marketing and is_marketing_top_authority(marketing, frappe.session.user))}


def validate_interview_assignee(doc):
    """A new Interview belongs to its creator unless they add it on behalf of an earlier holder of the
    Marketing record (or someone in their own line). Afterwards only the Marketing's top authority
    can move it to another employee of the department."""
    marketing = doc.marketing_link
    if not marketing or not frappe.db.exists("Marketing", marketing):
        return
    user = frappe.session.user
    me = get_employee_name(user)
    holders = set(_marketing_holders(marketing))

    if doc.is_new():
        if not doc.assign_to:
            doc.assign_to = me or frappe.db.get_value("Marketing", marketing, "assign_to")
            return
        if user == "Administrator" or doc.assign_to == me or doc.assign_to in holders:
            return
        if me and doc.assign_to in get_reporting_subtree(me, _marketing_department(marketing)):
            return
        frappe.throw(
            frappe._("{0} is not part of this record's team, so the interview can't be added for them.").format(doc.assign_to),
            frappe.PermissionError,
        )

    before = doc.get_doc_before_save()
    if not before or before.assign_to == doc.assign_to:
        return
    if not doc.assign_to:
        frappe.throw(frappe._("Assigned To can't be cleared."), frappe.ValidationError)
    if not is_marketing_top_authority(marketing, user):
        frappe.throw(
            frappe._("Only the highest authority of Marketing can change who an interview is assigned to."),
            frappe.PermissionError,
        )
    in_department = frappe.db.exists(
        "Employee Assignment Detail", {"parent": doc.assign_to, "department": _marketing_department(marketing)}
    )
    if not in_department and doc.assign_to not in holders:
        frappe.throw(
            frappe._("{0} does not work in this department.").format(doc.assign_to), frappe.ValidationError
        )
