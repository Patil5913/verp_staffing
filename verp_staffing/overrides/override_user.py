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
        
    def validate(self):
        self.__new_password = self.new_password
        self.new_password = ""

        if not frappe.flags.in_test:
            self.password_strength_test()

        if self.name not in STANDARD_USERS:
            self.email = self.name
            self.validate_email_type(self.name)

        self.populate_role_profile_roles()
		# self.check_roles_added() # to avoid has no role message
        self.set_system_user()
        self.clean_name()
        self.set_full_name()
        self.check_enable_disable()
        self.ensure_unique_roles()
        self.remove_all_roles_for_guest()
        self.validate_username()
        self.remove_disabled_roles()
        self.validate_user_email_inbox()
        ask_pass_update()
        self.validate_allowed_modules()
        self.validate_user_image()
        self.set_time_zone()

        if self.language == "Loading...":
            self.language = None

        if (self.name not in ["Administrator", "Guest"]) and (not self.get_social_login_userid("frappe")):
            self.set_social_login_userid("frappe", frappe.generate_hash(length=39))

    def after_insert(self):
        super().after_insert()

        # adding role Inbox User to all users except Administrator and Guest
        if self.name in ("Administrator", "Guest"):
            return

        if frappe.db.exists(
            "Has Role",
            {"parent": self.name, "role": "Inbox User"}
        ):
            return

        self.append("roles", {"role": "Inbox User"})
        self.save(ignore_permissions=True)


def ask_pass_update():
	# update the sys defaults as to awaiting users
	from frappe.utils import set_default

	password_list = frappe.get_all(
		"User Email", filters={"awaiting_password": 1, "used_oauth": 0}, pluck="parent", distinct=True
	)
	set_default("email_user_password", ",".join(password_list))
