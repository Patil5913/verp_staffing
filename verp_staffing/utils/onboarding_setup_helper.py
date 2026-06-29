import json

import frappe


def _has_non_empty_array_value(data: dict) -> bool:
    """
    Returns True if at least one key contains a non-empty array.
    """

    if not isinstance(data, dict):
        return False

    return any(isinstance(v, list) and len(v) > 0 for v in data.values())


def _safe_json_load(value):
    if not value:
        return {}

    try:
        return json.loads(value)
    except Exception:
        return {}


def has_employee_setup():
    return bool(frappe.db.exists("Employee", {}))


def has_pdf_agreement_template():
    return bool(frappe.db.exists("Pdf Agreement Template", {}))


def is_erp_configuration_complete():
    try:
        config = frappe.get_cached_doc(
            "ERP Configuration",
            "ERP Configuration",
        )

        if not config:
            return False

        # Required simple fields
        if not config.default_interview_status:
            return False

        if not config.expiry_hours_of_agreement:
            return False

        # Candidate Details Form Fields
        candidate_details = _safe_json_load(config.candidate_details_form_fields)
        candidate_setup_done = any(
            isinstance(v, dict)
            and isinstance(v.get("fields"), list)
            and len(v.get("fields")) > 0
            for v in candidate_details.values()
        )
        if not candidate_setup_done:
            return False

        # Department Display Form Fields
        display_fields = _safe_json_load(config.department_display_form_fields)

        if not _has_non_empty_array_value(display_fields):
            return False

        # Department Access Form Fields
        access_fields = _safe_json_load(config.department_access_form_fields)

        if not _has_non_empty_array_value(access_fields):
            return False

        return True
    except frappe.DoesNotExistError:
        return False


@frappe.whitelist()
def get_setup_progress():
    """
    Single source of truth for onboarding progress.
    Used by:
        - Setup Workspace
        - Employee Form
        - ERP Configuration Form
        - Future onboarding banners
    """
    steps = {
        "department": True,
        "hierarchy": True,
        "employee": has_employee_setup(),
        "erp_configuration": is_erp_configuration_complete(),
        "pdf_agreement_template": has_pdf_agreement_template(),
    }

    ordered_steps = [
        "department",
        "hierarchy",
        "employee",
        "erp_configuration",
        "pdf_agreement_template",
    ]

    current_step = "completed"

    for step in ordered_steps:
        if not steps[step]:
            current_step = step
            break

    completed_steps = sum(steps.values())

    total_steps = len(ordered_steps)

    progress_percentage = round((completed_steps / total_steps) * 100)

    next_actions = {
        "employee": {
            "label": "Create First Employee",
            "doctype": "Employee",
            "route": "/app/employee/new",
        },
        "erp_configuration": {
            "label": "Configure ERP Settings",
            "doctype": "ERP Configuration",
            "route": "/app/erp-configuration",
        },
        "pdf_agreement_template": {
            "label": "Create Agreement Template",
            "doctype": "Pdf Agreement Template",
            "route": "/app/pdf-agreement-template/new",
        },
        "completed": {
            "label": "Go To Dashboard",
            "route": "/app",
        },
    }

    return {
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "progress_percentage": progress_percentage,
        "current_step": current_step,
        "current_step_label": {
            "employee": "Create First Employee",
            "erp_configuration": "Configure ERP Settings",
            "pdf_agreement_template": "Create Agreement Template",
            "completed": "Setup Complete",
        }.get(current_step),
        "is_completed": current_step == "completed",
        "next_action": next_actions.get(current_step),
        "steps": steps,
    }

@frappe.whitelist()
def hide_setup_workspace():
    workspace = frappe.get_doc("Workspace", "Setup")
    workspace.is_hidden = 1
    workspace.save()