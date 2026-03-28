# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
import json
from datetime import datetime, timedelta, timezone

from verp_staffing.crm.api.helpers import (
    get_employee_name,
    get_user,
    send_system_notification,
    send_notification,
    get_approver_by_department,
)

PERMISSION_EXPIRY_MINUTES = 30

# UPDATABLE_FIELDS = {
#     "surname": "Surname",
#     "first_name": "First Name",
#     "father_name": "Father Name",
#     # "email": "Email",
# }

# UPDATABLE_TABLE_FIELDS = {
#     "address_history": {
#         "label": "Address History",
#         "doctype": "Lead Address History",
#         "columns": {
#             "state": "State",
#             "country": "Country",
#             "from_date": "From Date",
#             "to_date": "To Date",
#         },
#     }
# }


@frappe.whitelist()
def get_lead_detail_fields_meta():
    try:
        meta = frappe.get_meta("Lead Detail Form")
    except Exception:
        return {}

    # frappe.errprint(f"{meta}")
    skip_fieldtypes = [
        "Section Break",
        "Column Break",
        "Tab Break",
        "HTML",
        "Button",
        "Fold",
        "Heading",
    ]

    fields = {}

    for df in meta.fields:
        if df.fieldtype in skip_fieldtypes:
            continue

        if not df.fieldname:
            continue

        fields[df.fieldname] = df.label or df.fieldname.replace("_", " ").title()

    return fields


def get_manager_of_employee(employee_name):
    result = frappe.db.get_value(
        "Employee Assignment Detail",
        filters={"parent": employee_name},
        fieldname="assigned_to",
    )
    return result or None


def check_candidate_form_required_from_sales_order(so_name):
    if not so_name:
        return False

    candidate_form_fields_tab = frappe.db.get_single_value(
        "ERP Configuration", "candidate_details_form_fields"
    )

    if not candidate_form_fields_tab:
        return False

    try:
        tab_data = json.loads(candidate_form_fields_tab)

        services = frappe.db.get_all(
            "SalesOrderServices",
            filters={"parent": so_name, "parenttype": "Sales Order"},
            pluck="service",
        )

        for service in services:
            service_key = (service or "").lower().strip()
            service_config = tab_data.get(service_key)
            if (
                service_config
                and service_config.get("is_candidate_form_required") is True
            ):
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
        expiry_time = granted_at + timedelta(minutes=PERMISSION_EXPIRY_MINUTES)
        now_utc = datetime.now(timezone.utc)
        return now_utc > expiry_time
    except Exception:
        return True


@frappe.whitelist()
def _request_permission(ref_doctype, ref_name, reason):
    user = frappe.session.user
    employee = get_employee_name(user)
    if not employee:
        frappe.throw("No Employee record found for the current user.")

    if ref_doctype == "Customer":
        customer_owner = frappe.db.get_value("Customer", ref_name, "customer_owner")
        if not customer_owner:
            frappe.throw("No customer owner found for this Customer.")
        manager_employee = get_approver_by_department(customer_owner)
    else:
        manager_employee = get_approver_by_department(employee)

    if not manager_employee:
        frappe.throw("No suitable approver found in the hierarchy.")

    manager_user = get_user(manager_employee)
    if not manager_user:
        frappe.throw("Approver employee has no linked User account.")

    comment = frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": ref_doctype,
            "reference_name": ref_name,
            "content": json.dumps(
                {
                    "type": "update_permission_request",
                    "reason": reason,
                    "requested_by_employee": employee,
                    "requested_by_user": user,
                    "approver_employee": manager_employee,
                    "approver_user": manager_user,
                    "status": "Pending",
                    "granted_at": None,
                }
            ),
            "comment_by": user,
        }
    )
    comment.insert(ignore_permissions=True)

    manager_email = frappe.db.get_value("User", manager_user, "email")

    send_notification(
        recipients=[manager_email],
        subject=f"Update Permission Request for {ref_doctype} {ref_name}",
        message=(
            f"Employee <b>{employee}</b> has requested permission to update "
            f"fields on {ref_doctype} <b>{ref_name}</b>.<br><br>"
            f"<b>Reason:</b> {reason}<br><br>"
            f"Please open the form and click <b>Give Permission</b> to approve."
        ),
        reference_doctype=ref_doctype,
        reference_name=ref_name,
        send_email=1,
        send_system=1,
    )

    return {
        "status": "success",
        "comment_name": comment.name,
        "manager_employee": manager_employee,
        "manager_user": manager_user,
    }


@frappe.whitelist()
def _check_permission_status(ref_doctype, ref_name):
    user = frappe.session.user
    employee = get_employee_name(user)

    if not employee:
        return {"status": "none"}

    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": ref_doctype,
            "reference_name": ref_name,
            "comment_type": "Info",
        },
        fields=["name", "content"],
        order_by="creation desc",
    )

    for c in comments:
        try:
            data = json.loads(c.content)
            if (
                data.get("type") == "update_permission_request"
                and data.get("requested_by_employee") == employee
            ):
                raw_status = data.get("status", "Pending")

                if raw_status == "Approved":
                    granted_at = data.get("granted_at")

                    if is_permission_expired(granted_at):
                        data["status"] = "Expired"
                        frappe.db.set_value(
                            "Comment", c.name, "content", json.dumps(data)
                        )
                        frappe.db.commit()
                        return {"status": "expired"}

                    granted_dt = datetime.fromisoformat(granted_at)
                    if granted_dt.tzinfo is None:
                        granted_dt = granted_dt.replace(tzinfo=timezone.utc)
                    expiry_dt = granted_dt + timedelta(
                        minutes=PERMISSION_EXPIRY_MINUTES
                    )
                    remaining_seconds = int(
                        (expiry_dt - datetime.now(timezone.utc)).total_seconds()
                    )

                    return {
                        "status": "approved",
                        "remaining_seconds": max(remaining_seconds, 0),
                    }

                if raw_status == "Declined":
                    return {"status": "declined"}

                return {"status": raw_status.lower()}

        except Exception:
            continue

    return {"status": "none"}


@frappe.whitelist()
def get_lead_detail_form_lock_status(customer_name=None, lead_detail_name=None):
    user = frappe.session.user

    try:
        employee = get_employee_name(user)
    except Exception:
        employee = None

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

    # Check if employee is lead_owner of linked Lead
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
            if lead_owner == employee:
                lead_owner_match = True

    # Check if employee is assign_to on ANY service doctype for this customer
    service_doctypes = [
        "Resume",
        "RUC",
        "JDC",
        "Training",
        "Cover Letter",
        "Marketing",
        "Technical Other Services",
        "Marketing Other Services",
    ]
    is_service_assignee = False

    for doctype in service_doctypes:
        try:
            exists = frappe.db.exists(
                doctype,
                {
                    "customer": customer_name,
                    "assign_to": employee,
                },
            )
            if exists:
                is_service_assignee = True
                break
        except Exception:
            continue

    is_owner = is_customer_owner or lead_owner_match or is_service_assignee

    # Check candidate form required via ERP Configuration JSON
    resolved_lead_detail = frappe.db.get_value(
        "Customer", customer_name, "lead_details"
    )
    candidate_form_required = False

    if resolved_lead_detail:
        so_name = frappe.db.get_value(
            "Lead Detail Form", resolved_lead_detail, "sales_order"
        )
        candidate_form_required = check_candidate_form_required_from_sales_order(
            so_name
        )

    return {
        "is_owner": is_owner,
        "candidate_form_required": candidate_form_required,
        "permission": "none",
        "customer_name": customer_name,
    }


@frappe.whitelist()
def request_field_update(customer_name, reason, field_updates):
    user = frappe.session.user

    try:
        employee = get_employee_name(user)
    except Exception:
        employee = None

    if not employee:
        frappe.throw("No Employee record found for the current user.")

    customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
    if not customer_owner:
        frappe.throw("No customer owner found for this Customer.")

    # Route based on requesting employee's own department
    manager_employee = get_approver_by_department(employee)
    if not manager_employee:
        frappe.throw("No suitable approver found in your hierarchy.")

    manager_user = get_user(manager_employee)
    if not manager_user:
        frappe.throw("Approver employee has no linked User account.")

    if isinstance(field_updates, str):
        field_updates = json.loads(field_updates)

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

    send_notification(
        recipients=[manager_email],
        subject=f"Field Update Request for Customer {customer_name}",
        message=(
            f"Employee <b>{employee}</b> has requested to update fields "
            f"on Customer <b>{customer_name}</b>.<br><br>"
            f"<b>Reason:</b> {reason}<br><br>"
            f"Please open Customer <b>{customer_name}</b> and click "
            f"<b>Accept Updates</b> to review."
        ),
        reference_doctype="Customer",
        reference_name=customer_name,
        send_email=1,
        send_system=1,
    )

    return {
        "status": "success",
        "manager_employee": manager_employee,
    }


@frappe.whitelist()
def get_pending_field_update_request(customer_name):
    user = frappe.session.user

    try:
        current_employee = get_employee_name(user)
    except Exception:
        current_employee = None

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
    user = frappe.session.user

    try:
        current_employee = get_employee_name(user)
    except Exception:
        current_employee = None

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


# @frappe.whitelist()
# def apply_field_updates(customer_name, comment_name, approved_fields):
#     user = frappe.session.user

#     try:
#         manager_employee = get_employee_name(user)
#     except Exception:
#         manager_employee = None

#     if not manager_employee:
#         frappe.throw("No Employee record found.")

#     if isinstance(approved_fields, str):
#         approved_fields = json.loads(approved_fields)

#     comment_doc = frappe.get_doc("Comment", comment_name)
#     data = json.loads(comment_doc.content)

#     if data.get("status") != "Pending":
#         frappe.throw("This request has already been processed.")

#     field_updates = data.get("field_updates", {})

#     lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")

#     if not lead_detail_name:
#         frappe.throw("No Lead Detail Form found for this Customer.")

#     updated_fields = {}

#     for field in approved_fields:
#         if field in field_updates:
#             # ── Handle table fields ──
#             if field in UPDATABLE_TABLE_FIELDS:
#                 config = UPDATABLE_TABLE_FIELDS[field]
#                 new_rows = field_updates[field].get("new", [])

#                 # Delete existing rows
#                 frappe.db.delete(
#                     config["doctype"],
#                     {
#                         "parent": lead_detail_name,
#                         "parenttype": "Lead Detail Form",
#                     },
#                 )

#                 # Insert new rows
#                 for idx, row in enumerate(new_rows):
#                     new_row = frappe.get_doc(
#                         {
#                             "doctype": config["doctype"],
#                             "parent": lead_detail_name,
#                             "parenttype": "Lead Detail Form",
#                             "parentfield": field,
#                             "idx": idx + 1,
#                             **{k: row.get(k, "") for k in config["columns"].keys()},
#                         }
#                     )
#                     new_row.insert(ignore_permissions=True)

#                 updated_fields[field] = new_rows

#             # ── Handle simple fields ──
#             elif field in UPDATABLE_FIELDS:
#                 new_value = field_updates[field].get("new")
#                 frappe.db.set_value(
#                     "Lead Detail Form",
#                     lead_detail_name,
#                     field,
#                     new_value,
#                 )
#                 updated_fields[field] = new_value

#     # Mark comment as processed
#     data["status"] = "Approved"
#     data["approved_by"] = manager_employee
#     data["approved_fields"] = approved_fields
#     data["approved_at"] = datetime.now(timezone.utc).isoformat()
#     frappe.db.set_value("Comment", comment_name, "content", json.dumps(data))
#     frappe.db.commit()

#     # Notify requester
#     requester_user = data.get("requested_by_user")
#     if requester_user:
#         requester_email = frappe.db.get_value("User", requester_user, "email")
#         if requester_email:
#             field_names = ", ".join(
#                 UPDATABLE_FIELDS.get(
#                     f, UPDATABLE_TABLE_FIELDS.get(f, {}).get("label", f)
#                 )
#                 for f in approved_fields
#             )
#             send_notification(
#                 recipients=[requester_email],
#                 subject=f"Field Updates Approved for Customer {customer_name}",
#                 message=(
#                     f"Your manager <b>{manager_employee}</b> has approved updates "
#                     f"for: <b>{field_names}</b>.<br><br>"
#                     f"The Lead Detail Form has been updated."
#                 ),
#                 reference_doctype="Customer",
#                 reference_name=customer_name,
#                 send_email=1,
#                 send_system=1,
#             )

#     return {
#         "status": "success",
#         "updated_fields": updated_fields,
#     }


@frappe.whitelist()
def apply_field_updates(customer_name, comment_name, approved_fields):
    user = frappe.session.user
    try:
        manager_employee = get_employee_name(user)
    except Exception:
        manager_employee = None

    if not manager_employee:
        frappe.throw("No Employee record found.")

    if isinstance(approved_fields, str):
        approved_fields = json.loads(approved_fields)

    comment_doc = frappe.get_doc("Comment", comment_name)
    data = json.loads(comment_doc.content)

    if data.get("status") != "Pending":
        frappe.throw("This request has already been processed.")

    field_updates = data.get("field_updates", {})
    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")

    if not lead_detail_name:
        frappe.throw("No Lead Detail Form found for this Customer.")

    # Get Lead Detail Form meta for dynamic field handling
    lead_detail_meta = frappe.get_meta("Lead Detail Form")
    updated_fields = {}

    for field in approved_fields:
        if field not in field_updates:
            continue

        df = lead_detail_meta.get_field(field)
        if not df:
            frappe.log_error(
                f"Field '{field}' not found in Lead Detail Form", "apply_field_updates"
            )
            continue

        # Handle TABLE fields
        if df.fieldtype == "Table":
            child_doctype = df.options
            if not child_doctype:
                continue

            new_rows = field_updates[field].get("new", [])

            # Delete existing rows for this table field
            frappe.db.delete(
                child_doctype,
                {
                    "parent": lead_detail_name,
                    "parenttype": "Lead Detail Form",
                    "parentfield": field,  # Important: specify parentfield
                },
            )

            # Insert new rows
            for idx, row in enumerate(new_rows):
                new_row = frappe.get_doc(
                    {
                        "doctype": child_doctype,
                        "parent": lead_detail_name,
                        "parenttype": "Lead Detail Form",
                        "parentfield": field,
                        "idx": idx + 1,
                        **row,  # Spread row data
                    }
                )
                new_row.insert(ignore_permissions=True)

            updated_fields[field] = new_rows

        # Handle SIMPLE fields (Data, Text, Date, etc.)
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
        ]:
            new_value = field_updates[field].get("new")
            frappe.db.set_value(
                "Lead Detail Form",
                lead_detail_name,
                field,
                new_value,
            )
            updated_fields[field] = new_value

        else:
            frappe.log_error(
                f"Unsupported fieldtype '{df.fieldtype}' for field '{field}'",
                "apply_field_updates",
            )

    # Mark comment as processed
    data["status"] = "Approved"
    data["approved_by"] = manager_employee
    data["approved_fields"] = approved_fields
    data["approved_at"] = datetime.now(timezone.utc).isoformat()
    frappe.db.set_value("Comment", comment_name, "content", json.dumps(data))
    frappe.db.commit()

    # Notify requester (same as before)
    requester_user = data.get("requested_by_user")
    if requester_user:
        requester_email = frappe.db.get_value("User", requester_user, "email")
        if requester_email:
            # Get field labels dynamically
            field_labels = []
            for f in approved_fields:
                df = lead_detail_meta.get_field(f)
                label = df.label if df else f.replace("_", " ").title()
                field_labels.append(label)

            field_names = ", ".join(field_labels)
            send_notification(
                recipients=[requester_email],
                subject=f"Field Updates Approved for Customer {customer_name}",
                message=(
                    f"Your manager <b>{manager_employee}</b> has approved updates "
                    f"for: <b>{field_names}</b>.<br><br>"
                    f"The Lead Detail Form has been updated."
                ),
                reference_doctype="Customer",
                reference_name=customer_name,
                send_email=1,
                send_system=1,
            )

    return {
        "status": "success",
        "updated_fields": updated_fields,
    }


# @frappe.whitelist()
# def get_lead_detail_field_values(customer_name):
#     lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")

#     if not lead_detail_name:
#         return {}

#     values = (
#         frappe.db.get_value(
#             "Lead Detail Form",
#             lead_detail_name,
#             list(UPDATABLE_FIELDS.keys()),
#             as_dict=True,
#         )
#         or {}
#     )

#     # ── Fetch ALL table fields from ERP Configuration dynamically ──
#     # so any table field in any dept key is returned
#     try:
#         dept_access_raw = frappe.db.get_single_value(
#             "ERP Configuration", "department_access_form_fields"
#         )
#         if dept_access_raw:
#             dept_access = json.loads(dept_access_raw)
#             lead_detail_meta = frappe.get_meta("Lead Detail Form")

#             # Collect all unique fieldnames across all dept keys
#             all_fieldnames = set()
#             for fieldnames in dept_access.values():
#                 for f in fieldnames:
#                     all_fieldnames.add((f or "").strip())

#             for fieldname in all_fieldnames:
#                 if not fieldname or fieldname in values:
#                     continue

#                 df = lead_detail_meta.get_field(fieldname)
#                 if not df:
#                     continue

#                 if df.fieldtype == "Table":
#                     child_doctype = df.options
#                     if not child_doctype:
#                         continue

#                     child_meta = frappe.get_meta(child_doctype)
#                     skip_fieldtypes = {
#                         "Section Break",
#                         "Column Break",
#                         "Tab Break",
#                         "HTML",
#                         "Button",
#                         "Fold",
#                         "Heading",
#                         "Read Only",
#                         "Attach",
#                         "Attach Image",
#                     }
#                     col_fieldnames = [
#                         cf.fieldname
#                         for cf in child_meta.fields
#                         if cf.fieldtype not in skip_fieldtypes
#                         and cf.fieldname
#                         not in (
#                             "name",
#                             "parent",
#                             "parenttype",
#                             "parentfield",
#                             "idx",
#                             "owner",
#                             "modified_by",
#                             "creation",
#                             "modified",
#                             "docstatus",
#                         )
#                     ]

#                     rows = frappe.db.get_all(
#                         child_doctype,
#                         filters={
#                             "parent": lead_detail_name,
#                             "parenttype": "Lead Detail Form",
#                         },
#                         fields=col_fieldnames + ["name"],
#                         order_by="idx asc",
#                     )
#                     values[fieldname] = rows

#     except Exception as e:
#         frappe.log_error(str(e), "get_lead_detail_field_values dynamic fetch")

#     # ── Also fetch hardcoded table fields ──
#     for fieldname, config in UPDATABLE_TABLE_FIELDS.items():
#         if fieldname not in values:
#             rows = frappe.db.get_all(
#                 config["doctype"],
#                 filters={
#                     "parent": lead_detail_name,
#                     "parenttype": "Lead Detail Form",
#                 },
#                 fields=list(config["columns"].keys()) + ["name"],
#                 order_by="idx asc",
#             )
#             values[fieldname] = rows

#     return values


@frappe.whitelist()
def get_lead_detail_field_values(customer_name):
    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")
    if not lead_detail_name:
        return {}

    # Get ALL updatable fields dynamically from ERP Configuration
    try:
        dept_access_raw = frappe.db.get_single_value(
            "ERP Configuration", "department_access_form_fields"
        )
        if dept_access_raw:
            dept_access = json.loads(dept_access_raw)

            # Get current user's allowed fields
            user = frappe.session.user
            employee = get_employee_name(user)
            allowed_fieldnames = []

            if employee:
                assignment_rows = frappe.db.get_all(
                    "Employee Assignment Detail",
                    filters={"parent": employee},
                    fields=["department", "designation"],
                )

                dept_access_normalized = {
                    k.lower().strip(): v for k, v in dept_access.items()
                }

                for row in assignment_rows:
                    designation = (row.get("designation") or "").lower().strip()
                    department = (row.get("department") or "").lower().strip()

                    # Check designation first
                    if designation and designation in dept_access_normalized:
                        allowed_fieldnames = dept_access_normalized[designation]
                        break

                    # Check department
                    if department and department in dept_access_normalized:
                        allowed_fieldnames = dept_access_normalized[department]
                        break

            # Also check customer owner fields
            customer_owner_fields = dept_access_normalized.get("customer", [])
            allowed_fieldnames.extend(customer_owner_fields)
            allowed_fieldnames = list(
                set([f.strip() for f in allowed_fieldnames if f.strip()])
            )
    except Exception:
        allowed_fieldnames = []

    # Get Lead Detail Form meta
    try:
        lead_detail_meta = frappe.get_meta("Lead Detail Form")
    except Exception:
        return {}

    # Fetch simple field values
    simple_field_values = (
        frappe.db.get_value(
            "Lead Detail Form",
            lead_detail_name,
            [f for f in allowed_fieldnames if f],
            as_dict=True,
        )
        or {}
    )

    values = {**simple_field_values}

    # Fetch table field values dynamically
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

    for fieldname in allowed_fieldnames:
        fieldname = fieldname.strip()
        if not fieldname or fieldname in values:
            continue

        df = lead_detail_meta.get_field(fieldname)
        if not df:
            continue

        if df.fieldtype == "Table":
            child_doctype = df.options
            if not child_doctype:
                continue

            try:
                child_meta = frappe.get_meta(child_doctype)
                col_fieldnames = [
                    cf.fieldname
                    for cf in child_meta.fields
                    if (
                        cf.fieldtype not in skip_fieldtypes
                        and cf.fieldname not in system_fields
                        and cf.fieldname
                    )
                ]

                rows = frappe.db.get_all(
                    child_doctype,
                    filters={
                        "parent": lead_detail_name,
                        "parenttype": "Lead Detail Form",
                    },
                    fields=col_fieldnames,
                    order_by="idx asc",
                )
                values[fieldname] = rows
            except Exception:
                continue

    return values


@frappe.whitelist()
def request_field_update_by_owner(customer_name, reason, field_updates):
    user = frappe.session.user

    try:
        employee = get_employee_name(user)
    except Exception:
        employee = None

    if not employee:
        frappe.throw("No Employee record found for the current user.")

    # Verify logged-in user is actually the customer_owner
    customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
    if customer_owner != employee:
        frappe.throw("Only the customer owner can send this request.")

    manager_employee = get_approver_by_department(employee)
    if not manager_employee:
        frappe.throw("No suitable approver found in your hierarchy.")

    manager_user = get_user(manager_employee)
    if not manager_user:
        frappe.throw("Approver employee has no linked User account.")

    if isinstance(field_updates, str):
        field_updates = json.loads(field_updates)

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

    send_notification(
        recipients=[manager_email],
        subject=f"Field Update Request for Customer {customer_name}",
        message=(
            f"Employee <b>{employee}</b> has requested to update fields "
            f"on Customer <b>{customer_name}</b>.<br><br>"
            f"<b>Reason:</b> {reason}<br><br>"
            f"Please open Customer <b>{customer_name}</b> and click "
            f"<b>Accept Updates</b> to review."
        ),
        reference_doctype="Customer",
        reference_name=customer_name,
        send_email=1,
        send_system=1,
    )

    return {
        "status": "success",
        "manager_employee": manager_employee,
    }


@frappe.whitelist()
def get_candidate_form_required_status(customer_name):
    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")
    if not lead_detail_name:
        return {"required": False}

    so_name = frappe.db.get_value("Lead Detail Form", lead_detail_name, "sales_order")
    if not so_name:
        return {"required": False}

    required = check_candidate_form_required_from_sales_order(so_name)
    return {"required": required}


@frappe.whitelist()
def get_owner_pending_field_update_request(customer_name):
    user = frappe.session.user

    try:
        employee = get_employee_name(user)
    except Exception:
        employee = None

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
                if child_df.fieldtype in skip_fieldtypes:
                    continue
                if child_df.fieldname in system_fields:
                    continue
                columns[child_df.fieldname] = (
                    child_df.label or child_df.fieldname.replace("_", " ").title()
                )

            if columns:
                table_fields[fieldname] = {
                    "label": df.label or fieldname.replace("_", " ").title(),
                    "doctype": child_doctype,
                    "columns": columns,
                }
        else:
            simple_fields[fieldname] = df.label or fieldname.replace("_", " ").title()

    return {"simple_fields": simple_fields, "table_fields": table_fields}


# ─────────────────────────────────────────────
# HELPER: get normalized dept access config
# ─────────────────────────────────────────────


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


@frappe.whitelist()
def get_department_updatable_fields():
    """
    Returns simple_fields and table_fields for the logged-in employee
    based on their designation/department matching keys in
    ERP Configuration → department_access_form_fields.
    """
    user = frappe.session.user
    employee = get_employee_name(user)

    if not employee:
        return {"simple_fields": {}, "table_fields": {}}

    assignment_rows = frappe.db.get_all(
        "Employee Assignment Detail",
        filters={"parent": employee},
        fields=["department", "designation"],
    )

    if not assignment_rows:
        return {"simple_fields": {}, "table_fields": {}}

    dept_access_normalized = _get_dept_access_config()
    if not dept_access_normalized:
        return {"simple_fields": {}, "table_fields": {}}

    allowed_fieldnames = []

    for row in assignment_rows:
        designation = (row.get("designation") or "").lower().strip()
        department = (row.get("department") or "").lower().strip()

        # 1. Exact designation match
        if designation and designation in dept_access_normalized:
            allowed_fieldnames = dept_access_normalized[designation]
            break

        # 2. Partial designation match
        if designation:
            for config_key, config_fields in dept_access_normalized.items():
                if config_key in designation or designation in config_key:
                    allowed_fieldnames = config_fields
                    break

        if allowed_fieldnames:
            break

        # 3. Exact department match
        if department and department in dept_access_normalized:
            allowed_fieldnames = dept_access_normalized[department]
            break

        # 4. Partial department match
        if department:
            for config_key, config_fields in dept_access_normalized.items():
                if config_key in department or department in config_key:
                    allowed_fieldnames = config_fields
                    break

        if allowed_fieldnames:
            break

    if not allowed_fieldnames:
        frappe.log_error(
            f"No match for employee {employee}. "
            f"Rows: {[(r.get('designation',''), r.get('department','')) for r in assignment_rows]}. "
            f"Config keys: {list(dept_access_normalized.keys())}",
            "dept_fields_no_match",
        )
        return {"simple_fields": {}, "table_fields": {}}

    return _build_fields_from_fieldnames(allowed_fieldnames)


@frappe.whitelist()
def get_customer_owner_updatable_fields():
    """
    Returns simple_fields and table_fields for the customer owner
    using the 'customer' key in ERP Configuration → department_access_form_fields.
    """
    dept_access_normalized = _get_dept_access_config()
    allowed_fieldnames = dept_access_normalized.get("customer", [])

    if not allowed_fieldnames:
        return {"simple_fields": {}, "table_fields": {}}

    return _build_fields_from_fieldnames(allowed_fieldnames)
