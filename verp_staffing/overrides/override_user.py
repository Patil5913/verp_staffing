import frappe
from frappe.core.doctype.user.user import User
from frappe import _, STANDARD_USERS


class CustomUser(User):
    @classmethod
    def get_quick_entry_fields(cls):
        """
        Controls fields shown in User Quick Entry.
        """
        fields = super().get_quick_entry_fields()
        # REMOVE role_profile_name from quick entry
        return [f for f in fields if f.get("fieldname") != "role_profile_name"]

    def send_login_mail(self, subject, template, add_args, now=None, custom_template=None):
        # On a site that also runs vrugledm, its own User override loses to this one, so apply
        # its fix here: send from the default outgoing Email Account rather than the signed-in
        # user's address, which the SMTP server rejects as "not owned by user".
        if "vrugledm" not in frappe.get_installed_apps():
            return super().send_login_mail(subject, template, add_args, now=now, custom_template=custom_template)

        real_sendmail = frappe.sendmail

        def sendmail(*args, **kwargs):
            kwargs["sender"] = None
            return real_sendmail(*args, **kwargs)

        frappe.sendmail = sendmail
        try:
            return super().send_login_mail(subject, template, add_args, now=now, custom_template=custom_template)
        finally:
            frappe.sendmail = real_sendmail

    def on_update(self):
        super().on_update()
        if self.user_type == "Website User":
            return  # customers are not employees
        if not getattr(self.flags, "in_insert", False):
            return
        if self.name == "Administrator":
            return
        if frappe.flags.get("in_sample_data_import"):
            return
        if frappe.db.exists("Employee", {"user": self.name}):
            return

        frappe.msgprint(
            msg=_(
                "This user does not have an Employee record.\nYou should create an Employee for proper system access."
            ),
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
        super().after_insert()

        # adding role Inbox User to all users except Administrator and Guest
        if self.name in ("Administrator", "Guest"):
            return

        # Customers (website users) get no staff roles; Inbox User would also make them a System User
        if self.user_type == "Website User":
            return

        if frappe.db.exists("Has Role", {"parent": self.name, "role": "Inbox User"}):
            return

        self.append("roles", {"role": "Inbox User"})
        self.save(ignore_permissions=True)


def ask_pass_update():
    # update the sys defaults as to awaiting users
    from frappe.utils import set_default

    password_list = frappe.get_all(
        "User Email",
        filters={"awaiting_password": 1, "used_oauth": 0},
        pluck="parent",
        distinct=True,
    )
    set_default("email_user_password", ",".join(password_list))
