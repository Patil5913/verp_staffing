# # Copyright (c) 2025, Vrugle and contributors
# # For license information, please see license.txt

# import frappe
# import json
# from datetime import datetime, timedelta, timezone

# from verp_staffing.crm.api.helpers import (
#     get_employee_name,
#     get_user,
#     get_all_subordinates,
#     send_system_notification,
#     send_notification,
# )

# PERMISSION_EXPIRY_MINUTES = 1


# def get_manager_of_employee(employee_name):
#     result = frappe.db.get_value(
#         "Employee Assignment Detail",
#         filters={"parent": employee_name},
#         fieldname="assigned_to",
#     )
#     return result or None


# def is_permission_expired(granted_at_str):
#     if not granted_at_str:
#         return True
#     try:
#         granted_at = datetime.fromisoformat(granted_at_str)

#         # If granted_at has no timezone info, treat as UTC
#         if granted_at.tzinfo is None:
#             granted_at = granted_at.replace(tzinfo=timezone.utc)

#         expiry_time = granted_at + timedelta(minutes=PERMISSION_EXPIRY_MINUTES)
#         now_utc = datetime.now(timezone.utc)

#         return now_utc > expiry_time
#     except Exception:
#         return True


# @frappe.whitelist()
# def _decline_permission(ref_doctype, ref_name):
#     user = frappe.session.user
#     manager_employee = get_employee_name(user)

#     if not manager_employee:
#         frappe.throw("No Employee record found for the current manager user.")

#     # Get owner to notify them
#     owner_field = "lead_owner" if ref_doctype == "Lead" else "customer_owner"
#     owner_employee = frappe.db.get_value(ref_doctype, ref_name, owner_field)
#     owner_user = get_user(owner_employee)

#     comments = frappe.get_all(
#         "Comment",
#         filters={
#             "reference_doctype": ref_doctype,
#             "reference_name": ref_name,
#             "comment_type": "Info",
#         },
#         fields=["name", "content"],
#         order_by="creation desc",
#     )

#     declined_comment = None
#     for c in comments:
#         try:
#             data = json.loads(c.content)
#             if (
#                 data.get("type") == "update_permission_request"
#                 and data.get("status") == "Pending"
#             ):
#                 data["status"] = "Declined"
#                 data["declined_by"] = manager_employee
#                 data["declined_at"] = datetime.now().isoformat()
#                 frappe.db.set_value("Comment", c.name, "content", json.dumps(data))
#                 frappe.db.commit()
#                 declined_comment = c.name
#                 break
#         except Exception:
#             continue

#     if not declined_comment:
#         frappe.throw("No pending permission request found.")

#     # Notify the owner
#     if owner_user:
#         send_system_notification(
#             user=owner_user,
#             subject=f"Permission Request Declined for {ref_doctype} {ref_name}",
#             message=(
#                 f"Your manager <b>{manager_employee}</b> has declined your request "
#                 f"to update fields on {ref_doctype} <b>{ref_name}</b>.<br><br>"
#                 f"You may submit a new request with a different reason if needed."
#             ),
#             reference_doctype=ref_doctype,
#             reference_name=ref_name,
#         )

#     return {
#         "status": "declined",
#         "ref_name": ref_name,
#         "declined_by": manager_employee,
#     }


# # @frappe.whitelist()
# # def _request_permission(ref_doctype, ref_name, reason):
# #     user = frappe.session.user
# #     employee = get_employee_name(user)
# #     if not employee:
# #         frappe.throw("No Employee record found for the current user.")

# #     manager_employee = get_manager_of_employee(employee)
# #     if not manager_employee:
# #         frappe.throw("No manager found in the hierarchy for your Employee record.")

# #     manager_user = get_user(manager_employee)
# #     if not manager_user:
# #         frappe.throw("Manager employee has no linked User account.")

# #     comment = frappe.get_doc(
# #         {
# #             "doctype": "Comment",
# #             "comment_type": "Info",
# #             "reference_doctype": ref_doctype,
# #             "reference_name": ref_name,
# #             "content": json.dumps(
# #                 {
# #                     "type": "update_permission_request",
# #                     "reason": reason,
# #                     "requested_by_employee": employee,
# #                     "requested_by_user": user,
# #                     "status": "Pending",
# #                     "granted_at": None,
# #                 }
# #             ),
# #             "comment_by": user,
# #         }
# #     )
# #     comment.insert(ignore_permissions=True)

# #     manager_email = frappe.db.get_value("User", manager_user, "email")

# #     send_notification(
# #         recipients=[manager_email],
# #         subject=f"Update Permission Request for Lead {ref_name}",
# #         message=(
# #             f"Employee <b>{employee}</b> has requested permission to update "
# #             f"the email field on Lead <b>{ref_name}</b>.<br><br>"
# #             f"<b>Reason:</b> {reason}<br><br>"
# #             f"Please open Lead <b>{ref_name}</b> and click "
# #             f"<b>Give Permission</b> to approve."
# #         ),
# #         reference_doctype="Lead",
# #         reference_name=ref_name,
# #         send_email=1,
# #         send_system=1,
# #     )

# #     return {
# #         "status": "success",
# #         "comment_name": comment.name,
# #         "manager_employee": manager_employee,
# #         "manager_user": manager_user,
# #     }


# @frappe.whitelist()
# def _request_permission(ref_doctype, ref_name, reason):
#     user = frappe.session.user
#     employee = get_employee_name(user)
#     if not employee:
#         frappe.throw("No Employee record found for the current user.")

#     # ── Find correct manager based on doctype ──
#     if ref_doctype == "Customer":
#         # Request goes to manager of customer_owner, not service person's manager
#         customer_owner = frappe.db.get_value("Customer", ref_name, "customer_owner")
#         if not customer_owner:
#             frappe.throw("No customer owner found for this Customer.")
#         manager_employee = get_manager_of_employee(customer_owner)
#     else:
#         # Lead — goes to lead owner's manager (original flow)
#         manager_employee = get_manager_of_employee(employee)

#     if not manager_employee:
#         frappe.throw("No manager found in the hierarchy.")

#     manager_user = get_user(manager_employee)
#     if not manager_user:
#         frappe.throw("Manager employee has no linked User account.")

#     comment = frappe.get_doc(
#         {
#             "doctype": "Comment",
#             "comment_type": "Info",
#             "reference_doctype": ref_doctype,
#             "reference_name": ref_name,
#             "content": json.dumps(
#                 {
#                     "type": "update_permission_request",
#                     "reason": reason,
#                     "requested_by_employee": employee,
#                     "requested_by_user": user,
#                     "status": "Pending",
#                     "granted_at": None,
#                 }
#             ),
#             "comment_by": user,
#         }
#     )
#     comment.insert(ignore_permissions=True)

#     manager_email = frappe.db.get_value("User", manager_user, "email")

#     send_notification(
#         recipients=[manager_email],
#         subject=f"Update Permission Request for {ref_doctype} {ref_name}",
#         message=(
#             f"Employee <b>{employee}</b> has requested permission to update "
#             f"fields on {ref_doctype} <b>{ref_name}</b>.<br><br>"
#             f"<b>Reason:</b> {reason}<br><br>"
#             f"Please open Customer <b>{ref_name}</b> and click "
#             f"<b>Give Permission</b> to approve."
#         ),
#         reference_doctype=ref_doctype,
#         reference_name=ref_name,
#         send_email=1,
#         send_system=1,
#     )

#     return {
#         "status": "success",
#         "comment_name": comment.name,
#         "manager_employee": manager_employee,
#         "manager_user": manager_user,
#     }


# @frappe.whitelist()
# def _give_permission(ref_doctype, ref_name):
#     user = frappe.session.user
#     manager_employee = get_employee_name(user)
#     if not manager_employee:
#         frappe.throw("No Employee record found for the current manager user.")

#     # Get owner field based on doctype
#     owner_field = "lead_owner" if ref_doctype == "Lead" else "customer_owner"
#     owner_employee = frappe.db.get_value(ref_doctype, ref_name, owner_field)
#     owner_user = get_user(owner_employee)

#     comments = frappe.get_all(
#         "Comment",
#         filters={
#             "reference_doctype": ref_doctype,
#             "reference_name": ref_name,
#             "comment_type": "Info",
#         },
#         fields=["name", "content"],
#         order_by="creation desc",
#     )

#     approved_comment = None
#     for c in comments:
#         try:
#             data = json.loads(c.content)
#             if (
#                 data.get("type") == "update_permission_request"
#                 and data.get("status") == "Pending"
#             ):
#                 data["status"] = "Approved"
#                 data["approved_by"] = manager_employee
#                 data["granted_at"] = datetime.now(timezone.utc).isoformat()
#                 frappe.db.set_value("Comment", c.name, "content", json.dumps(data))
#                 frappe.db.commit()
#                 approved_comment = c.name
#                 break
#         except Exception:
#             continue

#     if not approved_comment:
#         frappe.throw("No pending permission request found.")

#     owner_email = frappe.db.get_value("User", owner_user, "email")

#     if owner_user:
#         send_notification(
#             recipients=[owner_email],
#             subject=f"Permission Granted for Lead {ref_name}",
#             message=(
#                 f"Your manager <b>{manager_employee}</b> has granted you permission "
#                 f"to update the email field on Lead <b>{ref_name}</b>.<br><br>"
#                 f"<b>Note:</b> This permission is valid for "
#                 f"<b>{PERMISSION_EXPIRY_MINUTES} minutes</b> only.<br><br>"
#                 f"Please open the Lead Detail Form to make your changes."
#             ),
#             reference_doctype=ref_doctype,
#             reference_name=ref_name,
#             send_email=1,
#             send_system=1,
#         )

#     return {
#         "status": "approved",
#         "ref_name": ref_name,
#         "expires_in_minutes": PERMISSION_EXPIRY_MINUTES,
#     }


# @frappe.whitelist()
# def _check_permission_status(ref_doctype, ref_name):
#     user = frappe.session.user
#     employee = get_employee_name(user)

#     if not employee:
#         return {"status": "none"}

#     comments = frappe.get_all(
#         "Comment",
#         filters={
#             "reference_doctype": ref_doctype,
#             "reference_name": ref_name,
#             "comment_type": "Info",
#         },
#         fields=["name", "content"],
#         order_by="creation desc",
#     )

#     for c in comments:
#         try:
#             data = json.loads(c.content)
#             requested_by = data.get("requested_by_employee")

#             if (
#                 data.get("type") == "update_permission_request"
#                 and data.get("requested_by_employee") == employee
#             ):
#                 raw_status = data.get("status", "Pending")

#                 if raw_status == "Approved":
#                     granted_at = data.get("granted_at")

#                     if is_permission_expired(granted_at):
#                         data["status"] = "Expired"
#                         frappe.db.set_value(
#                             "Comment", c.name, "content", json.dumps(data)
#                         )
#                         frappe.db.commit()
#                         return {"status": "expired"}

#                     granted_dt = datetime.fromisoformat(granted_at)
#                     if granted_dt.tzinfo is None:
#                         granted_dt = granted_dt.replace(tzinfo=timezone.utc)
#                     expiry_dt = granted_dt + timedelta(
#                         minutes=PERMISSION_EXPIRY_MINUTES
#                     )
#                     remaining_seconds = int(
#                         (expiry_dt - datetime.now(timezone.utc)).total_seconds()
#                     )

#                     return {
#                         "status": "approved",
#                         "remaining_seconds": max(remaining_seconds, 0),
#                     }

#                 if raw_status == "Declined":
#                     return {"status": "declined"}

#                 return {"status": raw_status.lower()}

#         except Exception as e:

#             continue

#     return {"status": "none"}


# @frappe.whitelist()
# def _check_pending_for_manager(ref_doctype, ref_name):
#     user = frappe.session.user
#     manager_employee = get_employee_name(user)
#     if not manager_employee:
#         return {"has_pending": False}

#     subordinates = get_all_subordinates(manager_employee)
#     if not subordinates:
#         return {"has_pending": False}

#     comments = frappe.get_all(
#         "Comment",
#         filters={
#             "reference_doctype": ref_doctype,
#             "reference_name": ref_name,
#             "comment_type": "Info",
#         },
#         fields=["name", "content"],
#         order_by="creation desc",
#     )

#     for c in comments:
#         try:
#             data = json.loads(c.content)
#             if (
#                 data.get("type") == "update_permission_request"
#                 and data.get("status") == "Pending"
#             ):
#                 requester = data.get("requested_by_employee")
#                 if requester in subordinates:
#                     return {
#                         "has_pending": True,
#                         "requested_by": requester,
#                         "reason": data.get("reason"),
#                         "comment_name": c.name,
#                         "expires_in_minutes": PERMISSION_EXPIRY_MINUTES,
#                     }
#                 return {"has_pending": False}
#         except Exception:
#             continue

#     return {"has_pending": False}


# @frappe.whitelist()
# def get_lead_detail_form_lock_status(customer_name=None, lead_detail_name=None):
#     user = frappe.session.user

#     try:
#         employee = get_employee_name(user)
#     except Exception:
#         employee = None

#     if not employee:
#         return {
#             "is_owner": False,
#             "candidate_form_required": False,
#             "permission": "none",
#         }

#     # If called with lead_detail_name, find customer from it
#     if lead_detail_name and not customer_name:
#         customer_name = frappe.db.get_value(
#             "Customer", {"lead_details": lead_detail_name}, "name"
#         )

#     if not customer_name:
#         return {
#             "is_owner": False,
#             "candidate_form_required": False,
#             "permission": "none",
#         }

#     customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
#     is_customer_owner = employee == customer_owner

#     # Check if employee is lead_owner of linked Lead
#     lead_owner_match = False
#     lead_detail_doc = frappe.db.get_value("Customer", customer_name, "lead_details")

#     if lead_detail_doc:
#         lead_ref = frappe.db.get_value(
#             "Doctype Reference",
#             {
#                 "parent": lead_detail_doc,
#                 "parenttype": "Lead Detail Form",
#                 "reference_doctype": "Lead",
#             },
#             "reference_person",
#         )
#         if lead_ref:
#             lead_owner = frappe.db.get_value("Lead", lead_ref, "lead_owner")
#             if lead_owner == employee:
#                 lead_owner_match = True

#     # Check if employee is assign_to on ANY service doctype for this customer
#     service_doctypes = [
#         "Resume",
#         "RUC",
#         "JDC",
#         "Training",
#         "Cover Letter",
#         "Marketing",
#         "Technical Other Services",
#         "Marketing Other Services",
#     ]
#     is_service_assignee = False

#     for doctype in service_doctypes:
#         try:
#             exists = frappe.db.exists(
#                 doctype,
#                 {
#                     "customer": customer_name,
#                     "assign_to": employee,
#                 },
#             )
#             if exists:
#                 is_service_assignee = True
#                 break
#         except Exception:
#             continue

#     is_owner = is_customer_owner or lead_owner_match or is_service_assignee

#     # Check candidate form required
#     resolved_lead_detail = frappe.db.get_value(
#         "Customer", customer_name, "lead_details"
#     )
#     candidate_form_required = False

#     if resolved_lead_detail:
#         so_name = frappe.db.get_value(
#             "Lead Detail Form", resolved_lead_detail, "sales_order"
#         )

#         if so_name:
#             services = frappe.db.get_all(
#                 "SalesOrderServices",
#                 filters={"parent": so_name, "parenttype": "Sales Order"},
#                 fields=["service"],
#                 ignore_permissions=True,
#             )
#             service_names = [s.service for s in services if s.service]

#             if service_names:
#                 requires = frappe.db.exists(
#                     "Service",
#                     {
#                         "name": ["in", service_names],
#                         "is_candidate_form_required": 1,
#                     },
#                 )
#                 candidate_form_required = bool(requires)

#     perm_status = "none"
#     if is_owner and candidate_form_required:
#         # ── Check permission specifically for this employee ──
#         # First check if THIS employee's own request was approved
#         perm = _check_permission_status("Customer", customer_name)
#         perm_status = perm.get("status", "none")

#         # If this employee has no request of their own,
#         # check if they are customer_owner or lead_owner
#         # and if any approved permission exists (for them to unlock)
#         if perm_status == "none" and (is_customer_owner or lead_owner_match):
#             any_perm = check_any_approved_permission(customer_name)
#             perm_status = any_perm.get("status", "none")

#     return {
#         "is_owner": is_owner,
#         "candidate_form_required": candidate_form_required,
#         "permission": perm_status,
#         "customer_name": customer_name,
#     }


# @frappe.whitelist()
# def get_service_form_permission_status(
#     customer_name, service_doctype=None, service_name=None
# ):
#     """
#     Called from service doctypes (Resume, RUC, JDC etc).
#     Checks if logged-in user is:
#     1. The customer_owner on Customer, OR
#     2. The assign_to on the service document
#     """
#     user = frappe.session.user

#     try:
#         employee = get_employee_name(user)
#     except Exception:
#         employee = None

#     if not employee:
#         return {"is_owner": False, "permission": "none"}

#     customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
#     is_customer_owner = employee == customer_owner

#     # Also check if logged-in user is the assign_to on the service doc
#     is_assignee = False
#     if service_doctype and service_name:
#         assign_to = frappe.db.get_value(service_doctype, service_name, "assign_to")
#         is_assignee = employee == assign_to

#     is_owner = is_customer_owner or is_assignee

#     perm_status = "none"
#     if is_owner:
#         # Check permission by the logged-in employee specifically
#         perm = _check_permission_status("Customer", customer_name)
#         perm_status = perm.get("status", "none")

#         # If no permission found for this user, check if any approved exists
#         if perm_status == "none":
#             any_perm = check_any_approved_permission(customer_name)
#             if any_perm.get("status") == "approved":
#                 perm_status = "approved"

#     return {
#         "is_owner": is_owner,
#         "permission": perm_status,
#     }


# @frappe.whitelist()
# def check_pending_requests_for_customer_manager(customer_name):
#     """
#     For service doctypes — checks if there is any pending request on this Customer
#     and if the logged-in user is the manager of the customer_owner.
#     """
#     user = frappe.session.user

#     try:
#         manager_employee = get_employee_name(user)
#     except Exception:
#         manager_employee = None

#     if not manager_employee:
#         return {"has_pending": False}

#     # Get customer_owner
#     customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
#     if not customer_owner:
#         return {"has_pending": False}

#     # Check if logged-in user is the manager of customer_owner
#     manager_of_owner = get_manager_of_employee(customer_owner)
#     if manager_of_owner != manager_employee:
#         return {"has_pending": False}

#     # Find any pending request on this Customer
#     comments = frappe.get_all(
#         "Comment",
#         filters={
#             "reference_doctype": "Customer",
#             "reference_name": customer_name,
#             "comment_type": "Info",
#         },
#         fields=["name", "content"],
#         order_by="creation desc",
#     )

#     for c in comments:
#         try:
#             data = json.loads(c.content)
#             if (
#                 data.get("type") == "update_permission_request"
#                 and data.get("status") == "Pending"
#             ):
#                 return {
#                     "has_pending": True,
#                     "requested_by": data.get("requested_by_employee"),
#                     "reason": data.get("reason"),
#                     "comment_name": c.name,
#                     "expires_in_minutes": PERMISSION_EXPIRY_MINUTES,
#                 }
#         except Exception:
#             continue

#     return {"has_pending": False}


# @frappe.whitelist()
# def check_any_approved_permission(customer_name):
#     """
#     Returns approved status if ANY comment on this Customer
#     has status Approved and is not expired.
#     Used when resume person requests but customer owner needs unlock.
#     """
#     comments = frappe.get_all(
#         "Comment",
#         filters={
#             "reference_doctype": "Customer",
#             "reference_name": customer_name,
#             "comment_type": "Info",
#         },
#         fields=["name", "content"],
#         order_by="creation desc",
#     )

#     for c in comments:
#         try:
#             data = json.loads(c.content)
#             if data.get("type") == "update_permission_request":
#                 raw_status = data.get("status", "Pending")

#                 if raw_status == "Approved":
#                     granted_at = data.get("granted_at")
#                     if is_permission_expired(granted_at):
#                         data["status"] = "Expired"
#                         frappe.db.set_value(
#                             "Comment", c.name, "content", json.dumps(data)
#                         )
#                         frappe.db.commit()
#                         continue  # check next comment

#                     granted_dt = datetime.fromisoformat(granted_at)
#                     if granted_dt.tzinfo is None:
#                         granted_dt = granted_dt.replace(tzinfo=timezone.utc)
#                     expiry_dt = granted_dt + timedelta(
#                         minutes=PERMISSION_EXPIRY_MINUTES
#                     )
#                     remaining_seconds = int(
#                         (expiry_dt - datetime.now(timezone.utc)).total_seconds()
#                     )

#                     return {
#                         "status": "approved",
#                         "remaining_seconds": max(remaining_seconds, 0),
#                     }

#         except Exception:
#             continue

#     return {"status": "none"}


# UPDATABLE_FIELDS = {
#     "surname": "Surname",
#     "first_name": "First Name",
#     "father_name": "Father Name",
#     "email": "Email",
# }


# @frappe.whitelist()
# def request_field_update(customer_name, reason, field_updates):
#     """
#     Called when service person clicks Send in Update Detail dialog.
#     field_updates is a JSON string: {"surname": {"old": "x", "new": "y"}, ...}
#     """
#     user = frappe.session.user

#     try:
#         employee = get_employee_name(user)
#     except Exception:
#         employee = None

#     if not employee:
#         frappe.throw("No Employee record found for the current user.")

#     manager_employee = get_manager_of_employee(employee)
#     if not manager_employee:
#         frappe.throw("No manager found in the hierarchy for your Employee record.")

#     manager_user = get_user(manager_employee)
#     if not manager_user:
#         frappe.throw("Manager employee has no linked User account.")

#     if isinstance(field_updates, str):
#         field_updates = json.loads(field_updates)

#     comment = frappe.get_doc(
#         {
#             "doctype": "Comment",
#             "comment_type": "Info",
#             "reference_doctype": "Customer",
#             "reference_name": customer_name,
#             "content": json.dumps(
#                 {
#                     "type": "field_update_request",
#                     "reason": reason,
#                     "requested_by_employee": employee,
#                     "requested_by_user": user,
#                     "status": "Pending",
#                     "field_updates": field_updates,
#                     "requested_at": datetime.now(timezone.utc).isoformat(),
#                 }
#             ),
#             "comment_by": user,
#         }
#     )
#     comment.insert(ignore_permissions=True)

#     manager_email = frappe.db.get_value("User", manager_user, "email")

#     send_notification(
#         recipients=[manager_email],
#         subject=f"Field Update Request for Customer {customer_name}",
#         message=(
#             f"Employee <b>{employee}</b> has requested to update fields "
#             f"on Customer <b>{customer_name}</b>.<br><br>"
#             f"<b>Reason:</b> {reason}<br><br>"
#             f"Please open the service form and click <b>Accept Updates</b> to review."
#         ),
#         reference_doctype="Customer",
#         reference_name=customer_name,
#         send_email=1,
#         send_system=1,
#     )

#     return {
#         "status": "success",
#         "manager_employee": manager_employee,
#     }


# @frappe.whitelist()
# def get_pending_field_update_request(customer_name):
#     """
#     Called for manager to check if there is a pending field update request.
#     Returns the pending request with field_updates data.
#     """
#     user = frappe.session.user

#     try:
#         manager_employee = get_employee_name(user)
#     except Exception:
#         manager_employee = None

#     if not manager_employee:
#         return {"has_pending": False}

#     customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
#     if not customer_owner:
#         return {"has_pending": False}

#     manager_of_owner = get_manager_of_employee(customer_owner)
#     if manager_of_owner != manager_employee:
#         return {"has_pending": False}

#     comments = frappe.get_all(
#         "Comment",
#         filters={
#             "reference_doctype": "Customer",
#             "reference_name": customer_name,
#             "comment_type": "Info",
#         },
#         fields=["name", "content"],
#         order_by="creation desc",
#     )

#     for c in comments:
#         try:
#             data = json.loads(c.content)
#             if (
#                 data.get("type") == "field_update_request"
#                 and data.get("status") == "Pending"
#             ):
#                 return {
#                     "has_pending": True,
#                     "comment_name": c.name,
#                     "requested_by": data.get("requested_by_employee"),
#                     "reason": data.get("reason"),
#                     "field_updates": data.get("field_updates", {}),
#                 }
#         except Exception:
#             continue

#     return {"has_pending": False}


# @frappe.whitelist()
# def apply_field_updates(customer_name, comment_name, approved_fields):
#     """
#     Called when manager clicks Done.
#     approved_fields: list of field names that were checked/approved.
#     Updates those fields in Lead Detail Form.
#     """
#     user = frappe.session.user

#     try:
#         manager_employee = get_employee_name(user)
#     except Exception:
#         manager_employee = None

#     if not manager_employee:
#         frappe.throw("No Employee record found.")

#     if isinstance(approved_fields, str):
#         approved_fields = json.loads(approved_fields)

#     # Get the comment
#     comment_doc = frappe.get_doc("Comment", comment_name)
#     data = json.loads(comment_doc.content)

#     if data.get("status") != "Pending":
#         frappe.throw("This request has already been processed.")

#     field_updates = data.get("field_updates", {})

#     # Find Lead Detail Form linked to this Customer
#     lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")

#     if not lead_detail_name:
#         frappe.throw("No Lead Detail Form found for this Customer.")

#     # Apply only approved fields
#     updated_fields = {}
#     for field in approved_fields:
#         if field in field_updates and field in UPDATABLE_FIELDS:
#             new_value = field_updates[field].get("new")
#             frappe.db.set_value(
#                 "Lead Detail Form",
#                 lead_detail_name,
#                 field,
#                 new_value,
#             )
#             updated_fields[field] = new_value

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
#             field_names = ", ".join(UPDATABLE_FIELDS.get(f, f) for f in approved_fields)
#             send_notification(
#                 recipients=[requester_email],
#                 subject=f"Field Updates Approved for Customer {customer_name}",
#                 message=(
#                     f"Your manager <b>{manager_employee}</b> has approved updates "
#                     f"for the following fields: <b>{field_names}</b>.<br><br>"
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


# @frappe.whitelist()
# def get_lead_detail_field_values(customer_name):
#     """
#     Returns current values of updatable fields from Lead Detail Form.
#     Used to show old values in the Update Detail dialog.
#     """
#     lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")

#     if not lead_detail_name:
#         return {}

#     values = frappe.db.get_value(
#         "Lead Detail Form",
#         lead_detail_name,
#         list(UPDATABLE_FIELDS.keys()),
#         as_dict=True,
#     )

#     return values or {}


# @frappe.whitelist()
# def get_all_pending_field_update_requests(customer_name):
#     """
#     Returns ALL pending field update requests on this Customer.
#     Used on Customer form for manager to see all pending requests together.
#     """
#     user = frappe.session.user

#     try:
#         manager_employee = get_employee_name(user)
#     except Exception:
#         manager_employee = None

#     if not manager_employee:
#         return []

#     # Verify logged-in user is manager of customer_owner
#     customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
#     if not customer_owner:
#         return []

#     manager_of_owner = get_manager_of_employee(customer_owner)
#     if manager_of_owner != manager_employee:
#         return []

#     comments = frappe.get_all(
#         "Comment",
#         filters={
#             "reference_doctype": "Customer",
#             "reference_name": customer_name,
#             "comment_type": "Info",
#         },
#         fields=["name", "content"],
#         order_by="creation desc",
#     )

#     pending = []
#     for c in comments:
#         try:
#             data = json.loads(c.content)
#             if (
#                 data.get("type") == "field_update_request"
#                 and data.get("status") == "Pending"
#             ):
#                 pending.append(
#                     {
#                         "comment_name": c.name,
#                         "requested_by": data.get("requested_by_employee"),
#                         "reason": data.get("reason"),
#                         "field_updates": data.get("field_updates", {}),
#                     }
#                 )
#         except Exception:
#             continue

#     return pending


# @frappe.whitelist()
# def request_field_update(customer_name, reason, field_updates):
#     user = frappe.session.user

#     try:
#         employee = get_employee_name(user)
#     except Exception:
#         employee = None

#     if not employee:
#         frappe.throw("No Employee record found for the current user.")

#     # ── Goes to manager of customer_owner, not service person's manager ──
#     customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
#     if not customer_owner:
#         frappe.throw("No customer owner found for this Customer.")

#     manager_employee = get_manager_of_employee(customer_owner)
#     if not manager_employee:
#         frappe.throw("No manager found for the customer owner.")

#     manager_user = get_user(manager_employee)
#     if not manager_user:
#         frappe.throw("Manager employee has no linked User account.")

#     if isinstance(field_updates, str):
#         field_updates = json.loads(field_updates)

#     comment = frappe.get_doc(
#         {
#             "doctype": "Comment",
#             "comment_type": "Info",
#             "reference_doctype": "Customer",
#             "reference_name": customer_name,
#             "content": json.dumps(
#                 {
#                     "type": "field_update_request",
#                     "reason": reason,
#                     "requested_by_employee": employee,
#                     "requested_by_user": user,
#                     "status": "Pending",
#                     "field_updates": field_updates,
#                     "requested_at": datetime.now(timezone.utc).isoformat(),
#                 }
#             ),
#             "comment_by": user,
#         }
#     )
#     comment.insert(ignore_permissions=True)

#     manager_email = frappe.db.get_value("User", manager_user, "email")

#     send_notification(
#         recipients=[manager_email],
#         subject=f"Field Update Request for Customer {customer_name}",
#         message=(
#             f"Employee <b>{employee}</b> has requested to update fields "
#             f"on Customer <b>{customer_name}</b>.<br><br>"
#             f"<b>Reason:</b> {reason}<br><br>"
#             f"Please open Customer <b>{customer_name}</b> and click "
#             f"<b>Accept Updates</b> to review."
#         ),
#         reference_doctype="Customer",
#         reference_name=customer_name,
#         send_email=1,
#         send_system=1,
#     )

#     return {
#         "status": "success",
#         "manager_employee": manager_employee,
#     }


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
)

PERMISSION_EXPIRY_MINUTES = 30

UPDATABLE_FIELDS = {
    "surname": "Surname",
    "first_name": "First Name",
    "father_name": "Father Name",
    "email": "Email",
}


def get_manager_of_employee(employee_name):
    result = frappe.db.get_value(
        "Employee Assignment Detail",
        filters={"parent": employee_name},
        fieldname="assigned_to",
    )
    return result or None


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
    """
    Used for Lead email field locking flow only.
    Sends request to manager of lead_owner.
    """
    user = frappe.session.user
    employee = get_employee_name(user)
    if not employee:
        frappe.throw("No Employee record found for the current user.")

    if ref_doctype == "Customer":
        customer_owner = frappe.db.get_value("Customer", ref_name, "customer_owner")
        if not customer_owner:
            frappe.throw("No customer owner found for this Customer.")
        manager_employee = get_manager_of_employee(customer_owner)
    else:
        manager_employee = get_manager_of_employee(employee)

    if not manager_employee:
        frappe.throw("No manager found in the hierarchy.")

    manager_user = get_user(manager_employee)
    if not manager_user:
        frappe.throw("Manager employee has no linked User account.")

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
    """
    Used for Lead email field locking only.
    Checks permission status for the currently logged-in employee.
    """
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
    """
    Determines if Lead Detail Form should be locked/unlocked for logged-in user.
    Used in lead_detail_form.js.
    """
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

    # Check candidate form required via Sales Order
    resolved_lead_detail = frappe.db.get_value(
        "Customer", customer_name, "lead_details"
    )
    candidate_form_required = False

    if resolved_lead_detail:
        so_name = frappe.db.get_value(
            "Lead Detail Form", resolved_lead_detail, "sales_order"
        )

        if so_name:
            services = frappe.db.get_all(
                "SalesOrderServices",
                filters={"parent": so_name, "parenttype": "Sales Order"},
                fields=["service"],
                ignore_permissions=True,
            )
            service_names = [s.service for s in services if s.service]

            if service_names:
                requires = frappe.db.exists(
                    "Service",
                    {
                        "name": ["in", service_names],
                        "is_candidate_form_required": 1,
                    },
                )
                candidate_form_required = bool(requires)

    return {
        "is_owner": is_owner,
        "candidate_form_required": candidate_form_required,
        "permission": "none",
        "customer_name": customer_name,
    }


@frappe.whitelist()
def request_field_update(customer_name, reason, field_updates):
    """
    Called when service person clicks Send in Update Detail dialog.
    Request goes to manager of customer_owner.
    field_updates: {"surname": {"old": "x", "new": "y"}, ...}
    """
    user = frappe.session.user

    try:
        employee = get_employee_name(user)
    except Exception:
        employee = None

    if not employee:
        frappe.throw("No Employee record found for the current user.")

    # Goes to manager of customer_owner, not service person's manager
    customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
    if not customer_owner:
        frappe.throw("No customer owner found for this Customer.")

    manager_employee = get_manager_of_employee(customer_owner)
    if not manager_employee:
        frappe.throw("No manager found for the customer owner.")

    manager_user = get_user(manager_employee)
    if not manager_user:
        frappe.throw("Manager employee has no linked User account.")

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
    """
    Returns single pending field update request for this customer.
    Used on service doctype forms to check if request already sent.
    """
    user = frappe.session.user

    try:
        manager_employee = get_employee_name(user)
    except Exception:
        manager_employee = None

    if not manager_employee:
        return {"has_pending": False}

    customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
    if not customer_owner:
        return {"has_pending": False}

    manager_of_owner = get_manager_of_employee(customer_owner)
    if manager_of_owner != manager_employee:
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
    """
    Returns ALL pending field update requests on this Customer.
    Used on Customer form for manager to review all at once.
    """
    user = frappe.session.user

    try:
        manager_employee = get_employee_name(user)
    except Exception:
        manager_employee = None

    if not manager_employee:
        return []

    customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
    if not customer_owner:
        return []

    manager_of_owner = get_manager_of_employee(customer_owner)
    if manager_of_owner != manager_employee:
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
def apply_field_updates(customer_name, comment_name, approved_fields):
    """
    Called when manager clicks Done in Accept Updates dialog.
    Updates only the approved fields in Lead Detail Form.
    """
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

    # Apply only approved fields
    updated_fields = {}
    for field in approved_fields:
        if field in field_updates and field in UPDATABLE_FIELDS:
            new_value = field_updates[field].get("new")
            frappe.db.set_value(
                "Lead Detail Form",
                lead_detail_name,
                field,
                new_value,
            )
            updated_fields[field] = new_value

    # Mark comment as processed
    data["status"] = "Approved"
    data["approved_by"] = manager_employee
    data["approved_fields"] = approved_fields
    data["approved_at"] = datetime.now(timezone.utc).isoformat()
    frappe.db.set_value("Comment", comment_name, "content", json.dumps(data))
    frappe.db.commit()

    # Notify requester
    requester_user = data.get("requested_by_user")
    if requester_user:
        requester_email = frappe.db.get_value("User", requester_user, "email")
        if requester_email:
            field_names = ", ".join(UPDATABLE_FIELDS.get(f, f) for f in approved_fields)
            send_notification(
                recipients=[requester_email],
                subject=f"Field Updates Approved for Customer {customer_name}",
                message=(
                    f"Your manager <b>{manager_employee}</b> has approved updates "
                    f"for the following fields: <b>{field_names}</b>.<br><br>"
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


@frappe.whitelist()
def get_lead_detail_field_values(customer_name):
    """
    Returns current values of updatable fields from Lead Detail Form.
    Used to show old values in the Update Detail dialog.
    """
    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")

    if not lead_detail_name:
        return {}

    values = frappe.db.get_value(
        "Lead Detail Form",
        lead_detail_name,
        list(UPDATABLE_FIELDS.keys()),
        as_dict=True,
    )

    return values or {}


@frappe.whitelist()
def request_field_update_by_owner(customer_name, reason, field_updates):
    """
    Called when customer_owner clicks Update Detail on Customer form.
    Request goes to manager of customer_owner.
    """
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

    # Goes to manager of customer_owner
    manager_employee = get_manager_of_employee(employee)
    if not manager_employee:
        frappe.throw("No manager found for your Employee record.")

    manager_user = get_user(manager_employee)
    if not manager_user:
        frappe.throw("Manager employee has no linked User account.")

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
    """
    Checks if any service in the Sales Order for this Customer
    has Is Candidate Form Required = 1.
    Returns True/False.
    """
    lead_detail_name = frappe.db.get_value("Customer", customer_name, "lead_details")
    if not lead_detail_name:
        return {"required": False}

    so_name = frappe.db.get_value("Lead Detail Form", lead_detail_name, "sales_order")
    if not so_name:
        return {"required": False}

    services = frappe.db.get_all(
        "SalesOrderServices",
        filters={"parent": so_name, "parenttype": "Sales Order"},
        fields=["service"],
        ignore_permissions=True,
    )
    service_names = [s.service for s in services if s.service]

    if not service_names:
        return {"required": False}

    requires = frappe.db.exists(
        "Service",
        {
            "name": ["in", service_names],
            "is_candidate_form_required": 1,
        },
    )

    return {"required": bool(requires)}


@frappe.whitelist()
def get_owner_pending_field_update_request(customer_name):
    """
    Checks if the customer_owner has a pending field_update_request.
    Used on Customer form to show alert instead of button.
    """
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
