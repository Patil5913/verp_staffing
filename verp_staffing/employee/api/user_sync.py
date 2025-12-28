import frappe

def create_user_from_employee(doc, method=None):
    if doc.user:
        frappe.errprint(f"User already linked to Employee {doc.name}: {doc.user}")
        return

    if not doc.user_email:
        frappe.throw("Login Email is required to create User")

    email = doc.user_email.strip().lower()
    frappe.errprint(f"Creating/Linking User for Employee {doc.name} with email {email}, name {doc.employee_name}")
    # Reuse existing user if present
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
    else:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": doc.employee_name or email.split('@')[0],
            "enabled": 1,
            "send_welcome_email": 0
        })
        user.insert(ignore_permissions=True)
        frappe.errprint(f"Created User {user.name} for Employee {doc.name}")

    # Link user to employee
    doc.db_set("user", user.name)

    # Initial role sync
    frappe.flags.in_employee_sync = True
    frappe.call(
        "verp_staffing.employee.api.workspace_automation.sync_user_workspace_roles",
        doc=doc
    )
    frappe.flags.in_employee_sync = False
