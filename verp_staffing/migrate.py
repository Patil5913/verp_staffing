import frappe

def after_migrate():
    keep_list = ["CRM", "Users"]

    frappe.db.sql("""
        UPDATE `tabWorkspace`
        SET is_hidden = 1
        WHERE name NOT IN ({})
    """.format(", ".join(["%s"] * len(keep_list))), tuple(keep_list))

    frappe.db.commit()
    print("Workspace visibility updated via after_migrate()")
