import os

import frappe
from frappe.utils.file_manager import get_content_hash

def resolve_file_path(file_url):
    if not file_url:
        return None

    fname = os.path.basename(file_url)

    private_path = frappe.get_site_path(
        "private",
        "files",
        fname,
    )

    if os.path.exists(private_path):
        return private_path

    public_path = frappe.get_site_path(
        "public",
        "files",
        fname,
    )

    if os.path.exists(public_path):
        return public_path

    return None


def execute():
    duplicate_files = frappe.db.sql(
        """
        SELECT
            file_url,
            COUNT(*) AS file_count
        FROM `tabFile`
        WHERE attached_to_doctype = 'Agreement'
          AND file_url IS NOT NULL
          AND file_url != ''
          AND LOWER(file_url) LIKE '%.pdf'
        GROUP BY file_url
        HAVING COUNT(*) > 1
        """,
        as_dict=True,
    )

    for row in duplicate_files:
        file_url = row.file_url

        file_path = resolve_file_path(file_url)

        if not file_path:
            frappe.log_error(
                title="Agreement PDF Hash Patch - File Not Found",
                message=(f"Unable to resolve PDF file.\nFile URL: {file_url}"),
            )
            continue

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            content_hash = get_content_hash(content)
            file_size = len(content)

            frappe.db.sql(
                """
                UPDATE `tabFile`
                SET
                    content_hash = %s,
                    file_size = %s
                WHERE attached_to_doctype = 'Agreement'
                  AND file_url = %s
                """,
                (
                    content_hash,
                    file_size,
                    file_url,
                ),
            )

        except Exception:
            frappe.log_error(
                title="Agreement PDF Hash Patch - Failed",
                message=frappe.get_traceback(),
            )
