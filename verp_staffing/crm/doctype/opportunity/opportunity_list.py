import frappe
from frappe.desk.reportview import get as original_get

@frappe.whitelist()
def secure_get(**kwargs):
    user = frappe.session.user
    roles = frappe.get_roles(user)
    doctype = frappe.local.form_dict.get("doctype")

    # Intercept URL query safely
    if user != "Administrator" and doctype == "Opportunity":
        opportunity_owners = get_opportunity_owners_list_based_on_role(user, roles)
        
        # Force filter even if user tries to modify URL
        frappe.local.form_dict['filters'] = frappe.as_json([
            ["Opportunity", "opportunity_owner", "in", opportunity_owners]
        ])

    # Call Frappe's original get function with the current form_dict
    return original_get(**frappe.local.form_dict)


def get_employee_name(user):
    return frappe.db.get_value("Employee", {"user": user}, "employee_name")


def get_employee_leads(user):
    employee_name = get_employee_name(user)
    if not employee_name:
        return []

    return [employee_name]


def get_manager_opportunities(user):
    """Return self + all connected employees' employee_name."""
    all_owners = []

    all_owners.extend(get_employee_leads(user)) # get his own leads

    connected_employees = frappe.db.get_all(
        "Employee",
        filters={"manager": get_employee_name(user)},
        pluck="user"
    )

    for emp in connected_employees:
        all_owners.extend(get_employee_leads(emp))
    
    return all_owners


def get_master_manager_opportunities(user):
    """Return self + all connected managers + all connected employees of managers' employee_name."""
    all_owners = []

    all_owners.extend(get_employee_leads(user)) # get his own leads

    connected_managers = frappe.db.get_all(
        "Employee",
        filters={"master_manager": get_employee_name(user), "designation": "manager"},
        pluck="user"
    )

    for man in connected_managers:
        all_owners.extend(get_manager_opportunities(man))

    return all_owners


def get_opportunity_owners_list_based_on_role(user, roles):
    """Return Employee names that the user is allowed to see based on role."""

    if "Sales Master Manager" in roles:
        return get_master_manager_opportunities(user)

    if "Sales Manager" in roles:
        return get_manager_opportunities(user)

    # Default: normal employee
    return get_employee_leads(user)