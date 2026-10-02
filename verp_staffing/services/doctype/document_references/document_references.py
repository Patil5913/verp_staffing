# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import os


class DocumentReferences(Document):
	pass

def get_document_title(file_url):
    """
    Return a document title from a file URL/path.

    Example:
        /files/My_Resume.pdf
        -> My_Resume.pdf
    """

    if not file_url:
        return ""

    file_url = file_url.split("?")[0]

    return os.path.basename(file_url)

def set_document_reference_titles(rows):
    """
    Populate document_title for Document References rows
    where a document exists and document_title is empty.
    """

    for row in rows or []:
        if row.document and not row.document_title:
            row.document_title = get_document_title(row.document)