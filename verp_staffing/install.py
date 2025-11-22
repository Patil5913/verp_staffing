import frappe

def after_install():
    seed_sales_stages()
    create_role("Lead Employee")
    set_role_permissions("Lead Employee", "Lead", ["create", "read", "write"])


def seed_sales_stages():
    doctype = "Sales Stage"
    sales_stages = ["Prospecting", "Qualification", "Needs Analysis", "Value Proposition", "Identifying Decision Makers", "Perception Analysis", "Proposal/Price Quote", "Negotiation/Review"]

    for stage in sales_stages:
        if not frappe.db.exists(doctype, stage):
            doc = frappe.get_doc({
                "doctype": doctype,
                "name1": stage,
            })
            doc.insert(ignore_permissions=True)
            

def create_role(role_name):
    """Create role if it doesn't already exist."""
    
    if not frappe.db.exists("Role", role_name):
        role = frappe.new_doc("Role")
        role.role_name = role_name
        role.desk_access = 1
        role.save(ignore_permissions=True)


def set_role_permissions(role, doctype, perms):
    """
    perms = list of permissions like:
        ["read", "write", "create", "delete"]
    """

    perm_map = {
        "read": "read",
        "write": "write",
        "create": "create",
        "delete": "delete",
        "submit": "submit",
        "cancel": "cancel",
        "amend": "amend",
        "print": "print",
        "email": "email",
        "share": "share",
        "report": "report",
        "import": "import",
        "export": "export",
    }

    # Remove existing permissions for this role + doctype (important for idempotency)
    frappe.db.delete("Custom DocPerm", {
        "role": role,
        "parent": doctype
    })

    # Create new permission line
    perm_doc = frappe.new_doc("Custom DocPerm")
    perm_doc.parent = doctype
    perm_doc.parentfield = "permissions"
    perm_doc.parenttype = "DocType"
    perm_doc.role = role
    perm_doc.idx = 1

    # Set permissions dynamically
    for p in perms:
        if p in perm_map:
            setattr(perm_doc, perm_map[p], 1)

    perm_doc.save(ignore_permissions=True)

    # Clear cache so permissions apply immediately
    frappe.clear_cache(doctype=doctype)
