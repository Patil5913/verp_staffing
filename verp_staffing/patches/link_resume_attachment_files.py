import frappe


def execute():
    # Resume's document upload widget never set File.attached_to_doctype/
    # attached_to_name (see Resume.link_resume_attachments), so File
    # permission checks for existing resumes fall through to "deny everyone
    # but the uploader" regardless of Resume's has_permission hook. Back-fill
    # the link for every resume uploaded before that fix went in.
    rows = frappe.db.sql(
        """
        SELECT dr.parent AS resume_name, dr.document AS file_url
        FROM `tabDocument References` dr
        WHERE dr.parenttype = 'Resume'
          AND dr.parentfield = 'resume_table'
          AND IFNULL(dr.document, '') != ''
        """,
        as_dict=True,
    )

    for row in rows:
        file_name = frappe.db.get_value("File", {"file_url": row.file_url}, "name")
        if not file_name:
            continue

        frappe.db.set_value(
            "File",
            file_name,
            {"attached_to_doctype": "Resume", "attached_to_name": row.resume_name},
            update_modified=False,
        )
