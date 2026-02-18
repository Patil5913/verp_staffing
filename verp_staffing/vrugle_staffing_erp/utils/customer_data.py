import frappe

@frappe.whitelist()
def get_data_by_customer(customer, fields):
    if not customer or not fields:
        return []
    
    if isinstance(fields, str):
        fields = frappe.parse_json(fields)
        
    source_doctype = "Lead Details"
    
    meta = frappe.get_meta(source_doctype)
    normal_fields = []
    table_fields = []
    
    for fieldname in fields:
        df = meta.get_field(fieldname)
        if not df:
            continue
        if df.fieldtype == "Table":
            table_fields.append(df)
        else:
            if frappe.db.has_column(source_doctype, fieldname):
                normal_fields.append(fieldname)
    
    if "name" not in normal_fields:
        normal_fields.append("name")
    
    parent_rows = frappe.get_all(
        source_doctype,
        fields=normal_fields,
        filters=[
            ["Doctype Reference", "reference_doctype", "=", "Customer"],
            ["Doctype Reference", "reference_person", "=", customer],
        ],
        order_by="creation desc",
        distinct=True
    )
    
    if not parent_rows:
        return []
    
    result = []
    for row in parent_rows:
        row_data = {
            "name": row.name,
            "fields": [],
            "tables": []
        }
        
        # ---------------- NORMAL FIELDS ----------------
        for f in normal_fields:
            if f == "name":
                continue
            df = meta.get_field(f)
            row_data["fields"].append({
                "fieldname": f,
                "label": df.label if df else f,
                "fieldtype": df.fieldtype if df else None,
                "options": df.options if df and hasattr(df, 'options') else None,  # Add options field
                "value": row.get(f)
            })
        
        # ---------------- TABLE FIELDS ----------------
        for df in table_fields:
            child_doctype = df.options
            child_meta = frappe.get_meta(child_doctype)
            
            columns = [
                {
                    "fieldname": cdf.fieldname,
                    "label": cdf.label,
                    "fieldtype": cdf.fieldtype
                }
                for cdf in child_meta.fields
                if cdf.fieldtype not in ("Section Break", "Column Break")
                and frappe.db.has_column(child_doctype, cdf.fieldname)
            ]
            
            child_rows = frappe.get_all(
                child_doctype,
                filters={
                    "parent": row.name,
                    "parenttype": source_doctype,
                    "parentfield": df.fieldname
                },
                fields=[c["fieldname"] for c in columns],
                order_by="idx asc"
            )
            
            row_data["tables"].append({
                "fieldname": df.fieldname,
                "label": df.label,
                "doctype": child_doctype,
                "columns": columns,
                "rows": child_rows
            })
        
        result.append(row_data)
    
    return result