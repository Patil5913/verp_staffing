import json
import frappe


def execute():
    raw_config = frappe.db.get_single_value(
        "ERP Configuration", "candidate_details_form_fields"
    )
    if not raw_config:
        return

    try:
        data = json.loads(raw_config)
    except Exception:
        return

    if not isinstance(data, dict):
        return

    changed = False
    for service, cfg in data.items():
        if isinstance(cfg, list):
            # Legacy flat array format for a service
            new_fields = []
            for item in cfg:
                if isinstance(item, str):
                    new_fields.append({"field_name": item, "is_required": False})
                elif isinstance(item, dict):
                    fname = (
                        item.get("field_name")
                        or item.get("field")
                        or item.get("fieldname")
                    )
                    req = bool(item.get("is_required"))
                    if fname:
                        new_fields.append({"field_name": fname, "is_required": req})
            data[service] = {
                "fields": new_fields,
                "is_agreement_required": False,
                "is_candidate_form_required": False,
            }
            changed = True
        elif isinstance(cfg, dict):
            fields = cfg.get("fields", [])
            new_fields = []
            fields_changed = False
            for item in fields:
                if isinstance(item, str):
                    new_fields.append({"field_name": item, "is_required": False})
                    fields_changed = True
                elif isinstance(item, dict):
                    fname = (
                        item.get("field_name")
                        or item.get("field")
                        or item.get("fieldname")
                    )
                    req = bool(item.get("is_required"))
                    if fname:
                        new_fields.append({"field_name": fname, "is_required": req})
                    else:
                        new_fields.append(item)
                else:
                    new_fields.append(item)
            if fields_changed:
                cfg["fields"] = new_fields
                changed = True

    if changed:
        frappe.db.set_single_value(
            "ERP Configuration", "candidate_details_form_fields", json.dumps(data)
        )
