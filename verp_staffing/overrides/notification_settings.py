import frappe
from frappe.desk.doctype.notification_settings.notification_settings import (
    create_notification_settings,
)


def ensure_notification_settings():
    user = frappe.session.user
    if user and user != "Guest" and not frappe.db.exists("Notification Settings", user):
        create_notification_settings(user)
