import frappe, json, fitz
from frappe.utils.pdf import get_pdf
from frappe.utils.file_manager import save_file
import os


@frappe.whitelist()
def create_and_send(sales_order, template, data):
    if frappe.db.exists("Agreement", {"sales_order": sales_order}):
        frappe.throw("Agreement already exists for this Sales Order.")

    tpl = frappe.get_doc("Agreement Template", template)
    data_dict = json.loads(data)

    # Create Agreement Doc
    agreement = frappe.get_doc(
        {
            "doctype": "Agreement",
            "sales_order": sales_order,
            "template": template,
            "data": json.dumps(data_dict),
            "status": "Locked",
        }
    ).insert(ignore_permissions=True)
    # attach agreement to sales order
    so = frappe.get_doc("Sales Order", sales_order)
    so.agreement = agreement.name

    so.save(ignore_permissions=True)
    # Generate PDF
    html = render_html_from_template(tpl, data_dict)
    pdf = get_pdf(html)

    # Attach PDF to Agreement
    fname = f"Agreement_{sales_order}.pdf"
    filedoc = save_file(
        fname,  # file name
        pdf,  # file bytes
        "Agreement",  # parent DocType
        agreement.name,  # parent docname
        is_private=0,
    )

    # Email to customer (optional)
    so = frappe.get_doc("Sales Order", sales_order)
    email = getattr(so, "contact_email", None)

    if email:
        frappe.sendmail(
            recipients=[email],
            subject=f"Agreement for {sales_order}",
            message="Please find attached your agreement.",
            attachments=[{"fname": fname, "fcontent": pdf}],
        )

    frappe.db.commit()

    return {"agreement": agreement.name, "pdf_url": filedoc.file_url}


@frappe.whitelist()
def download_agreement(agreement):
    doc = frappe.get_doc("Agreement", agreement)

    # If already generated, return saved file
    if doc.pdf:
        return {"file_url": doc.pdf}

    # If not generated yet → throw error (user must submit first)
    frappe.throw(
        "Agreement PDF is not generated yet. Please submit the agreement first."
    )


@frappe.whitelist()
def preview_agreement(template_name, data):
    """
    Returns a temporary filled PDF (NOT saved in agreement)
    """
    template = frappe.get_doc("Pdf Agreement Template", template_name)
    # agr = frappe.get_doc("Agreement", agreement)
    json_data = json.loads(data or "{}")
    fields = json.loads(template.fields_json or "[]")

    template_path = get_template_path(template)
    frappe.errprint(f"=====data==={json_data}\n =====fields===={fields}")
    pdf_path, url = generate_pdf(template_path, fields, json_data, save_final=False)

    return {"file_url": url}


# Final submit
@frappe.whitelist()
def submit_and_generate(sales_order, template, data):
    """
    Generates final PDF and saves it permanently to the agreement doctype
    Only run when salesman clicks submit/send.
    """
    # Create Agreement Doc
    data_dict = json.loads(data)
    agreement = frappe.get_doc(
        {
            "doctype": "Agreement",
            "sales_order": sales_order,
            "template": template,
            "data": json.dumps(data_dict),
            "status": "Locked",
        }
    ).insert(ignore_permissions=True)

    # attach agreement to sales order
    so = frappe.get_doc("Sales Order", sales_order)
    so.agreement = agreement.name

    so.save(ignore_permissions=True)

    template = frappe.get_doc("Pdf Agreement Template", template)

    fields = json.loads(template.fields_json or "[]")
    data = json.loads(agreement.data or "{}")
    template_path = get_template_path(template)

    pdf_path, url = generate_pdf(template_path, fields, data, save_final=True)

    # Save final URL in doctype

    agreement.db_set("pdf", url)

    return {"file_url": url}


def get_template_path(template):
    file_url = template.upload_pdf_template
    file_path = frappe.utils.get_files_path() + "/" + os.path.basename(file_url)
    frappe.errprint(f"============file_path==============: {file_path}")
    return file_path


# Generating pdf With canva and drawing using fitz
def generate_pdf(input_pdf_path, fields, data_dict, save_final=False):
    """
    ACCURATE PDF Generator for top-origin pixel based coordinates.
    Scaling is computed using actual PDF page size and builder pixel size.
    """

    pdf = fitz.open(input_pdf_path)

    for f in fields:

        page_index = int(f.get("page", 1)) - 1
        if page_index < 0 or page_index >= len(pdf):
            continue

        page = pdf[page_index]
        page_rect = page.rect

        # Builder page size (saved during field placement)
        px_w = float(f.get("page_width") or 0)
        px_h = float(f.get("page_height") or 0)

        if not px_w or not px_h:
            frappe.throw("Missing page_width/page_height in field JSON")

        # Compute PERFECT scale factors
        sx = page_rect.width / px_w
        sy = page_rect.height / px_h

        # Field coordinates from builder
        bx = float(f.get("x") or 0)
        by = float(f.get("y") or 0)
        bw = float(f.get("width") or 150)
        bh = float(f.get("height") or 30)

        # Convert top-origin px → top-origin PDF points
        tx = bx * sx
        ty = by * sy
        tw = bw * sx
        th = bh * sy

        rect = fitz.Rect(tx, ty, tx + tw, ty + th)

        # Fetch value
        name = f.get("name")
        val = data_dict.get(name, "")

        ftype = f.get("type", "Text")

        # --- Render fields ----
        if ftype == "Checkbox":
            render_checkbox(page, rect, val)

        elif ftype == "Signature":
            render_signature(page, rect, val)

        else:
            fontsize = max(8, int(th * 0.55))
            render_text(page, rect, str(val), fontsize=fontsize)

    # --- Save Result ---
    filename = f"agreement_{frappe.generate_hash(6)}.pdf"

    if save_final:
        out_path = frappe.utils.get_files_path(filename)
        url = f"/files/{filename}"
    else:
        tmp_dir = frappe.utils.get_files_path("tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        out_path = os.path.join(tmp_dir, filename)
        url = f"/files/tmp/{filename}"

    pdf.save(out_path)
    pdf.close()

    return out_path, url


# helpers


def render_text(page, rect, text, fontsize=12):
    annot = page.add_freetext_annot(
        rect,
        text,
        fontsize=fontsize,
        fontname="helv",
        text_color=(0, 0, 0),
        fill_color=None,
        align=0,
    )
    # Make annotation non-editable and normal looking
    annot.update()


def render_checkbox(page, rect, value):
    mark = "☑" if str(value).lower() in ("1", "true", "yes", "checked") else "☐"
    annot = page.add_freetext_annot(
        rect, mark, fontsize=14, fontname="helv", text_color=(0, 0, 0)
    )
    annot.update()


# can be used when webform is submitted and drawing signature to PDF
def render_signature(page, rect, file_url):
    if not file_url:
        return
    try:
        fn = os.path.basename(file_url)
        local_path = frappe.utils.get_files_path(fn)
        if not os.path.exists(local_path):
            local_path = frappe.get_site_path("public", "files", fn)
        if not os.path.exists(local_path):
            frappe.log_error(f"Signature file not found: {file_url}", "Agreement PDF")
            return

        img_bytes = open(local_path, "rb").read()

        page.insert_image(rect, stream=img_bytes)
    except Exception as e:
        frappe.log_error(
            message=f"render_signature error: {e}\nfile_url: {file_url}",
            title="Agreement PDF",
        )
