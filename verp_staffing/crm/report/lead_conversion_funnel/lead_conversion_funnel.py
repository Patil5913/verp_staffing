# # Copyright (c) 2026, Vrugle and contributors
# # For license information, please see license.txt

# import frappe

# def execute(filters=None):
#     columns = get_columns()
#     data = get_data()
#     chart = get_chart(data)

#     return columns, data, None, chart


# def get_columns():
#     return [
#         {
#             "label": "Stage",
#             "fieldname": "stage",
#             "fieldtype": "Data",
#             "width": 200,
#         },
#         {
#             "label": "Count",
#             "fieldname": "count",
#             "fieldtype": "Int",
#             "width": 120,
#         },
#     ]


# def get_data():
#     total_leads = frappe.db.count("Lead")

#     leads_with_opportunity = frappe.db.sql("""
#         SELECT COUNT(DISTINCT l.name)
#         FROM `tabLead` l
#         INNER JOIN `tabOpportunity` o
#           ON o.opportunity_from = 'Lead'
#          AND o.party_name = l.name
#     """)[0][0]

#     lost_leads =frappe.db.count(
#         "Opportunity",
#         {
#             "opportunity_from": "Lead",
#             "status": "Lost"
#         }
#     )

#     converted_opportunities = frappe.db.count(
#         "Opportunity",
#         {
#             "opportunity_from": "Lead",
#             "status": "Converted"
#         }
#     )

#     return [
#         {"stage": "Total Leads", "count": total_leads},
#         {"stage": "Leads with Opportunity", "count": leads_with_opportunity},
#         {"stage": "Lost Leads", "count": lost_leads},
#         {"stage": "Converted Opportunities", "count": converted_opportunities},
#     ]


# def get_chart(data):
#     return {
#         "data": {
#             "labels": [row["stage"] for row in data],
#             "datasets": [
#                 {
#                     "name": "Lead Funnel",
#                     "values": [row["count"] for row in data],
#                 }
#             ],
#         },
#         "type": "bar",
#     }


import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data()
    chart = get_chart(data)

    return columns, data, None, chart


def get_columns():
    return [
        {
            "label": "Stage",
            "fieldname": "stage",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Count",
            "fieldname": "count",
            "fieldtype": "Int",
            "width": 120,
        },
    ]


def get_data():
    total_leads = frappe.db.count("Lead")

    leads_with_opportunity = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT l.name)
        FROM `tabLead` l
        INNER JOIN `tabOpportunity` o
          ON o.opportunity_from = 'Lead'
         AND o.party_name = l.name
    """
    )[0][0]

    converted_opportunities = frappe.db.count(
        "Opportunity", {"opportunity_from": "Lead", "status": "Converted"}
    )

    lost_opportunities = frappe.db.count(
        "Opportunity", {"opportunity_from": "Lead", "status": "Lost"}
    )

    return [
        {"stage": "Total Leads", "count": total_leads},
        {"stage": "Leads with Opportunity", "count": leads_with_opportunity},
        {"stage": "Converted Opportunities", "count": converted_opportunities},
        {"stage": "Lost Opportunities", "count": lost_opportunities},
    ]


def get_chart(data):
    return {
        "data": {
            "labels": [row["stage"] for row in data],
            "datasets": [
                {
                    "name": "Lead Conversion Funnel",
                    "values": [row["count"] for row in data],
                    
                },
            ],
            "colors": [
                        "#4F46E5",  # Total Leads - Indigo
                        "#0284C7",  # Leads with Opportunity - Blue
                        "#16A34A",  # Converted - Green
                        "#DC2626",  # Lost - Red
                    ],
        },
        "type": "bar",
    }
