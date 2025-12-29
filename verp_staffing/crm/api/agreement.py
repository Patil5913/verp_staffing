import frappe, json, fitz
from frappe.utils.pdf import get_pdf
from frappe.utils.file_manager import save_file
import os
from verp_staffing.crm.api.helpers import send_notification


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
def preview_agreement(template, data):
    """
    Returns a temporary filled PDF (NOT saved in agreement)
    """
    frappe.errprint(f"Preview Agreement {template} with data {data}")
    data_dict = json.loads(data) if isinstance(data, str) else (data or {})
    tpl = frappe.get_doc("Pdf Agreement Template", template)

    # get fields
    try:
        fields = json.loads(tpl.fields_json or "[]")
    except Exception:
        fields = []

    # get local path of template upload
    if not tpl.upload_pdf_template:
        frappe.throw("Template has no uploaded PDF")

    # compute input file path
    # upload_pdf_template is typically "/files/xxx.pdf" or "files/xxx.pdf" or URL
    filename = os.path.basename(tpl.upload_pdf_template)
    input_pdf_path = frappe.get_site_path("public", "files", filename)
    if not os.path.exists(input_pdf_path):
        frappe.throw("Template PDF not found on disk")

    # payment_terms might be included in data_dict as list; ensure list
    payment_terms = data_dict.get("Payment_Terms") or []
    out_path, url = generate_pdf(
        input_pdf_path, fields, data_dict, payment_terms=payment_terms, save_final=False
    )

    # Save a temp File doc (preview)
    return {"file_url": url}


# Final submit
@frappe.whitelist()
def submit_and_generate(sales_order, template, data):
    """
    Generates final PDF and saves it permanently to the agreement doctype
    Only run when salesman clicks submit/send.
    """

    data_dict = json.loads(data) if isinstance(data, str) else (data or {})

    # Prevent duplicates
    if frappe.db.exists("Agreement", {"sales_order": sales_order}):
        frappe.throw("Agreement already exists for this Sales Order.")

    tpl = frappe.get_doc("Pdf Agreement Template", template)
    try:
        fields = json.loads(tpl.fields_json or "[]")
    except Exception:
        fields = []

    # input PDF
    if not tpl.upload_pdf_template:
        frappe.throw("Template has no uploaded PDF")
    filename = os.path.basename(tpl.upload_pdf_template)
    input_pdf_path = frappe.get_site_path("public", "files", filename)
    if not os.path.exists(input_pdf_path):
        frappe.throw("Template PDF not found on disk")

    # Collect payment_terms from Sales Order child table if not passed in data
    payment_terms = data_dict.get("Payment_Terms")

    out_path, url = generate_pdf(
        input_pdf_path, fields, data_dict, payment_terms=payment_terms, save_final=True
    )

    # Create Agreement doc
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

    agreement.db_set("pdf", url)

    # send email optionally
    try:
        so = frappe.get_doc("Sales Order", sales_order)
        recipient = getattr(so, "contact_email", None) or getattr(
            so, "customer_email", None
        )
        if recipient:
            frappe.sendmail(
                recipients=[recipient],
                subject=f"Agreement for {sales_order}",
                message="Please find attached agreement.",
                attachments=[
                    {
                        "fname": os.path.basename(url),
                        "fcontent": open(
                            frappe.get_site_path("public", url.lstrip("/")), "rb"
                        ).read(),
                    }
                ],
            )
    except Exception as e:
        frappe.log_error(message=f"Email send error: {e}", title="Agreement Email")

    frappe.db.commit()
    send_notification(
            recipients=[recipient],
            subject=f"Agreement Created.",
            message=(
                f"Agreement has been created please check the agreement and fill the form "
            ),
            send_email=1,
            send_system=0,
        )
    return {"agreement": agreement.name, "file_url": url}


def get_template_path(template):
    file_url = template.upload_pdf_template
    file_path = frappe.utils.get_files_path() + "/" + os.path.basename(file_url)
    return file_path


def generate_pdf(input_pdf_path, fields, data_dict, payment_terms, save_final=False):

    pdf = fitz.open(input_pdf_path)

    for f in fields:

        page_index = int(f.get("page", 1)) - 1
        if page_index < 0 or page_index >= len(pdf):
            continue

        page = pdf[page_index]
        page_rect = page.rect

        px_w = float(f.get("page_width") or 0)
        px_h = float(f.get("page_height") or 0)

        if not px_w or not px_h:
            frappe.throw("Missing page_width/page_height in field JSON")

        sx = page_rect.width / px_w
        sy = page_rect.height / px_h

        bx = float(f.get("x") or 0)
        by = float(f.get("y") or 0)
        bw = float(f.get("width") or 150)
        bh = float(f.get("height") or 30)

        tx = bx * sx
        ty = by * sy
        tw = bw * sx
        th = bh * sy

        rect = fitz.Rect(tx, ty, tx + tw, ty + th)

        name = f.get("name")
        val = data_dict.get(name, "")
        ftype = f.get("type", "Text")

        # EXISTING FIELD TYPES
        if ftype == "Checkbox":
            render_checkbox(page, rect, val)
        elif ftype == "Payment_Terms":
            val = data_dict.get(ftype, "")
            render_payment_terms_table(page, rect, val)
        elif ftype == "Signature":
            render_signature(page, rect, val)

        else:
            fontsize = max(8, int(th * 0.55))
            render_text(page, rect, str(val), fontsize=fontsize)

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


# Helpers for rendering different field types
# TEXT FIELD


def render_text(page, rect, text, fontsize=12):
    """
    Render wrapped and auto-fitted text using FreeText annotation only.
    """
    text = text or ""

    # Min/max font
    max_font = fontsize
    min_font = 6

    width = rect.width
    height = rect.height

    # A good baseline character width (PDF Helvetica)
    def char_width(font):
        return font * 0.45  # average Helvetica width

    # A good baseline line height
    def line_height(font):
        return font * 1.2

    # Try decreasing font until the text fits
    font = max_font
    while font >= min_font:

        cw = char_width(font)
        lh = line_height(font)

        max_chars = int(width / cw)
        max_lines = int(height / lh)

        # Estimate wrapped text
        wrapped_lines = []
        for word_block in text.split("\n"):
            words = word_block.split(" ")
            line = ""
            for w in words:
                if len(line + " " + w) <= max_chars:
                    line = (line + " " + w).strip()
                else:
                    wrapped_lines.append(line)
                    line = w
            if line:
                wrapped_lines.append(line)

        # Check if fits
        if len(wrapped_lines) <= max_lines:
            final_text = "\n".join(wrapped_lines)

            annot = page.add_freetext_annot(
                rect,
                final_text,
                fontsize=font,
                fontname="helv",
                text_color=(0, 0, 0),
                fill_color=None,
                align=0,
            )
            annot.update()
            return

        font -= 1

    # If nothing fits — render smallest possible text
    annot = page.add_freetext_annot(
        rect,
        text,
        fontsize=min_font,
        fontname="helv",
        text_color=(0, 0, 0),
        fill_color=None,
        align=0,
    )
    annot.update()


# CHECKBOX FIELD
def render_checkbox(page, rect, value):
    mark = "☑" if str(value).lower() in ("1", "true", "yes", "checked") else "☐"
    annot = page.add_freetext_annot(
        rect, mark, fontsize=14, fontname="helv", text_color=(0, 0, 0)
    )
    annot.update()


# SIGNATURE FIELD
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

def render_payment_terms_table(page, rect, terms):
    """
    Render a small table using annotations only.
    Includes debug logs via frappe.errprint to help diagnose coordinate / rotation problems.

    Approach
    - For each cell create a rect annotation (page.add_rect_annot)
      then create a freetext annotation for the cell text.
    - Use annot.set_colors and annot.set_border for visible borders.
    - Log page rect, rotation, input rect and actual annotation bbox to trace mismatches.
    - If results appear inverted try the 'flipped' fallback that maps top-origin -> bottom-origin.
    """

    # quick guard
    if not terms:
        render_text(page, rect, "No Payment Terms", fontsize=10)
        return

    try:
        frappe.errprint("render_payment_terms_table debug start")
        frappe.errprint(f"page.rect: {page.rect}")  # points
        try:
            # PyMuPDF exposes mediabox and rotation properties sometimes
            frappe.errprint(f"page.mediabox: {getattr(page, 'mediabox', None)}")
        except Exception:
            pass
        try:
            frappe.errprint(f"page_rotation: {getattr(page, 'rotation', None)}")
        except Exception:
            pass

        columns = ["Date", "Amount", "Received"]
        keys = ["date", "amount", "is_received"]

        col_count = len(columns)
        col_width = rect.width / col_count
        row_height = 20  # points; adjust if you want taller rows

        # Start at top of supplied rect (top-origin)
        y = rect.y0

        frappe.errprint(f"input rect: {rect}")
        frappe.errprint(f"col_width: {col_width}, row_height: {row_height}")

        def draw_cell_with_annots(cell_rect, text, font=9):
            """
            1) Create a visible rectangle annotation using add_rect_annot
            2) Then create a free text annotation inside the same rect for the content
            3) Log bbox values for debugging
            """
            # Create rect annot for border
            r_annot = page.add_rect_annot(cell_rect)
            # border width
            try:
                r_annot.set_border(width=0.6)
            except TypeError:
                # older/newer pyMuPDF variations
                try:
                    r_annot.set_border({"width": 0.6})
                except Exception:
                    pass
            # set stroke color
            try:
                r_annot.set_colors(stroke=(0, 0, 0))
            except Exception:
                # older versions might use set_color; attempt that
                try:
                    r_annot.set_color(stroke=(0, 0, 0))
                except Exception:
                    pass

            # ensure annot is written
            try:
                r_annot.update()
            except Exception:
                pass

            # Log rect and annot bbox
            try:
                frappe.errprint(f"draw_cell - cell_rect: {cell_rect}")
                frappe.errprint(f"draw_cell - rect_annot.bbox: {getattr(r_annot, 'bbox', getattr(r_annot, 'rect', None))}")
            except Exception:
                pass

            # Create freetext annot for text inside same rect
            # Small inset so text not touch border
            inset = 3
            text_rect = fitz.Rect(cell_rect.x0 + inset, cell_rect.y0 + inset, cell_rect.x1 - inset, cell_rect.y1 - inset)

            t_annot = page.add_freetext_annot(
                text_rect,
                str(text or ""),
                fontsize=font,
                fontname="helv",
                text_color=(0, 0, 0),
                fill_color=None,
                align=0,
            )
            try:
                t_annot.update()
            except Exception:
                pass

            # Log freetext bbox
            try:
                frappe.errprint(f"draw_cell - freetext.bbox: {getattr(t_annot, 'bbox', getattr(t_annot, 'rect', None))}")
            except Exception:
                pass

            return r_annot, t_annot

        # Render header row
        for idx, col in enumerate(columns):
            cell = fitz.Rect(
                rect.x0 + idx * col_width,
                y,
                rect.x0 + (idx + 1) * col_width,
                y + row_height,
            )
            draw_cell_with_annots(cell, col, font=10)

        y += row_height

        # Render body rows
        for row in terms:
            for idx, key in enumerate(keys):
                cell = fitz.Rect(
                    rect.x0 + idx * col_width,
                    y,
                    rect.x0 + (idx + 1) * col_width,
                    y + row_height,
                )

                value = row.get(key, "")
                if key == "is_received":
                    value = "Yes" if str(value).lower() in ("1", "true", "yes") else "No"

                draw_cell_with_annots(cell, value, font=9)

            y += row_height

        frappe.errprint("render_payment_terms_table debug end")

    except Exception as exc:
        # As last resort log exception so you can paste it here
        frappe.errprint(f"render_payment_terms_table exception: {exc}")
        # fallback: draw simple text to avoid failing the whole PDF
        render_text(page, rect, "Payment terms rendering failed", fontsize=10)
