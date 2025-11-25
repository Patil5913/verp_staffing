import frappe
from frappe.desk.reportview import get as original_get


@frappe.whitelist()
def secure_get(**kwargs):
    user = frappe.session.user
    roles = frappe.get_roles(user)
    doctype = frappe.local.form_dict.get("doctype")

    # Intercept URL query safely
    if user != "Administrator" and doctype == "Lead":
        lead_owners = get_lead_list_based_on_role(user, roles)

        if "Sales Employee" in roles:
            allowed_leads = get_sales_employee_leads(user)

            frappe.local.form_dict["filters"] = frappe.as_json(
                [
                    ["Lead", "name", "in", allowed_leads],
                ]
            )

            return original_get(**frappe.local.form_dict)

        if "Sales Manager" in roles:
            allowed_leads = get_sales_manager_leads(user)

            frappe.local.form_dict["filters"] = frappe.as_json(
                [["Lead", "name", "in", allowed_leads]]
            )

            return original_get(**frappe.local.form_dict)

        if "Sales Master Manager" in roles:
            allowed_leads = get_sales_master_manager_leads(user)

            frappe.local.form_dict["filters"] = frappe.as_json(
                [["Lead", "name", "in", allowed_leads]]
            )

            return original_get(**frappe.local.form_dict)

        # Force filter even if user tries to modify URL
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Lead", "lead_owner", "in", lead_owners]]
        )

    if user != "Administrator" and doctype == "Opportunity":
        opportunity_owners = get_lead_list_based_on_role(user, roles)

        # Force filter even if user tries to modify URL
        frappe.local.form_dict["filters"] = frappe.as_json(
            [["Opportunity", "opportunity_owner", "in", opportunity_owners]]
        )

    # Call Frappe's original get function with the current form_dict
    return original_get(**frappe.local.form_dict)


def get_employee_name(user):
    return frappe.db.get_value("Employee", {"user": user}, "employee_name")


def get_employee_list(user):
    employee_name = get_employee_name(user)
    if not employee_name:
        return []

    return [employee_name]


def get_manager_leads(user):
    """Return self + all connected employees' employee_name."""
    all_owners = []

    all_owners.extend(get_employee_list(user))  # get his own leads

    connected_employees = frappe.db.get_all(
        "Employee", filters={"manager": get_employee_name(user)}, pluck="user"
    )

    for emp in connected_employees:
        all_owners.extend(get_employee_list(emp))

    return all_owners


def get_master_manager_leads(user):
    """Return self + all connected managers + all connected employees of managers' employee_name."""
    all_owners = []

    all_owners.extend(get_employee_list(user))  # get his own leads

    connected_managers = frappe.db.get_all(
        "Employee",
        filters={"master_manager": get_employee_name(user), "designation": "manager"},
        pluck="user",
    )

    for man in connected_managers:
        all_owners.extend(get_manager_leads(man))

    return all_owners


def get_manager_opportunities(user):
    """Return self + all connected employees' employee_name."""
    all_owners = []

    all_owners.extend(get_employee_list(user))  # get his own leads

    connected_employees = frappe.db.get_all(
        "Employee", filters={"manager": get_employee_name(user)}, pluck="user"
    )

    for emp in connected_employees:
        all_owners.extend(get_employee_list(emp))

    return all_owners


def get_master_manager_opportunities(user):
    """Return self + all connected managers + all connected employees of managers' employee_name."""
    all_owners = []

    all_owners.extend(get_employee_list(user))  # get his own leads

    connected_managers = frappe.db.get_all(
        "Employee",
        filters={"master_manager": get_employee_name(user), "designation": "manager"},
        pluck="user",
    )

    for man in connected_managers:
        all_owners.extend(get_manager_opportunities(man))

    return all_owners


def get_lead_list_based_on_role(user, roles):
    """Return Employee names that the user is allowed to see based on role."""

    if "Lead Master Manager" in roles:
        return get_master_manager_leads(user)

    if "Lead Manager" in roles:
        return get_manager_leads(user)

    if "Sales Master Manager" in roles:
        return get_master_manager_opportunities(user)

    if "Sales Manager" in roles:
        return get_manager_opportunities(user)

    # Default: normal employee
    return get_employee_list(user)


def get_sales_employee_leads(user):
    """Return leads assigned directly to the Sales Employee."""

    all_leads = []

    all_leads.extend(get_employee_list(user))  # get his own leads

    opp_leads = frappe.db.get_all(  # get leads from opportunities assigned to him
        "Opportunity",
        filters={"opportunity_owner": get_employee_name(user)},
        pluck="party_name",
    )
    own_leads = frappe.db.get_all(  # get leads assigned to him
        "Lead", filters={"lead_owner": get_employee_name(user)}, pluck="name"
    )

    all_leads.extend(own_leads)
    all_leads.extend(opp_leads)
    return all_leads


def get_sales_manager_leads(user):
    """Return leads assigned directly to the Sales Manager and his team."""
    all_leads = []

    all_leads.extend(get_employee_list(user))  # get his own leads

    # get leads from opportunities assigned to him
    opp_leads = frappe.db.get_all(
        "Opportunity",
        filters={"opportunity_owner": get_employee_name(user)},
        pluck="party_name",
    )
    own_leads = frappe.db.get_all(  # get leads assigned to him
        "Lead", filters={"lead_owner": get_employee_name(user)}, pluck="name"
    )

    all_leads.extend(own_leads)

    all_leads.extend(opp_leads)

    connected_employees = frappe.db.get_all(
        "Employee", filters={"manager": get_employee_name(user)}, pluck="user"
    )

    for emp in connected_employees:
        emp_leads = get_sales_employee_leads(emp)
        all_leads.extend(emp_leads)

    return all_leads


def get_sales_master_manager_leads(user):
    """Return leads assigned directly to the Sales Master Manager, his managers and their teams."""
    all_leads = []

    all_leads.extend(get_employee_list(user))  # get his own leads

    # get leads from opportunities assigned to him
    opp_leads = frappe.db.get_all(
        "Opportunity",
        filters={"opportunity_owner": get_employee_name(user)},
        pluck="party_name",
    )
    own_leads = frappe.db.get_all(  # get leads assigned to him
        "Lead", filters={"lead_owner": get_employee_name(user)}, pluck="name"
    )

    all_leads.extend(own_leads)
    all_leads.extend(opp_leads)

    connected_managers = frappe.db.get_all(
        "Employee",
        filters={"master_manager": get_employee_name(user), "designation": "manager"},
        pluck="user",
    )

    for man in connected_managers:
        man_leads = get_sales_manager_leads(man)
        all_leads.extend(man_leads)

    return all_leads
