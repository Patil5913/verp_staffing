# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe, json
from frappe.utils.pdf import get_pdf
from frappe.utils.file_manager import save_file


class Agreement(Document):
	pass


def render_html_from_pdf_template(template_doc, data_dict):
    """
    Render pages from template_doc.fields_json which contains placed fields.
    For PDF preview we will take the original PDF as background image per page,
    then overlay absolute-positioned HTML blocks with values substituted.
    Finally wrap pages with page-break-after for PDF conversion.
    """
    fields = json.loads(template_doc.fields_json or "[]")
    # group fields by page
    pages_map = {}
    for f in fields:
        pages_map.setdefault(f['page'], []).append(f)

    # Build full HTML: for each page produce a div with background image (original file URL)
    # Use the uploaded file URL accessible via template_doc.upload_pdf_template
    pdf_url = template_doc.upload_pdf_template
    # Note: Using <img src="data:image/..."> would be heavier. We use absolute file URL.
    # We'll render one <div> per page and overlay fields using absolute positioning using pixel dimensions stored in fields.

    # we need page dimension info: we'll approximate from first page render ratio; if needed store page width/height.
    # For now we will treat coordinates in pixels and use CSS to set background-size: contain; position with percentage fallback.

    pages_html = []
    max_page = max([int(p) for p in pages_map.keys()]) if pages_map else 1

    for page_num in range(1, max_page + 1):
        page_fields = pages_map.get(page_num, [])

        # build overlay html for this page
        overlay = ""
        for f in page_fields:
            # fetch value from data_dict (fields filled from Sales Order)
            key = f.get("fieldname")
            val = data_dict.get(key, "")

            # use style absolute position using px assuming renderer will use same image natural width
            left = f.get("x", 0)
            top = f.get("y", 0)
            width = f.get("width", 150)
            height = f.get("height", 30)
            label = f.get("label") or key

            # Safely escape value
            val_html = frappe.utils.escape_html(str(val)) if val is not None else ""

            overlay += f'''
                <div style="
                    position:absolute;
                    left:{left}px;
                    top:{top}px;
                    width:{width}px;
                    height:{height}px;
                    border: none;
                    font-size: 12px;
                    background: transparent;
                    ">
                    {val_html}
                </div>
            '''

        # For background, we'll embed the page image via CSS background-image: url(pdf_url?page=page_num)
        # Note: not all PDF servers support page parameter. If not available, consider rendering canvases server-side.
        # Simpler approach: show the whole PDF as a large image (we assume client-side rendering used same images)
        pages_html.append(f'''
            <div class="agreement-page" style="position:relative; width:794px; min-height:1122px; margin:0 auto;">
                <img src="{pdf_url}#page={page_num}" style="width:794px; display:block;" />
                <div style="position:absolute; top:0; left:0; width:794px; height:1122px;">
                    {overlay}
                </div>
            </div>
            <div style="page-break-after: always;"></div>
        ''')

    full_html = f"""
    <html>
    <head><meta charset="utf-8">
    <style>
        body{{font-family: Arial, sans-serif; font-size:12px; margin:0; padding:0;}}
        .agreement-page img{{display:block;}}
    </style>
    </head>
    <body>
    {''.join(pages_html)}
    </body></html>
    """

    return full_html

@frappe.whitelist()
def render_preview(template, data):
    """
    template: name of Pdf Agreement Template doc
    data: JSON string of key => value (values filled in Sales Order agreement tab)
    """
    data_dict = json.loads(data) if isinstance(data, str) else data
    tpl = frappe.get_doc("Pdf Agreement Template", template)

    html = render_html_from_pdf_template(tpl, data_dict)
    pdf = get_pdf(html)
    fname = f"agreement_preview_{frappe.generate_hash(6)}.pdf"

    # Use File doc for preview (temporary)
    file = frappe.get_doc({
        "doctype": "File",
        "file_name": fname,
        "content": pdf,
        "is_private": 0
    })
    file.insert(ignore_permissions=True)
    return {"file_url": file.file_url}

@frappe.whitelist()
def create_and_send(sales_order, template, data):
    data_dict = json.loads(data) if isinstance(data, str) else data

    # Prevent duplicates
    if frappe.db.exists("Agreement", {"sales_order": sales_order}):
        frappe.throw("Agreement already exists for this Sales Order.")

    tpl = frappe.get_doc("Pdf Agreement Template", template)

    html = render_html_from_pdf_template(tpl, data_dict)
    pdf = get_pdf(html)
    fname = f"Agreement_{sales_order}.pdf"

    # create Agreement doc
    agreement = frappe.get_doc({
        "doctype": "Agreement",
        "sales_order": sales_order,
        "template": template,
        "data": json.dumps(data_dict),
        "status": "Locked"
    }).insert(ignore_permissions=True)

    # attach PDF permanently to Agreement using save_file
    # save_file(fname, content, dt, dn, folder=None, is_private=0)
    filedoc = save_file(fname, pdf, "Agreement", agreement.name, is_private=0)

    # simple email send (optional)
    so = frappe.get_doc("Sales Order", sales_order)
    recipient = getattr(so, "contact_email", None) or getattr(so, "customer_email", None)
    if recipient:
        frappe.sendmail(
            recipients=[recipient],
            subject=f"Agreement for {sales_order}",
            message="Please find attached agreement.",
            attachments=[{"fname": fname, "fcontent": pdf}]
        )

    frappe.db.commit()
    return {"agreement": agreement.name, "file_url": filedoc.file_url}

@frappe.whitelist()
def load_template_fields(template_name):
    tpl = frappe.get_doc("Pdf Agreement Template", template_name)
    return tpl.fields_json or "[]"