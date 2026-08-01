import frappe
from frappe.core.doctype.user.user import (User)
from frappe import _,STANDARD_USERS

class CustomUser(User):
    @classmethod
    def get_quick_entry_fields(cls):
        """
        Controls fields shown in User Quick Entry.
        """
        fields = super().get_quick_entry_fields()
        # REMOVE role_profile_name from quick entry
        return [
            f for f in fields
            if f.get("fieldname") != "role_profile_name"
        ]

    def on_update(self):
        super().on_update()
        if not getattr(self.flags, "in_insert", False):
            return
        if self.name == "Administrator":
            return

        if frappe.db.exists("Employee", {"user": self.name}):
            return

        frappe.msgprint(
            msg=_("This user does not have an Employee record.\nYou should create an Employee for proper system access."),
            title=_("Missing Employee Record"),
            primary_action={
                "label": _("Create Employee"),
                "client_action": "frappe.set_route",
                "args": ["employee", "new-employee-1"],
                "hide_on_success": True,
            },
        )
    def check_roles_added(self):
        "Override this core validation function as it is breaking our flow"
        return    

    def after_insert(self):
        # adding role Inbox User to all users except Administrator and Guest
        if self.name in ("Administrator", "Guest"):
            return

        if frappe.db.exists(
            "Has Role",
            {"parent": self.name, "role": "Inbox User"}
        ):
            return

        self.save(ignore_permissions=True)

        super().after_insert()


def ask_pass_update():
	# update the sys defaults as to awaiting users
	from frappe.utils import set_default

	password_list = frappe.get_all(
		"User Email", filters={"awaiting_password": 1, "used_oauth": 0}, pluck="parent", distinct=True
	)
	set_default("email_user_password", ",".join(password_list))
