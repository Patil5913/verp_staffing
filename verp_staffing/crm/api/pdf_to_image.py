import frappe

@frappe.whitelist(allow_guest=True)
def pdf_to_images(path):
    import fitz  # PyMuPDF
    import frappe
    import base64

    file_path = frappe.get_site_path("public", path)

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
