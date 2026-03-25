import frappe
from datetime import datetime

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
    today = datetime.today().strftime("%d/%m/%Y")
    base_series = f"{doctype_name}_{name}_{today}"

    # Count how many docs in the doctype have this name
    count = frappe.db.count(doctype_name, filters={"name": ["like", f"%{name}%"]})

    if count == 0:
        return base_series                  # 1st occurrence → no counter
    else:
        return f"{base_series}_{count}"     # 2nd+ occurrence → append counter