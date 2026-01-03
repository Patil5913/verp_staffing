import frappe
from frappe.core.doctype.user.user import (User)
from frappe import _

class CustomUser(User):
    def on_update(self):
        super().on_update()
        frappe.errprint(f"on_update called for {self.name}")
        if not getattr(self.flags, "in_insert", False):
            return
        if self.name == "Administrator":
            return

        employee_exists = frappe.db.exists("Employee", {"user": self.name})
        if employee_exists:
            return

        frappe.msgprint(
            msg=_("from onupdate This user does not have an Employee record.\nYou should create an Employee for proper system access."),
            title=_("Missing Employee Record"),
            primary_action={
                "label": _("Create Employee"),
                "client_action": "frappe.set_route",
                "args": ["Employee", "new-employee-1"],
                "hide_on_success": True,
            },
        )
