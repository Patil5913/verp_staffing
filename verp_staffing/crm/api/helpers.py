import frappe
from frappe.query_builder import DocType

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


def get_visible_employee_names_cached(department=None):
    cache = frappe.cache()
    cache_key = f"Visible_Employee_Names:{frappe.session.user}:{department or 'all'}"

    cached = cache.get_value(cache_key)
    if cached:
        return set(cached)

    employees = get_visible_employee_names(
        user=frappe.session.user,
        department=department,
    )

    cache.set_value(cache_key, employees, expires_in_sec=600)
    return employees


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
def generic_assign_query(user):

    doctype = frappe.local.form_dict.get("doctype")

    if user == "Administrator":
        return ""

    employee = frappe.db.get_value("Employee", {"user": user}, "name")
    if not employee:
        return "1=0"

    team = get_visible_employee_names_cached()

    if not team:
        return "1=0"

    team_sql = ",".join([frappe.db.escape(x) for x in team])

    return f"`tab{doctype}`.assign_to IN ({team_sql})"


from verp_staffing.employee.doctype.employee.employee import get_user_departments


def lead_query(user):
    if user == "Administrator":
        return ""

    team = get_visible_employee_names_cached()

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

    team = get_visible_employee_names_cached()

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
    team = get_visible_employee_names_cached()

    if not team:
        return "1=0"

    team_sql = ",".join([frappe.db.escape(x) for x in team])

    conditions = []

    conditions.append(
            f"""
            `tabCustomer`.customer_owner IN ({team_sql})
        """
    )

    # -------------------------
    # FINAL CONDITION
    # -------------------------
    if not conditions:
        return "1=0"

    return "(" + " OR ".join(conditions) + ")"

def sales_order_query(user):
    if user == "Administrator":
        return ""

    departments = get_user_departments(user)

    # Accounting sees everything
    if "Accounting" in departments:
        return ""

    team = get_visible_employee_names_cached()

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
