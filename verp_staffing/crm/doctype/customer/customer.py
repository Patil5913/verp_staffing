# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe.model.document import Document


class Customer(Document):
    def autoname(self):
        import re

        if self.customer_name:
            base_name = self.customer_name.strip()
            
            if not base_name:
                # fallback to default naming if something is wrong
                self.name = frappe.generate_hash(length=10)
                return

            self.title = base_name
            
            # Fetch all titles that start with base_name
            existing_titles = frappe.get_all(
                "Customer",
                filters={"title": ["like", f"{base_name}%"]},
                pluck="title"
            )
            
            max_count = 0

            for title in existing_titles:
                # Exact match (e.g., "name")
                if title == base_name:
                    max_count = max(max_count, 1)
                    continue

                # Match pattern name_number
                match = re.match(rf"^{re.escape(base_name)}-(\d+)$", title)
                if match:
                    count = int(match.group(1))
                    max_count = max(max_count, count)

            # Generate next title
            if max_count == 0:
                self.name = f"{base_name}-1"
            else:
                self.name = f"{base_name}-{max_count + 1}"
                

    def validate(self):
        if self.stage:
            try:
                json.loads(self.stage)
            except Exception:
                frappe.throw("Stage field contains invalid JSON")


@frappe.whitelist()
def get_employee_department():
    employee_name = frappe.get_value("Employee", {"user": frappe.session.user}, "name")

    if not employee_name:
        return None

    emp = frappe.get_doc("Employee", employee_name)
    return emp.employee_assignment_details_table


@frappe.whitelist()
def get_forwardable_departments(customer):
    """
    Return only departments that have at least one service.
    """
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer},
        pluck="name",
        order_by="creation desc",
        limit=1,
    )
    # rdqgv3r9ip
    frappe.errprint(f"Sales Orders for customer {customer}: {so}")
    # DISTINCT parent departments that have services
    services = frappe.db.sql(
        """
        SELECT service
        FROM `tabSalesOrderServices`
        WHERE parenttype = 'Sales Order'
        AND parent IN %s
        """,
        (tuple(so),),
        as_dict=True,
    )

    if not services:
        return []

    service_names = [d.service for d in services]
    
    # Optional: validate department still exists
    valid_services = frappe.get_all(
        "Service", filters={"name": ["in", service_names]}, pluck="name"
    )
    
    frappe.errprint(valid_services)

    return valid_services
