import frappe
from frappe.core.doctype.user.user import User as FrappeUser
from frappe import _

class CustomUser(FrappeUser):
    def after_insert(self):
        super().after_insert()
        frappe.errprint(f"CustomUser after_insert called for user: {self.name}")
        frappe.msgprint(
            msg=_("This user does not have an Employee record.\nYou should create an Employee for proper system access."),
            title=_("Missing Employee Record"),
            primary_action={
                'label': _("Create Employee"),
                'server_action': 'verp_staffing.overrides.user.redirect_to_employee_form',
                'hide_on_success': True 
            }
        )

@frappe.whitelist()
def redirect_to_employee_form():
    frappe.errprint("Redirecting to Employee form")
    frappe.set_route("Form", "Employee", "new-employee-1")