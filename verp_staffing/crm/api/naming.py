import re
from datetime import datetime

# import frappe
from frappe.utils import cstr
from frappe.model.naming import getseries


DOCTYPE_PREFIX_MAP = {
    "Sales Order": "SO",
    "Other Services": "OS",
    "Technical Other Services": "TOS",
    "Cover Letter" : "CL",
    "Marketing Other Services" : "MOS",
    "Lead Detail Form" : "LDF"
}

def sanitize(value: str) -> str:
    """
    Convert text into safe naming token.
    """

    value = cstr(value).strip()

    return re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        value,
    ).strip("_")

def generate_name_series(
    doctype_name: str,
    name: str,
) -> str:
    """
    Generate a unique document name in the format:

        PREFIX_NAME_DD_MM_YYYY
        PREFIX_NAME_DD_MM_YYYY_1
        PREFIX_NAME_DD_MM_YYYY_2
        ...

    Uses Frappe's naming-series mechanism to safely
    generate unique suffixes without database calls in loops.
    """

    prefix = DOCTYPE_PREFIX_MAP.get(
        doctype_name,
        sanitize(doctype_name).upper(),
    )

    safe_name = sanitize(name)
    today = datetime.now().strftime("%d/%m/%Y")

    base_name = f"{prefix}_{safe_name}_{today}"

    series = int(
        getseries(
            f"{base_name}_",
            3,
        )
    )

    return (
        base_name
        if series == 1
        else f"{base_name}_{series - 1}"
    )