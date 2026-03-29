app_name = "verp_staffing"
app_title = "Vrugle Staffing ERP"
app_publisher = "Vrugle"
app_description = "this is staffing erp designed and made by vrugle"
app_email = "contact@vrugle.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "verp_staffing",
# 		"logo": "/assets/verp_staffing/logo.png",
# 		"title": "Vrugle Staffing ERP",
# 		"route": "/verp_staffing",
# 		"has_permission": "verp_staffing.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = ["/assets/verp_staffing/css/globel.css"]
# pdflibjs Imports
app_include_js = [
    "pdf_lib_bundle.bundle.js",
    "/assets/verp_staffing/js/reusable.js",
    "/assets/verp_staffing/js/salesOrder.js",
    "/assets/verp_staffing/js/user_custom.js",
    "/assets/verp_staffing/js/about_override.js",
    # "/assets/verp_staffing/js/protection.js",
    "/assets/verp_staffing/js/email_badge.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/verp_staffing/css/verp_staffing.css"
# web_include_js = "/assets/verp_staffing/js/verp_staffing.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "verp_staffing/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
validation_docs = ["Lead", "Lead Course", "Resume", "RUC", "Opportunity", "Marketing","Marketing Other Services", "Customer","JDC","Cover Letter","Technical Other Services","Training" , "Other Services","Sales Order", "Agreement"]
doctype_js = {
    doc: ["public/js/reusable.js", "public/js/salesOrder.js"]
    for doc in validation_docs
}

doctype_list_js = {
    "Lead": "public/js/lead_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "verp_staffing/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "verp_staffing.utils.jinja_methods",
# 	"filters": "verp_staffing.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "verp_staffing.install.before_install"
# after_install = "verp_staffing.install.after_install"
after_migrate = [
    # "verp_staffing.install.remove_default_workspaces",
    "verp_staffing.install.after_install",
    "verp_staffing.vrugle_staffing_erp.utils.quota.validate_required_lead_documents_config",
]

# Uninstallation
# ------------

# before_uninstall = "verp_staffing.uninstall.before_uninstall"
# after_uninstall = "verp_staffing.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "verp_staffing.utils.before_app_install"
# after_app_install = "verp_staffing.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "verp_staffing.utils.before_app_uninstall"
# after_app_uninstall = "verp_staffing.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "verp_staffing.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {"User": "verp_staffing.overrides.override_user.CustomUser"}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Resume": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    "RUC": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    "JDC": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    "Training": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    "Cover Letter": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    "Marketing": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    "Technical Other Services": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    "Marketing Other Services": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    "Other Services": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_service_update_hook"
    },
    # --- Payment Terms ---
    "Sales Order": {
        "on_update": "verp_staffing.accounts.utils.sales_order_status.on_sales_order_update_hook"
    },
    "User": {
        "before_insert": "verp_staffing.vrugle_staffing_erp.utils.quota.user_limit",
        "before_save": "verp_staffing.overrides.user.sync_employee_enabled_from_user",
    },
    "File": {
        "before_insert": "verp_staffing.vrugle_staffing_erp.utils.quota.site_space_limit",
    },
    "Agreement": {"on_submit": "verp_staffing.crm.api.agreement.generate_final_pdf"},
    "Employee": {
        "on_update": "verp_staffing.employee.api.workspace_automation.sync_user_workspace_roles",
        "before_save": "verp_staffing.employee.api.workspace_automation.sync_user_workspace_roles",
        "on_trash": "verp_staffing.employee.api.workspace_automation.remove_user_workspace_roles",
    },
    "Interview Status": {
        "after_insert": "verp_staffing.marketing.doctype.interview.interview.add_to_kanban",
        "on_trash": "verp_staffing.marketing.doctype.interview.interview.remove_from_kanban",
        "on_update": "verp_staffing.marketing.doctype.interview.interview.sync_kanban",
    }
}

# Scheduled Tasks
# ---------------

# files delete from "file" doctype, time : weekly on sunday at 1 am (depends on site_config.json)
# DB and file storage backup everyday morning, time : (depends on site_config.json)

scheduler_events = {
    "hourly": [
        "verp_staffing.vrugle_staffing_erp.utils.quota.site_expiry_check",
        "verp_staffing.vrugle_staffing_erp.utils.quota.block_non_admin",
    ],
    "daily": ["verp_staffing.vrugle_staffing_erp.utils.quota.check_site_expiry"],
    "cron": {
        "*/15 * * * *": ["verp_staffing.crm.api.event_remainders.send_event_reminders"],
        "0 0 * * *": [  # This cron expression runs daily at midnight
            "verp_staffing.crm.api.event_remainders.sendOpportunityClosingDateReminder"
        ],
    },
}

# Testing
# -------

# before_tests = "verp_staffing.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#     "frappe.desk.reportview.get": "verp_staffing.crm.api.helpers.secure_get"
# }
# set query permisson for doctype
permission_query_conditions = {
    "Customer": "verp_staffing.crm.api.helpers.customer_query",
    "Opportunity": "verp_staffing.crm.api.helpers.opportunity_query",
    "Lead": "verp_staffing.crm.api.helpers.lead_query",
    "Resume": "verp_staffing.crm.api.helpers.generic_assign_query",
    "RUC": "verp_staffing.crm.api.helpers.generic_assign_query",
    "Marketing": "verp_staffing.crm.api.helpers.generic_assign_query",
    "Training": "verp_staffing.crm.api.helpers.generic_assign_query",
    "JDC": "verp_staffing.crm.api.helpers.generic_assign_query",
    "Cover Letter": "verp_staffing.crm.api.helpers.generic_assign_query",
    "Technical Other Services": "verp_staffing.crm.api.helpers.generic_assign_query",
    "Marketing Other Services": "verp_staffing.crm.api.helpers.generic_assign_query",
}

# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
before_request = [
    "verp_staffing.vrugle_staffing_erp.utils.quota.site_expiry_check",
    "verp_staffing.vrugle_staffing_erp.utils.quota.block_non_admin",
]

# after_request = ["verp_staffing.utils.after_request"]

# Job Events
# ----------
# before_job = ["verp_staffing.utils.before_job"]
# after_job = ["verp_staffing.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"verp_staffing.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = [
    {
        "dt": "Kanban Board",
        "filters": [["kanban_board_name", "=", "Interview"]]
    },
    {
        "dt": "Custom HTML Block",
        "filters": [["name", "=", "Email Inbox"]]
    },
    {
        "dt": "Workspace",
        "filters": [["name", "=", "Email Inbox"]]
    },
]
