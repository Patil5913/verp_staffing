# import frappe
# from frappe.desk.reportview import get as original_get


# @frappe.whitelist()
# def secure_get(**kwargs):
#     user = frappe.session.user
#     roles = frappe.get_roles(user)
#     doctype = frappe.local.form_dict.get("doctype")

#     # Intercept URL query safely
#     if user != "Administrator" and doctype == "Lead":
#         lead_owners = get_lead_list_based_on_role(user, roles)

#         if "Sales Employee" in roles:
#             allowed_leads = get_sales_employee_leads(user)

#             frappe.local.form_dict["filters"] = frappe.as_json(
#                 [
#                     ["Lead", "name", "in", allowed_leads],
#                 ]
#             )

#             return original_get(**frappe.local.form_dict)

#         if "Sales Manager" in roles:
#             allowed_leads = get_sales_manager_leads(user)

#             frappe.local.form_dict["filters"] = frappe.as_json(
#                 [["Lead", "name", "in", allowed_leads]]
#             )

#             return original_get(**frappe.local.form_dict)

#         if "Sales Master Manager" in roles:
#             allowed_leads = get_sales_master_manager_leads(user)

#             frappe.local.form_dict["filters"] = frappe.as_json(
#                 [["Lead", "name", "in", allowed_leads]]
#             )

#             return original_get(**frappe.local.form_dict)

#         # Force filter even if user tries to modify URL
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Lead", "lead_owner", "in", lead_owners]]
#         )

#     if user != "Administrator" and doctype == "Opportunity":
#         opportunity_owners = get_lead_list_based_on_role(user, roles)

#         # Force filter even if user tries to modify URL
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Opportunity", "opportunity_owner", "in", opportunity_owners]]
#         )
        
#     if user != "Administrator" and doctype == "Customer":
#         opportunity_owners = get_lead_list_based_on_role(user, roles)

#         allowed_oppotunities = frappe.db.get_all(
#             "Opportunity",
#             filters={"opportunity_owner": ["in", opportunity_owners]},
#             pluck="name",
#         )
#         # Force filter even if user tries to modify URL
#         frappe.local.form_dict["filters"] = frappe.as_json(
#             [["Customer", "opportunity", "in", allowed_oppotunities]]
#         )
#     # Call Frappe's original get function with the current form_dict
#     return original_get(**frappe.local.form_dict)


# def get_employee_name(user):
#     return frappe.db.get_value("Employee", {"user": user}, "employee_name")


# def get_employee_list(user):
#     employee_name = get_employee_name(user)
#     if not employee_name:
#         return []

#     return [employee_name]


# def get_manager_leads(user):
#     """Return self + all connected employees' employee_name."""
#     all_owners = []

#     all_owners.extend(get_employee_list(user))  # get his own leads

#     connected_employees = frappe.db.get_all(
#         "Employee", filters={"assigned_to": get_employee_name(user)}, pluck="user"
#     )

#     for emp in connected_employees:
#         all_owners.extend(get_employee_list(emp))

#     return all_owners


# def get_master_manager_leads(user):
#     """Return self + all connected managers + all connected employees of managers' employee_name."""
#     all_owners = []

#     all_owners.extend(get_employee_list(user))  # get his own leads

#     connected_managers = frappe.db.get_all(
#         "Employee",
#         filters={"assigned_to": get_employee_name(user)},
#         pluck="user",
#     )

#     for man in connected_managers:
#         all_owners.extend(get_manager_leads(man))

#     return all_owners


# def get_manager_opportunities(user):
#     """Return self + all connected employees' employee_name."""
#     all_owners = []

#     all_owners.extend(get_employee_list(user))  # get his own leads

#     connected_employees = frappe.db.get_all(
#         "Employee", filters={"assigned_to": get_employee_name(user)}, pluck="user"
#     )

#     for emp in connected_employees:
#         all_owners.extend(get_employee_list(emp))

#     return all_owners


# def get_master_manager_opportunities(user):
#     """Return self + all connected managers + all connected employees of managers' employee_name."""
#     all_owners = []

#     all_owners.extend(get_employee_list(user))  # get his own leads

#     connected_managers = frappe.db.get_all(
#         "Employee",
#         filters={"assigned_to": get_employee_name(user)},
#         pluck="user",
#     )

#     for man in connected_managers:
#         all_owners.extend(get_manager_opportunities(man))

#     return all_owners


# def get_lead_list_based_on_role(user, roles):
#     """Return Employee names that the user is allowed to see based on role."""

#     if "Lead Master Manager" in roles:
#         return get_master_manager_leads(user)

#     if "Lead Manager" in roles:
#         return get_manager_leads(user)

#     if "Sales Master Manager" in roles:
#         return get_master_manager_opportunities(user)

#     if "Sales Manager" in roles:
#         return get_manager_opportunities(user)

#     # Default: normal employee
#     return get_employee_list(user)


# def get_sales_employee_leads(user):
#     """Return leads assigned directly to the Sales Employee."""

#     all_leads = []

#     all_leads.extend(get_employee_list(user))  # get his own leads

    # opp_leads = frappe.db.get_all(  # get leads from opportunities assigned to him
    #     "Opportunity",
    #     filters={"opportunity_owner": get_employee_name(user)},
    #     pluck="party_name",
    # )
#     own_leads = frappe.db.get_all(  # get leads assigned to him
#         "Lead", filters={"lead_owner": get_employee_name(user)}, pluck="name"
#     )

#     all_leads.extend(own_leads)
#     all_leads.extend(opp_leads)
#     return all_leads


# def get_sales_manager_leads(user):
#     """Return leads assigned directly to the Sales Manager and his team."""
#     all_leads = []

#     all_leads.extend(get_employee_list(user))  # get his own leads

#     # get leads from opportunities assigned to him
#     opp_leads = frappe.db.get_all(
#         "Opportunity",
#         filters={"opportunity_owner": get_employee_name(user)},
#         pluck="party_name",
#     )
#     own_leads = frappe.db.get_all(  # get leads assigned to him
#         "Lead", filters={"lead_owner": get_employee_name(user)}, pluck="name"
#     )

#     all_leads.extend(own_leads)

#     all_leads.extend(opp_leads)

#     connected_employees = frappe.db.get_all(
#         "Employee", filters={"assigned_to": get_employee_name(user)}, pluck="user"
#     )

#     for emp in connected_employees:
#         emp_leads = get_sales_employee_leads(emp)
#         all_leads.extend(emp_leads)

#     return all_leads


# def get_sales_master_manager_leads(user):
#     """Return leads assigned directly to the Sales Master Manager, his managers and their teams."""
#     all_leads = []

#     all_leads.extend(get_employee_list(user))  # get his own leads

#     # get leads from opportunities assigned to him
#     opp_leads = frappe.db.get_all(
#         "Opportunity",
#         filters={"opportunity_owner": get_employee_name(user)},
#         pluck="party_name",
#     )
#     own_leads = frappe.db.get_all(  # get leads assigned to him
#         "Lead", filters={"lead_owner": get_employee_name(user)}, pluck="name"
#     )

#     all_leads.extend(own_leads)
#     all_leads.extend(opp_leads)

#     connected_managers = frappe.db.get_all(
#         "Employee",
#         filters={"assigned_to": get_employee_name(user)},
#         pluck="user",
#     )

#     for man in connected_managers:
#         man_leads = get_sales_manager_leads(man)
#         all_leads.extend(man_leads)

#     return all_leads


import frappe
from frappe.desk.reportview import get as original_get


# =========================================================
# ENTRY POINT
# =========================================================
@frappe.whitelist()
def secure_get(**kwargs):
    user = frappe.session.user
    roles = frappe.get_roles(user)
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

    return original_get(**frappe.local.form_dict)

# get allowed leads for sales person
def get_allowed_leads(user):
    root_employee = get_employee_name(user)
    all_leads = []
    if not root_employee:
        return []
    users = [root_employee]

    sub_users = get_subordinate_users(root_employee_name=get_employee_name(user))
    if sub_users:
        users.extend(sub_users)

    users = list(set(users)) 
    
    # Leads directly owned
    own_leads = frappe.db.get_all(
        "Lead",
        filters={"lead_owner": ["in", users]},
        pluck="name",
    )

    # Leads linked via opportunities
    opp_leads = frappe.db.get_all(
        "Opportunity",
        filters={"opportunity_owner": ["in", users]},
        pluck="party_name",  # assuming party_name = Lead
    )


    # Merge + dedupe
    all_leads = list(set(own_leads + opp_leads))

    return all_leads



# =========================================================
# CORE VISIBILITY LOGIC
# =========================================================
def get_visible_employee_names(user):
    root_employee = get_employee_name(user)
    if not root_employee:
        return []

    users = get_subordinate_users(
        root_employee_name=root_employee,
    )

    users.add(root_employee)
    return users


# =========================================================
# HIERARCHY HELPERS
# =========================================================
def get_role_hierarchy(name):
    hierarchy_json = frappe.db.get_value(
        "Hierarchy",
        name,
        "role_hierarchy_json",
    )
    if not hierarchy_json:
        return []

    try:
        return frappe.parse_json(hierarchy_json)
    except Exception:
        frappe.throw(f"Invalid role_hierarchy_json in Hierarchy: {name}")


def build_role_tree(hierarchy):
    tree = {}
    for row in hierarchy:
        parent = row.get("parent_role")
        children = row.get("child_roles", [])
        if parent:
            tree.setdefault(parent, set()).update(children)
    return tree


def get_all_child_roles(role, tree):
    collected = set()
    stack = [role]

    while stack:
        current = stack.pop()
        for child in tree.get(current, []):
            if child not in collected:
                collected.add(child)
                stack.append(child)
    return collected


# =========================================================
# EMPLOYEE TREE TRAVERSAL
# =========================================================
def get_employee_name(user):
    return frappe.db.get_value(
        "Employee",
        {"user": user},
        "employee_name",
    )


def get_subordinate_users(root_employee_name):
    collected_users = set()
    stack = [root_employee_name]


    while stack:
        current = stack.pop()

        children = frappe.db.get_all(
            "Employee",
            filters={"assigned_to": current},
            fields=["employee_name"],
        )

        for emp in children:
            stack.append(emp.employee_name)

            if emp.employee_name:
                collected_users.add(emp.employee_name)
    return collected_users
