# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt
"""
Shared PDF field placement + drawing for the E Sign engine and the Pdf
Agreement Template flow, so a field lands on the exported PDF exactly where it
sat in the builder.

Coordinate contract: a field box is a fraction (0..1) of the page *as a viewer
shows it* - CropBox applied, /Rotate applied, origin top-left, y down. That is
what pdf.js renders in the builders, so the same numbers work in the browser
and here. Everything PDF-specific (non-zero MediaBox origin, CropBox, page
rotation) is handled in `PageGeometry`.
"""

import io
import os

import frappe
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

FONT_NAME = "Helvetica"
BASELINE_FROM_TOP = 0.85  # ascent share of the font size; matches the builders' line box


class PageGeometry:
    """Visible size of a PDF page and the transform from visual to user space."""

    def __init__(self, page):
        media = page.mediabox
        box = page.cropbox if page.get("/CropBox") is not None else media
        # A CropBox outside the MediaBox is clipped by viewers, pdf.js included.
        x0 = max(float(box.left), float(media.left))
        y0 = max(float(box.bottom), float(media.bottom))
        x1 = min(float(box.right), float(media.right))
        y1 = min(float(box.top), float(media.top))
        self.x0, self.y0 = x0, y0
        self.cw, self.ch = x1 - x0, y1 - y0  # unrotated crop size
        self.rotation = int(page.get("/Rotate", 0) or 0) % 360
        if self.rotation % 90:
            self.rotation = 0
        swap = self.rotation in (90, 270)
        self.width = self.ch if swap else self.cw  # visual size
        self.height = self.cw if swap else self.ch

    def rect(self, x_frac, y_frac, w_frac, h_frac):
        """Fractions of the visual page (top-left origin) -> (x, y, w, h) in
        points, bottom-left origin, inside the visual overlay canvas."""
        w = self.width * w_frac
        h = self.height * h_frac
        x = self.width * x_frac
        y = self.height - self.height * y_frac - h
        return x, y, w, h

    def overlay_transform(self):
        """Maps the visual overlay canvas onto the page's own user space."""
        cw, ch = self.cw, self.ch
        a, b, c, d, e, f = {
            0: (1, 0, 0, 1, 0, 0),
            90: (0, 1, -1, 0, cw, 0),
            180: (-1, 0, 0, -1, cw, ch),
            270: (0, -1, 1, 0, 0, ch),
        }[self.rotation]
        return Transformation((a, b, c, d, e + self.x0, f + self.y0))


def wrap_lines(text, width, font_size):
    """Greedy word wrap to `width` points, keeping explicit newlines; a word
    longer than the box is broken by characters."""

    def w(s):
        return stringWidth(s, FONT_NAME, font_size)

    lines = []
    for paragraph in str(text).replace("\r\n", "\n").split("\n"):
        current = ""
        for word in paragraph.split(" "):
            candidate = word if not current else f"{current} {word}"
            if w(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = ""
            while w(word) > width and len(word) > 1:
                cut = len(word) - 1
                while cut > 1 and w(word[:cut]) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines


def draw_text(c, value, x, y, w, h, font_size=12, line_height=1.0):
    """Wrapped text from the top-left of the box; lines that don't fit are dropped."""
    if value in (None, ""):
        return
    size = float(font_size or 12)
    step = size * float(line_height or 1.0)
    c.setFont(FONT_NAME, size)
    top = y + h
    for i, line in enumerate(wrap_lines(value, w, size)):
        if top - (i + 1) * step < y - 0.01:
            break
        if line:
            c.drawString(x, top - i * step - size * BASELINE_FROM_TOP, line)


def draw_checkbox(c, checked, x, y, w, h):
    size = min(w, h) * 0.8
    bx, by = x + (w - size) / 2, y + (h - size) / 2
    c.setLineWidth(max(0.6, size * 0.06))
    c.rect(bx, by, size, size, stroke=1, fill=0)
    if checked:
        c.line(bx + size * 0.2, by + size * 0.55, bx + size * 0.42, by + size * 0.25)
        c.line(bx + size * 0.42, by + size * 0.25, bx + size * 0.8, by + size * 0.8)


def is_checked(value):
    return str(value).strip().lower() in ("1", "true", "yes", "checked", "on")


def resolve_file_path(file_url):
    """Site path for a /files/ or /private/files/ URL, or None."""
    if not file_url:
        return None
    if file_url.startswith("/private/files/"):
        path = frappe.get_site_path(file_url.lstrip("/"))
    elif file_url.startswith("/files/"):
        path = frappe.get_site_path("public", file_url.lstrip("/"))
    else:
        path = file_url if os.path.isabs(file_url) else None
    return path if path and os.path.exists(path) else None


def draw_image_fit(c, image, x, y, w, h):
    """Draw an image scaled to fit the box, keeping its aspect ratio, left/centre aligned."""
    if isinstance(image, str):
        path = resolve_file_path(image) or image
        if not os.path.exists(path):
            return
        image = Image.open(path)
    iw, ih = image.size
    if not iw or not ih:
        return
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(ImageReader(image.convert("RGBA")), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, mask="auto")


def stamp_pdf(source_path, draw_page):
    """Overlay drawings on every page of `source_path` and return the PDF bytes.

    `draw_page(canvas, page_number, geometry)` draws into a canvas that is the
    size of the page as viewers show it (origin bottom-left, use
    `geometry.rect()` to place a field box).
    """
    reader = PdfReader(source_path)
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        geo = PageGeometry(page)
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(geo.width, geo.height))
        draw_page(c, index + 1, geo)
        c.showPage()
        c.save()
        packet.seek(0)
        overlay = PdfReader(packet).pages[0]
        page.merge_transformed_page(overlay, geo.overlay_transform())
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
