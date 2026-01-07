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
    technical = frappe.get_all(
        "RUC",
        filters={"customer": customer},
        fields=["name", "status", "assign_to", "modified"],
        limit=1
    )
    if technical:
        result["technical"] = {
            "status": technical[0].status,
            "assign_to": technical[0].assign_to,
            "last_updated": technical[0].modified
        }

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
