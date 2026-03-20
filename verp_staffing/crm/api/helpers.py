import frappe
from frappe.desk.reportview import get as original_get

# get employee name from user
def get_employee_name(user):
    return frappe.db.get_value(
        "Employee",
        {"user": user},
        "name",
    )


# function to get all subordinate Employee names under root_employee
def get_all_subordinates(
    root_employee: str,
    department: str | None = None
) -> set[str]:
    
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
        allowed + [f"%{txt}%", page_len, start]
    )


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
        pluck="party_name",
    )

    return list(set(own_leads + opp_leads))


# to add list view restriction based on employee hierarchy
@frappe.whitelist()
def secure_get(**kwargs):
    user = frappe.session.user
    doctype = frappe.local.form_dict.get("doctype")

    if user == "Administrator":
        return original_get(**frappe.local.form_dict)

    if doctype == "Lead":
        allowed_leads = get_allowed_leads(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Lead", "name", "in", allowed_leads]]
        )
        return original_get(**frappe.local.form_dict)

    if doctype == "Opportunity":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Opportunity", "opportunity_owner", "in", owners]]
        )
        return original_get(**frappe.local.form_dict)

    if doctype == "Customer":
        owners = get_visible_employee_names(user)
        opportunities = frappe.db.get_all(
            "Opportunity",
            filters={"opportunity_owner": ["in", owners]},
            pluck="name",
        )
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Customer", "opportunity", "in", opportunities]]
        )
        return original_get(**frappe.local.form_dict)

    if doctype == "Customer":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Customer", "customer_owner", "in", owners]]
        )
        return original_get(**frappe.local.form_dict)
    
    if doctype == "Resume" or doctype == "RUC":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Resume","assign_to","in",owners]]
        )

    if doctype == "Marketing":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Marketing","assign_to","in",owners]]
        )

    if doctype == "Training":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Training","assign_to","in",owners]]
        )

    if doctype == "RUC":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["RUC","assign_to","in",owners]]
        )

    if doctype == "JDC":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["JDC","assign_to","in",owners]]
        )

    if doctype == "Cover Letter":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Cover Letter","assign_to","in",owners]]
        )

    if doctype == "Technical Other Services":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Technical Other Services","assign_to","in",owners]]
        )
    
    if doctype == "Marketing Other Services":
        owners = get_visible_employee_names(user)
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Marketing Other Services","assign_to","in",owners]]
        )

    return original_get(**frappe.local.form_dict)

import json

def send_system_notification(
    *,
    user,
    subject,
    message,
    reference_doctype=None,
    reference_name=None,
):
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": subject,
        "email_content": message,
        "for_user": user,
        "document_type": reference_doctype,
        "document_name": reference_name,
        "type": "Alert",
    }).insert(ignore_permissions=True)


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
        delayed=(not now) if now is not None else self.flags.delay_emails,
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
    attachments=None
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
            now=True,
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
    )

    return {
        "status": "success",
        "recipients": recipients,
    }