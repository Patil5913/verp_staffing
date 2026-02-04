import frappe

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
    
    frappe.errprint(otherservies)
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
