from frappe import _

def get_data():
    return [
        {
            "label": _("CRM"),
            "icon": "octicon octicon-briefcase",
            "items": [
                {"type": "doctype", "name": "Customer"},
                {"type": "doctype", "name": "Lead"},
                {"type": "doctype", "name": "Opportunity"},
                {"type": "doctype", "name": "CRM Task"},
                {"type": "doctype", "name": "CRM Event"}
            ]
        }
    ]
