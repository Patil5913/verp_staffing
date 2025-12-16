import frappe

@frappe.whitelist(allow_guest=True)
def pdf_to_images(path):
    import fitz  # PyMuPDF
    import base64
    import os

    if not path:
        frappe.throw("PDF path not provided")

    # strip leading slash and `files/`
    if path.startswith("/files/"):
        filename = path.replace("/files/", "", 1)
    else:
        filename = path

    file_path = frappe.get_site_path("public", "files", filename)

    if not os.path.exists(file_path):
        frappe.throw(f"PDF file not found at {file_path}")


    doc = fitz.open(file_path)
    images = []

    # High resolution scaling (2 = 144 DPI, 3 = 216 DPI, 4 = 288 DPI)
    zoom = 3  # adjust if needed
    mat = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        images.append("data:image/png;base64," + base64.b64encode(img_bytes).decode())

    return images
