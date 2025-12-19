import frappe

@frappe.whitelist()
def get_data_by_customer(
    source_doctype,
    customer,
    fields
):
    """
    to collect wanted data of customer from source_doctype
    - source_doctype: str
    - customer: str
    - fields: list[str]
    """

    if not source_doctype or not customer or not fields:
        return []

    if isinstance(fields, str):
        fields = frappe.parse_json(fields)

    # Always include name for reference
    fields = list(set(fields + ["name"]))

    return frappe.get_all(
        source_doctype,
        filters={"customer": customer},
        fields=fields,
        order_by="creation desc"
    )
