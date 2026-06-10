import frappe

@frappe.whitelist()
def _build_in_placeholders(prefix, items, values_dict):
    """
    Adds items to values_dict as %(prefix_0)s … %(prefix_N)s and returns the
    placeholder string for use inside an IN (...) clause.

    Handles the single-item tuple trailing-comma bug that breaks frappe.db.sql
    when you do `tuple([x])` → `('x',)` but MySQL sees `IN ('x',)`.
    """
    keys = []
    for i, item in enumerate(items):
        key = f"{prefix}_{i}"
        values_dict[key] = item
        keys.append(f"%({key})s")
    return ", ".join(keys)