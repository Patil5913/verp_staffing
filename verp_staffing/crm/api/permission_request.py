import frappe
import json
from datetime import datetime, timedelta, timezone

from verp_staffing.crm.api.helpers import (
    get_employee_name,
    get_user,
    send_notification,
    get_approver_by_department,
)

PERMISSION_EXPIRY_MINUTES = 30


def _add_activity_log(doctype, docname, message, user):
    """Add a comment as activity log on a document."""
    try:
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": doctype,
                "reference_name": docname,
                "content": message,
                "comment_by": user,
            }
        ).insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(str(e), "Activity Log Error")


def check_candidate_form_required_from_sales_order(so_name):
    if not so_name:
        return False

    raw = frappe.db.get_single_value(
        "ERP Configuration", "candidate_details_form_fields"
    )
    
    if not raw:
        return False

    try:
        tab_data = json.loads(raw)
        services = frappe.db.get_all(
            "SalesOrderServices",
            filters={"parent": so_name, "parenttype": "Sales Order"},
            pluck="service",
        )
        for service in services:
            config = tab_data.get((service or "").lower().strip())
            if config and config.get("is_candidate_form_required") is True:
                return True
    except Exception as e:
        frappe.log_error(str(e), "Candidate Form Check Error")

    return False


def is_permission_expired(granted_at_str):
    if not granted_at_str:
        return True
    try:
        granted_at = datetime.fromisoformat(granted_at_str)
        if granted_at.tzinfo is None:
            granted_at = granted_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > granted_at + timedelta(
            minutes=PERMISSION_EXPIRY_MINUTES
        )
    except Exception:
        return True


def _get_dept_access_config():
    try:
        raw = frappe.db.get_single_value(
            "ERP Configuration", "department_access_form_fields"
        )
        if not raw:
            return {}
        return {k.lower().strip(): v for k, v in json.loads(raw).items()}
    except Exception:
        return {}


def _build_fields_from_fieldnames(allowed_fieldnames):
    """
    Given a list of fieldnames, returns simple_fields and table_fields
    by reading Lead Detail Form meta and child doctype metas dynamically.
    """
    try:
        lead_detail_meta = frappe.get_meta("Lead Detail Form")
    except Exception:
        return {"simple_fields": {}, "table_fields": {}}

    skip_fieldtypes = {
        "Section Break",
        "Column Break",
        "Tab Break",
        "HTML",
        "Button",
        "Fold",
        "Heading",
        "Read Only",
        "Attach",
        "Attach Image",
    }
    system_fields = {
        "name",
        "parent",
        "parenttype",
        "parentfield",
        "idx",
        "owner",
        "modified_by",
        "creation",
        "modified",
        "docstatus",
    }

    simple_fields = {}
    table_fields = {}

    for fieldname in allowed_fieldnames:
        fieldname = (fieldname or "").strip()
        if not fieldname:
            continue

        df = lead_detail_meta.get_field(fieldname)
        if not df:
            frappe.log_error(
                f"Field '{fieldname}' not found in Lead Detail Form meta",
                "build_fields_missing_field",
            )
            continue

        if df.fieldtype == "Table":
            child_doctype = df.options
            if not child_doctype:
                continue
            try:
                child_meta = frappe.get_meta(child_doctype)
            except Exception:
                continue

            columns = {}

            for child_df in child_meta.fields:
                if (
                    child_df.fieldtype not in skip_fieldtypes
                    and child_df.fieldname not in system_fields
                    and child_df.fieldname
                ):
                    columns[child_df.fieldname] = {
                        "label": child_df.label or child_df.fieldname.replace("_", " ").title(),
                        "fieldtype": child_df.fieldtype,
                        "options": child_df.options or "",
                        "reqd": child_df.reqd or 0,
                        "description": child_df.description or "",
                    }

            if columns:
                table_fields[fieldname] = {
                    "label": df.label or fieldname.replace("_", " ").title(),
                    "doctype": child_doctype,
                    "columns": columns,
                }
        else:
            simple_fields[fieldname] = {
                "label": df.label or fieldname.replace("_", " ").title(),
                "fieldtype": df.fieldtype,
                "options": df.options or "",
                "reqd": df.reqd or 0,
            }

    return {"simple_fields": simple_fields, "table_fields": table_fields}


def _check_candidate_form_required_for_customer(customer_name, lead_detail_doc=None):
    """
    Checks if candidate form is required for this customer.
    Checks ALL Sales Orders linked to this customer — both:
    1. Via Lead Detail Form (sales_order field)
    2. Via Sales Order.customer field (button-created)
    """
    so_names_to_check = set()

    so_via_customer = frappe.db.get_all(
        "Sales Order",
        filters={"customer": customer_name},
        pluck="name",
    )
    for so in so_via_customer:
        so_names_to_check.add(so)

    if not so_names_to_check:
        return False

    for so_name in so_names_to_check:
        if check_candidate_form_required_from_sales_order(so_name):
            return True

    return False

@frappe.whitelist()
def on_sales_order_save(doc):
    if not doc.customer:
        return

    customer_name = doc.customer
    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")
    _check_candidate_form_required_for_customer(customer_name, lead_detail_name)


@frappe.whitelist()
def get_lead_detail_form_lock_status(customer_name=None, lead_detail_name=None):
    user = frappe.session.user
    employee = get_employee_name(user)
    
    if user == "Administrator":
        return {
            "is_owner": True,
            "candidate_form_required": False,
            "permission": "full_access",
            "customer_name": customer_name,
        }

    if not employee:
        return {
            "is_owner": False,
            "candidate_form_required": False,
            "permission": "none",
        }

    if lead_detail_name and not customer_name:
        customer_name = frappe.db.get_value(
            "Customer", {"lead_details": lead_detail_name}, "name"
        )

    if not customer_name:
        return {
            "is_owner": False,
            "candidate_form_required": False,
            "permission": "none",
        }

    customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
    is_customer_owner = employee == customer_owner

    lead_owner_match = False
    lead_detail_doc = frappe.db.get_value("Customer", customer_name, "lead_details")
    if lead_detail_doc:
        lead_ref = frappe.db.get_value(
            "Doctype Reference",
            {
                "parent": lead_detail_doc,
                "parenttype": "Lead Detail Form",
                "reference_doctype": "Lead",
            },
            "reference_person",
        )
        if lead_ref:
            lead_owner = frappe.db.get_value("Lead", lead_ref, "lead_owner")
            lead_owner_match = lead_owner == employee

    is_service_assignee = False
    for doctype in [
        "Resume",
        "RUC",
        "JDC",
        "Training",
        "Cover Letter",
        "Marketing",
        "Technical Other Services",
        "Marketing Other Services",
    ]:
        try:
            if frappe.db.exists(
                doctype, {"customer": customer_name, "assign_to": employee}
            ):
                is_service_assignee = True
                break
        except Exception:
            continue

    is_owner = is_customer_owner or lead_owner_match or is_service_assignee

    # ── Check candidate form required ──
    # Check ALL Sales Orders for this customer — both from Lead Detail Form and button-created ones
    candidate_form_required = _check_candidate_form_required_for_customer(
        customer_name, lead_detail_doc
    )

    return {
        "is_owner": is_owner,
        "candidate_form_required": candidate_form_required,
        "permission": "none",
        "customer_name": customer_name,
    }


@frappe.whitelist()
def get_department_updatable_fields(doctype=None):
    dept_access = _get_dept_access_config()
    if not dept_access:
        return {"simple_fields": {}, "table_fields": {}}

    if not doctype:
        return {"simple_fields": {}, "table_fields": {}}

    key = (doctype or "").lower().strip()

    allowed_fieldnames = dept_access.get(key, [])

    if not allowed_fieldnames:
        return {"simple_fields": {}, "table_fields": {}}

    return _build_fields_from_fieldnames(allowed_fieldnames)


@frappe.whitelist()
def get_customer_owner_updatable_fields():
    """
    Returns simple_fields and table_fields for the customer owner
    using the 'customer' key in ERP Configuration → department_access_form_fields.
    Called when Update Detail dialog opens on Customer form.
    """
    dept_access_normalized = _get_dept_access_config()
    allowed_fieldnames = dept_access_normalized.get("customer", [])
    if not allowed_fieldnames:
        return {"simple_fields": {}, "table_fields": {}}
    return _build_fields_from_fieldnames(allowed_fieldnames)


@frappe.whitelist()
def get_lead_detail_field_values(customer_name):
    """
    Returns current field values from Lead Detail Form for a customer.
    Fetches all fields that any department could possibly see.
    Called before opening the Update Detail dialog to show current values.
    """
    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")
    if not lead_detail_name:
        return {}

    dept_access_normalized = _get_dept_access_config()

    # Collect ALL fieldnames across ALL department keys
    all_fieldnames = set()
    for fieldnames in dept_access_normalized.values():
        for f in fieldnames:
            if f and f.strip():
                all_fieldnames.add(f.strip())

    if not all_fieldnames:
        return {}

    try:
        lead_detail_meta = frappe.get_meta("Lead Detail Form")
    except Exception:
        return {}

    skip_fieldtypes = {
        "Section Break",
        "Column Break",
        "Tab Break",
        "HTML",
        "Button",
        "Fold",
        "Heading",
        "Read Only",
        "Attach",
        "Attach Image",
    }
    system_fields = {
        "name",
        "parent",
        "parenttype",
        "parentfield",
        "idx",
        "owner",
        "modified_by",
        "creation",
        "modified",
        "docstatus",
    }

    # Separate simple and table fieldnames
    simple_fieldnames = []
    table_fieldnames = []

    for fieldname in all_fieldnames:
        df = lead_detail_meta.get_field(fieldname)
        if not df:
            continue
        if df.fieldtype == "Table":
            table_fieldnames.append(fieldname)
        else:
            simple_fieldnames.append(fieldname)

    # Fetch simple field values in one query
    values = {}
    if simple_fieldnames:
        values = (
            frappe.db.get_value(
                "Lead Detail Form",
                lead_detail_name,
                simple_fieldnames,
                as_dict=True,
            )
            or {}
        )

    # Fetch table field values
    for fieldname in table_fieldnames:
        df = lead_detail_meta.get_field(fieldname)
        if not df or not df.options:
            continue
        try:
            child_meta = frappe.get_meta(df.options)
            col_fieldnames = [
                cf.fieldname
                for cf in child_meta.fields
                if cf.fieldtype not in skip_fieldtypes
                and cf.fieldname not in system_fields
                and cf.fieldname
            ]
            rows = frappe.db.get_all(
                df.options,
                filters={"parent": lead_detail_name, "parenttype": "Lead Detail Form"},
                fields=col_fieldnames,
                order_by="idx asc",
            )
            values[fieldname] = rows
        except Exception:
            continue

    return values


def get_department_from_service(service_name):
    if not service_name:
        return None

    # Loop through all departments
    departments = frappe.get_all("Department", fields=["name", "department_name"])

    for dept in departments:
        services = frappe.get_all(
            "Department Service", filters={"parent": dept.name}, pluck="service"
        )

        # Match ignore case
        for s in services:
            if s and s.strip().lower() == service_name.strip().lower():
                frappe.errprint(f"[DEPT] '{service_name}' → '{dept.department_name}'")
                return dept.department_name

    return None


@frappe.whitelist()
def request_field_update(
    customer_name,
    reason,
    field_updates,
    service_doctype=None,
    service_name=None,
    extra_info=None,
):
    # frappe.errprint(f"data {service_doctype}, {service_name} , {extra_info}")
    user = frappe.session.user
    employee = get_employee_name(user)
    if not employee:
        frappe.throw("No Employee record found for the current user.")

    if not frappe.db.get_value("Customer", customer_name, "customer_owner"):
        frappe.throw("No customer owner found for this Customer.")

    department = None

    if extra_info:
        department = get_department_from_service(extra_info)

    elif service_doctype:
        department = get_department_from_service(service_doctype)
        
    manager_employee = get_approver_by_department(employee, service_doctype, extra_info)
    if not manager_employee:
        frappe.throw(
            f"Permission Request Configuration Is Not Set Up Properly For {department} Department. Please Contact Administrator."
        )

    manager_user = get_user(manager_employee)
    if not manager_user:
        frappe.throw("Approver employee has no linked User account.")

    if isinstance(field_updates, str):
        field_updates = json.loads(field_updates)

    # Build field labels for activity log
    lead_detail_meta = frappe.get_meta("Lead Detail Form")
    field_labels = []
    for f in field_updates.keys():
        df = lead_detail_meta.get_field(f)
        label = None
        if df:
            label = df.label or df.fieldname
        if not label:
            label = f.replace("_", " ").title()
        field_labels.append(str(label))

    comment = frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Customer",
            "reference_name": customer_name,
            "content": json.dumps(
                {
                    "type": "field_update_request",
                    "reason": reason,
                    "requested_by_employee": employee,
                    "requested_by_user": user,
                    "approver_employee": manager_employee,
                    "approver_user": manager_user,
                    "status": "Pending",
                    "field_updates": field_updates,
                    "service_doctype": service_doctype,
                    "service_name": service_name,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            "comment_by": user,
        }
    )
    comment.insert(ignore_permissions=True)

    manager_email = frappe.db.get_value("User", manager_user, "email")

    # 📧 SEND EMAIL
    template_name = "Field Update Request - permission request"
    print(f"-----template in field update request: {template_name}, exists: {frappe.db.exists('Email Template', template_name)}")
    if frappe.db.exists("Email Template", template_name):
        template = frappe.get_doc("Email Template", template_name)
        context = {
            "customer_name": customer_name,
            "employee": employee,
            "reason": reason,
            "field_labels": ", ".join(field_labels),
        }
        subject = frappe.render_template(template.subject, context)
        message = frappe.render_template(
            template.response_html or template.response, context
        )
    else:
        subject = f"Field Update Request for Customer {customer_name}"
        message = (
            f"Employee <b>{employee}</b> has requested to update fields "
            f"on Customer <b>{customer_name}</b>.<br><br>"
            f"<b>Reason:</b> {reason}<br><br>"
            f"<b>Fields:</b> {', '.join(field_labels)}<br><br>"
            f"Please open Customer <b>{customer_name}</b> and click <b>Accept Updates</b> to review."
        )

    send_notification(
        recipients=[manager_email],
        subject=subject,
        message=message,
        reference_doctype="Customer",
        reference_name=customer_name,
        send_email=1,
        send_system=1,
    )
    print(f"---------------------send notification: {send_notification}")

    activity_message = (
        f"<b> requested field update for: <b>{', '.join(field_labels)}</b>.<br>"
        f"<b>Reason:</b> {reason}<br>"
        f"Sent to manager <b>{manager_employee}</b> for approval."
    )

    # ── Log on Customer ──
    _add_activity_log("Customer", customer_name, activity_message, user)

    # ── Log on service doctype if provided ──
    if service_doctype and service_name:
        _add_activity_log(service_doctype, service_name, activity_message, user)

    return {"status": "success", "manager_employee": manager_employee}


@frappe.whitelist()
def request_field_update_by_owner(customer_name, reason, field_updates):
    user = frappe.session.user
    employee = get_employee_name(user)
    if not employee:
        frappe.throw("No Employee record found for the current user.")

    customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
    if customer_owner != employee:
        frappe.throw("Only the customer owner can send this request.")

    manager_employee = get_approver_by_department(employee)
    if not manager_employee:
        frappe.throw("Permission Request Configuration Is Not Set Up Properly For Sales Department. Please Contact Administrator.")

    manager_user = get_user(manager_employee)
    if not manager_user:
        frappe.throw("Approver employee has no linked User account.")

    if isinstance(field_updates, str):
        field_updates = json.loads(field_updates)

    lead_detail_meta = frappe.get_meta("Lead Detail Form")
    field_labels = []
    for f in field_updates.keys():
        df = lead_detail_meta.get_field(f)
        label = None
        if df:
            label = df.label or df.fieldname
        if not label:
            label = f.replace("_", " ").title()
        field_labels.append(str(label))

    comment = frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Customer",
            "reference_name": customer_name,
            "content": json.dumps(
                {
                    "type": "field_update_request",
                    "reason": reason,
                    "requested_by_employee": employee,
                    "requested_by_user": user,
                    "approver_employee": manager_employee,
                    "approver_user": manager_user,
                    "status": "Pending",
                    "field_updates": field_updates,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            "comment_by": user,
        }
    )
    comment.insert(ignore_permissions=True)

    manager_email = frappe.db.get_value("User", manager_user, "email")

    # 📧 SEND EMAIL
    template_name = "Field Update Request by owner - Permission Request"
    if frappe.db.exists("Email Template", template_name):
        template = frappe.get_doc("Email Template", template_name)
        context = {
            "customer_name": customer_name,
            "employee": employee,
            "reason": reason,
            "field_labels": ", ".join(field_labels),
        }
        subject = frappe.render_template(template.subject, context)
        message = frappe.render_template(
            template.response_html or template.response, context
        )
    else:
        subject = f"Field Update Request for Customer {customer_name}"
        message = (
            f"Employee <b>{employee}</b> has requested to update fields "
            f"on Customer <b>{customer_name}</b>.<br><br>"
            f"<b>Reason:</b> {reason}<br><br>"
            f"<b>Fields:</b> {', '.join(field_labels)}<br><br>"
            f"Please open Customer <b>{customer_name}</b> and click <b>Accept Updates</b> to review."
        )

    send_notification(
        recipients=[manager_email],
        subject=subject,
        message=message,
        reference_doctype="Customer",
        reference_name=customer_name,
        send_email=1,
        send_system=1,
    )

    activity_message = (
        f"<b>{employee}</b> (Customer Owner) requested field update for: <b>{', '.join(field_labels)}</b>.<br>"
        f"<b>Reason:</b> {reason}<br>"
        f"Sent to manager <b>{manager_employee}</b> for approval."
    )

    # ── Log on Customer only (owner request) ──
    _add_activity_log("Customer", customer_name, activity_message, user)

    return {"status": "success", "manager_employee": manager_employee}


@frappe.whitelist()
def get_pending_field_update_request(customer_name):
    """Returns single pending request where logged-in employee is the approver."""
    user = frappe.session.user
    current_employee = get_employee_name(user)
    if not current_employee:
        return {"has_pending": False}

    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Customer",
            "reference_name": customer_name,
            "comment_type": "Info",
        },
        fields=["name", "content"],
        order_by="creation desc",
    )

    for c in comments:
        try:
            data = json.loads(c.content)
            if (
                data.get("type") == "field_update_request"
                and data.get("status") == "Pending"
                and data.get("approver_employee") == current_employee
            ):
                return {
                    "has_pending": True,
                    "comment_name": c.name,
                    "requested_by": data.get("requested_by_employee"),
                    "reason": data.get("reason"),
                    "field_updates": data.get("field_updates", {}),
                }
        except Exception:
            continue

    return {"has_pending": False}


@frappe.whitelist()
def get_all_pending_field_update_requests(customer_name):
    """Returns ALL pending requests where logged-in employee is the approver."""
    user = frappe.session.user
    current_employee = get_employee_name(user)
    if not current_employee:
        return []

    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Customer",
            "reference_name": customer_name,
            "comment_type": "Info",
        },
        fields=["name", "content"],
        order_by="creation desc",
    )

    pending = []
    for c in comments:
        try:
            data = json.loads(c.content)
            if (
                data.get("type") == "field_update_request"
                and data.get("status") == "Pending"
                and data.get("approver_employee") == current_employee
            ):
                pending.append(
                    {
                        "comment_name": c.name,
                        "requested_by": data.get("requested_by_employee"),
                        "reason": data.get("reason"),
                        "field_updates": data.get("field_updates", {}),
                    }
                )
        except Exception:
            continue

    return pending


@frappe.whitelist()
def get_candidate_form_required_status(customer_name):
    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")
    required = _check_candidate_form_required_for_customer(
        customer_name, lead_detail_name
    )
    return {"required": required}


@frappe.whitelist()
def get_owner_pending_field_update_request(customer_name):
    """Checks if customer_owner already has a pending request."""
    user = frappe.session.user
    employee = get_employee_name(user)
    if not employee:
        return {"has_pending": False}

    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Customer",
            "reference_name": customer_name,
            "comment_type": "Info",
        },
        fields=["name", "content"],
        order_by="creation desc",
    )

    for c in comments:
        try:
            data = json.loads(c.content)
            if (
                data.get("type") == "field_update_request"
                and data.get("status") == "Pending"
                and data.get("requested_by_employee") == employee
            ):
                return {"has_pending": True}
        except Exception:
            continue

    return {"has_pending": False}


@frappe.whitelist()
def apply_field_updates(customer_name, comment_name, approved_fields):
    user = frappe.session.user
    manager_employee = get_employee_name(user)
    if not manager_employee:
        frappe.throw("No Employee record found.")

    if isinstance(approved_fields, str):
        approved_fields = json.loads(approved_fields)

    comment_doc = frappe.get_doc("Comment", comment_name)
    data = json.loads(comment_doc.content)

    if frappe.session.user != "Administrator" and data.get("status") != "Pending":
        frappe.throw("This request has already been processed.")

    field_updates = data.get("field_updates", {})
    requester_employee = data.get("requested_by_employee")
    service_doctype = data.get("service_doctype")
    service_name = data.get("service_name")

    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")
    if not lead_detail_name:
        frappe.throw("No Lead Detail Form found for this Customer.")

    lead_detail_meta = frappe.get_meta("Lead Detail Form")
    updated_fields = {}
    rejected_fields = []

    # Find which fields were NOT approved (rejected)
    all_requested_fields = list(field_updates.keys())
    rejected_fields = [f for f in all_requested_fields if f not in approved_fields]

    for field in approved_fields:
        if field not in field_updates:
            continue

        df = lead_detail_meta.get_field(field)
        if not df:
            frappe.log_error(
                f"Field '{field}' not found in Lead Detail Form", "apply_field_updates"
            )
            continue

        if df.fieldtype == "Table":
            child_doctype = df.options
            if not child_doctype:
                continue
            new_rows = field_updates[field].get("new", [])

            frappe.db.delete(
                child_doctype,
                {
                    "parent": lead_detail_name,
                    "parenttype": "Lead Detail Form",
                    "parentfield": field,
                },
            )

            for idx, row in enumerate(new_rows):
                frappe.get_doc(
                    {
                        "doctype": child_doctype,
                        "parent": lead_detail_name,
                        "parenttype": "Lead Detail Form",
                        "parentfield": field,
                        "idx": idx + 1,
                        **row,
                    }
                ).insert(ignore_permissions=True)

            updated_fields[field] = new_rows

        elif df.fieldtype in [
            "Data",
            "Text",
            "Small Text",
            "Long Text",
            "Date",
            "Datetime",
            "Int",
            "Float",
            "Currency",
            "Check",
            "Select",
            "Link",
        ]:
            new_value = field_updates[field].get("new")
            frappe.db.set_value("Lead Detail Form", lead_detail_name, field, new_value)
            updated_fields[field] = new_value

    data["status"] = "Approved"
    data["approved_by"] = manager_employee  
    data["approved_fields"] = approved_fields
    data["rejected_fields"] = rejected_fields
    data["approved_at"] = datetime.now(timezone.utc).isoformat()
    frappe.db.set_value("Comment", comment_name, "content", json.dumps(data))
    frappe.db.commit()

    # ── Build activity log message ──
    approved_labels = []
    rejected_labels = []
    for f in approved_fields:
        df = lead_detail_meta.get_field(f)
        label = df.label if df and df.label else f.replace("_", " ").title()
        approved_labels.append(str(label))
    for f in rejected_fields:
        df = lead_detail_meta.get_field(f)
        label = df.label if df and df.label else f.replace("_", " ").title()
        rejected_labels.append(str(label))

    activity_parts = []
    if approved_labels:
        activity_parts.append(f" Approved: <b>{', '.join(approved_labels)}</b>")
    if rejected_labels:
        activity_parts.append(f" Rejected: <b>{', '.join(rejected_labels)}</b>")

    activity_message = (
        f"Field update request from <b>{requester_employee}</b> reviewed by <b>{manager_employee}</b>.<br>"
        + "<br>".join(activity_parts)
    )

    # ── Add activity log to Customer ──
    _add_activity_log("Customer", customer_name, activity_message, user)

    # ── Add activity log to Service Doctype (NEW) ──
    if service_doctype and service_name:
        _add_activity_log(service_doctype, service_name, activity_message, user)

    # ── Notify requester ──
    requester_user = data.get("requested_by_user")
    if requester_user:
        requester_email = frappe.db.get_value("User", requester_user, "email")
        if requester_email:
            notify_parts = []
            if approved_labels:
                notify_parts.append(f"Approved: <b>{', '.join(approved_labels)}</b>")
            if rejected_labels:
                notify_parts.append(f"Rejected: <b>{', '.join(rejected_labels)}</b>")

            template_name = "Field Update Request Reviewed - permission request"
            if frappe.db.exists("Email Template", template_name):
                template = frappe.get_doc("Email Template", template_name)
                context = {
                    "customer_name": customer_name,
                    "manager_employee": manager_employee,
                    "requester_employee": requester_employee,
                    "notify_parts": "<br>".join(notify_parts),
                }
                subject = frappe.render_template(template.subject, context)
                message = frappe.render_template(
                    template.response_html or template.response, context
                )
            else:
                subject = f"Field Update Request Reviewed for Customer {customer_name}"
                message = (
                    f"Your manager <b>{manager_employee}</b> has reviewed your field update request.<br><br>"
                    + "<br>".join(notify_parts)
                    + "<br><br>The Lead Detail Form has been updated accordingly."
                )

            send_notification(
                recipients=[requester_email],
                subject=subject,
                message=message,
                reference_doctype="Customer",
                reference_name=customer_name,
                send_email=1,
                send_system=1,
            )

    return {
        "status": "success",
        "updated_fields": updated_fields,
        "rejected_fields": rejected_fields,
    }


@frappe.whitelist()
def reject_field_update_request(customer_name, comment_name):
    """Manager rejects entire field update request."""
    user = frappe.session.user
    manager_employee = get_employee_name(user)
    if not manager_employee:
        frappe.throw("No Employee record found.")

    comment_doc = frappe.get_doc("Comment", comment_name)
    data = json.loads(comment_doc.content)

    if data.get("status") != "Pending":
        frappe.throw("This request has already been processed.")

    requester_employee = data.get("requested_by_employee")
    field_updates = data.get("field_updates", {})
    service_doctype = data.get("service_doctype")
    service_name = data.get("service_name")

    # Build field labels
    lead_detail_meta = frappe.get_meta("Lead Detail Form")
    field_labels = []
    for f in field_updates.keys():
        df = lead_detail_meta.get_field(f)
        label = None
        if df:
            label = df.label or df.fieldname
        if not label:
            label = f.replace("_", " ").title()
        field_labels.append(str(label))

    data["status"] = "Rejected"
    data["rejected_by"] = manager_employee
    data["rejected_at"] = datetime.now(timezone.utc).isoformat()
    frappe.db.set_value("Comment", comment_name, "content", json.dumps(data))
    frappe.db.commit()

    activity_message = (
        f"<b>{manager_employee}</b> rejected field update request from <b>{requester_employee}</b>.<br>"
        f" Rejected fields: <b>{', '.join(field_labels)}</b>"
    )

    # ── Log on Customer ──
    _add_activity_log("Customer", customer_name, activity_message, user)

    # ── Log on service doctype if present ──
    if service_doctype and service_name:
        _add_activity_log(service_doctype, service_name, activity_message, user)

    # ── Notify requester ──
    requester_user = data.get("requested_by_user")
    if requester_user:
        requester_email = frappe.db.get_value("User", requester_user, "email")
        if requester_email:
            template_name = "Field Update Request Rejected - permission request"
            if frappe.db.exists("Email Template", template_name):
                template = frappe.get_doc("Email Template", template_name)
                context = {
                    "customer_name": customer_name,
                    "manager_employee": manager_employee,
                    "requester_employee": requester_employee,
                    "field_labels": ", ".join(field_labels),
                }
                subject = frappe.render_template(template.subject, context)
                message = frappe.render_template(
                    template.response_html or template.response, context
                )
            else:
                subject = f"Field Update Request Rejected for Customer {customer_name}"
                message = (
                    f"Your manager <b>{manager_employee}</b> has rejected your field update request.<br><br>"
                    f"<b>Rejected fields:</b> {', '.join(field_labels)}"
                )

            send_notification(
                recipients=[requester_email],
                subject=subject,
                message=message,
                reference_doctype="Customer",
                reference_name=customer_name,
                send_email=1,
                send_system=1,
            )

    return {"status": "success"}
