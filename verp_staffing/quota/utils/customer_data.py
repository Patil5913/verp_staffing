import frappe
from collections import defaultdict


def get_cached_table_columns(child_doctype):
    cache = frappe.cache()
    cache_key = f"table_schema:{child_doctype}"

    columns = cache.get_value(cache_key)
    if columns is not None:
        return columns

    child_meta = frappe.get_meta(child_doctype)

    columns = [
        {
            "fieldname": df.fieldname,
            "label": df.label,
            "fieldtype": df.fieldtype,
        }
        for df in child_meta.fields
        if df.fieldtype not in ("Section Break", "Column Break")
        and frappe.db.has_column(child_doctype, df.fieldname)
    ]

    cache.set_value(
        cache_key,
        columns,
        expires_in_sec=3600,
    )

    return columns


@frappe.whitelist()
def get_data_by_customer(customer, fields):
    if not customer or not fields:
        return []

    if isinstance(fields, str):
        fields = frappe.parse_json(fields)

    source_doctype = "Lead Detail Form"
    meta = frappe.get_meta(source_doctype)

    normal_fields = []
    table_fields = []

    for fieldname in fields:
        df = meta.get_field(fieldname)

        if not df:
            continue

        if df.fieldtype == "Table":
            table_fields.append(df)
        elif frappe.db.has_column(source_doctype, fieldname):
            normal_fields.append(fieldname)

    if "name" not in normal_fields:
        normal_fields.append("name")

    parent_rows = frappe.get_all(
        source_doctype,
        fields=normal_fields,
        filters=[
            ["Doctype Reference", "reference_person", "=", customer],
        ],
        order_by="`tabLead Detail Form`.creation desc",
        distinct=True
    )

    if not parent_rows:
        return []

    parent_names = [row.name for row in parent_rows]

    # ------------------------------------------------------------------
    # Build field metadata once
    # ------------------------------------------------------------------

    field_meta = {}

    for fieldname in normal_fields:
        if fieldname == "name":
            continue

        df = meta.get_field(fieldname)

        field_meta[fieldname] = {
            "label": df.label if df else fieldname,
            "fieldtype": df.fieldtype if df else None,
            "options": df.options if df else None,
        }

    # ------------------------------------------------------------------
    # Fetch all child table data in bulk
    # ------------------------------------------------------------------

    table_data_map = {}

    for df in table_fields:
        child_doctype = df.options

        if not child_doctype:
            continue

        columns = get_cached_table_columns(child_doctype)

        fieldnames = [c["fieldname"] for c in columns]

        child_rows = frappe.get_all(
            child_doctype,
            filters={
                "parent": ["in", parent_names],
                "parenttype": source_doctype,
                "parentfield": df.fieldname,
            },
            fields=["parent"] + fieldnames,
            order_by="idx asc",
        )

        grouped_rows = defaultdict(list)

        for child_row in child_rows:
            grouped_rows[child_row.parent].append(child_row)

        table_data_map[df.fieldname] = {
            "label": df.label,
            "doctype": child_doctype,
            "columns": columns,
            "rows_by_parent": grouped_rows,
        }

    # ------------------------------------------------------------------
    # Build response
    # ------------------------------------------------------------------

    result = []

    for row in parent_rows:
        row_data = {
            "name": row.name,
            "fields": [],
            "tables": [],
        }

        for fieldname in normal_fields:
            if fieldname == "name":
                continue

            meta_info = field_meta[fieldname]

            row_data["fields"].append(
                {
                    "fieldname": fieldname,
                    "label": meta_info["label"],
                    "fieldtype": meta_info["fieldtype"],
                    "options": meta_info["options"],
                    "value": row.get(fieldname),
                }
            )

        for table_field in table_fields:
            table_info = table_data_map.get(table_field.fieldname)

            if not table_info:
                continue

            row_data["tables"].append(
                {
                    "fieldname": table_field.fieldname,
                    "label": table_info["label"],
                    "doctype": table_info["doctype"],
                    "columns": table_info["columns"],
                    "rows": table_info["rows_by_parent"].get(
                        row.name,
                        [],
                    ),
                }
            )

        result.append(row_data)

    return result