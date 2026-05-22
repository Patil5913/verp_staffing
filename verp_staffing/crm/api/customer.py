import frappe
import json
from frappe.utils import now_datetime

@frappe.whitelist()

def get_customer_department_panels(customer):
    result = {}

    # ---------------- Resume ----------------
    resume = frappe.get_all(
        "Resume",
        filters={"customer": customer},
        fields=["name", "status", "assign_to", "modified"],
        limit=1
    )
    if resume:
        result["resume"] = {
            "status": resume[0].status,
            "assign_to": resume[0].assign_to,
            "last_updated": resume[0].modified
        }

    # ---------------- Technical ----------------
    result["technical"] = []

    ruc = frappe.get_all(
        "RUC",
        filters={"customer": customer},
        fields=["name", "status", "assign_to", "modified"],
        limit=1
    )

    jdc = frappe.get_all(
        "JDC",
        filters={"customer": customer},
        fields=["name", "status", "assign_to", "modified"],
        limit=1
    )
    
    training = frappe.get_all(
        "Training",
        filters={"customer": customer},
        fields=["name", "status", "assign_to", "modified"],
        limit=1
    )

    coverletter = frappe.get_all(
        "Cover Letter",
        filters={"customer": customer},
        fields=["name", "status", "assign_to", "modified"],
        limit=1
    )
    
    otherservies = frappe.get_all(
        "Technical Other Services",
        filters={"customer": customer},
        fields=["name", "status", "assign_to", "modified" , "service"],
    )
    
    if ruc:
        result["technical"].append({
            "name": "RUC",
            "status": ruc[0].status,
            "assign_to": ruc[0].assign_to,
            "last_updated": ruc[0].modified
        })

    if jdc:
        result["technical"].append({
            "name": "JDC",
            "status": jdc[0].status,
            "assign_to": jdc[0].assign_to,
            "last_updated": jdc[0].modified
        })
        
    if training:
        result["technical"].append({
            "name": "Traning",
            "status": training[0].status,
            "assign_to": training[0].assign_to,
            "last_updated": training[0].modified
        })
    
    if coverletter:
        result["technical"].append({
            "name": "Cover Letter",
            "status": coverletter[0].status,
            "assign_to": coverletter[0].assign_to,
            "last_updated": coverletter[0].modified
        })
        
    if otherservies:
        for service in otherservies:
            result["technical"].append({
                "name": service.service,
                "status": service.status,
                "assign_to": service.assign_to,
                "last_updated": service.modified
            })
    


    # ---------------- Marketing ----------------
    marketing = frappe.get_all(
        "Marketing",
        filters={"customer": customer},
        fields=["name", "assign_to", "modified"],
        limit=1
    )

    if marketing:
        marketing_name = marketing[0].name

        total_interviews = frappe.db.count(
            "Interview",
            filters={"marketing_link": marketing_name}
        )

        current_interviews = frappe.db.count(
            "Interview",
            filters={
                "marketing_link": marketing_name,
                "status": ["not in", ["Accepted", "Rejected"]]
            }
        )

        result["marketing"] = {
            "assign_to": marketing[0].assign_to,
            "total_interviews": total_interviews,
            "current_interviews": current_interviews,
            "last_updated": marketing[0].modified
        }

    return result


@frappe.whitelist()
def update_customer_stage(
    customer,
    service,
    *,
    prevent_duplicate=True,
    timestamp=None,
):
    """
    Generic reusable customer stage updater.

    Args:
        customer (str): Customer name
        service (str): Service key (example: "ruc", "visa", "marketing")
        prevent_duplicate (bool): Avoid duplicate department entry
        timestamp (str|None): Custom timestamp override
    """

    if not customer or not service:
        return

    cache_key = f"department_service::{service}"

    department = frappe.cache().get_value(
        cache_key
    )

    if not department:

        department = frappe.db.get_value(
            "Department Service",
            {
                "service_name": service,
            },
            "parent",
        )

        if not department:
            frappe.throw(
                f"Department not found for service: {service}"
            )

        frappe.cache().set_value(
            cache_key,
            department,
        )

    timestamp = (
        timestamp
        or now_datetime().isoformat()
    )

    stage = frappe.db.get_value(
        "Customer",
        customer,
        "stage",
    )

    # =====================================
    # ULTRA FAST PATH
    # =====================================

    if not stage:

        frappe.db.set_value(
            "Customer",
            customer,
            "stage",
            json.dumps(
                {
                    service: [
                        {
                            "department": department,
                            "timestamp": timestamp,
                        }
                    ]
                },
                separators=(",", ":"),
            ),
            update_modified=False,
        )

        return

    # =====================================
    # NORMAL PATH
    # =====================================

    try:
        stage_data = json.loads(stage)
    except Exception:
        stage_data = {}

    service_stage = stage_data.setdefault(
        service,
        [],
    )

    if prevent_duplicate:

        exists = any(
            row.get("department") == department
            for row in service_stage
        )

        if exists:
            return

    service_stage.append(
        {
            "department": department,
            "timestamp": timestamp,
        }
    )

    frappe.db.set_value(
        "Customer",
        customer,
        "stage",
        json.dumps(
            stage_data,
            separators=(",", ":"),
        ),
        update_modified=False,
    )