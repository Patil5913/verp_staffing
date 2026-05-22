import re
from datetime import datetime

import frappe
from frappe.utils import cstr

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

def generate_name_series(doctype_name: str, name: str) -> str:
    """
    Generate a name series based on doctype name, given name, today's date, and occurrence count.
    
    Args:
        doctype_name (str): The name of the DocType (e.g., 'DocType')
        name (str): The name to search for (e.g., 'name')
    
    Returns:
        str: Generated series like 'DocType_name_25/03/2026' or 'DocType_name_25/03/2026_2'
    
    Examples:
        1st occurrence → DocType_name_25/03/2026
        2nd occurrence → DocType_name_25/03/2026_1
        3rd occurrence → DocType_name_25/03/2026_2
    """
    prefix = DOCTYPE_PREFIX_MAP.get(
        doctype_name,
        sanitize(doctype_name).upper(),
    )

    safe_name = sanitize(name)

    today = datetime.now().strftime("%d_%m_%Y")

    base_name = f"{prefix}_{safe_name}_{today}"

    # Fast path
    if not frappe.db.exists(doctype_name, base_name):
        return base_name

    counter = 1

    while True:

        candidate_name = f"{base_name}_{counter}"

        if not frappe.db.exists(
            doctype_name,
            candidate_name,
        ):
            return candidate_name

        counter += 1 # 2nd+ occurrence → append counter