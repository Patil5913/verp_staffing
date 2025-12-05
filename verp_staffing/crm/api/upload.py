import frappe
import base64
import uuid

@frappe.whitelist(allow_guest=True)
def upload_file(filename, filedata):
    try:
        base64_data = filedata.split(",")[-1]
        file_bytes = base64.b64decode(base64_data)

        unique_name = f"{uuid.uuid4()}-{filename}"

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": unique_name,
            "is_private": 0,  
            "content": file_bytes
        })
        file_doc.insert(ignore_permissions=True)

        return {
            "success": True,
            "file_url": file_doc.file_url,
            "file_name": file_doc.name
        }

    except Exception as e:
        frappe.log_error(f"Error in upload_file: {e}")
        return {
            "success": False,
            "error": str(e)
        }
