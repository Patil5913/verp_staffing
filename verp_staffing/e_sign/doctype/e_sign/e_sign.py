# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

# import frappe
import frappe
import fitz
import uuid
from frappe.model.document import Document
from frappe.utils.file_manager import save_file
import random
from reportlab.pdfgen import canvas
from pdfrw import PdfReader, PdfWriter
from datetime import datetime, timezone
import os
from frappe.utils import now_datetime


class e_sign(Document):


    def validate(self):

        if not self.original_pdf:
            return

        file_doc = frappe.get_doc("File", {"file_url": self.original_pdf})

        # If already public → nothing to do
        if not file_doc.is_private:
            return

        # Read private file content
        private_path = file_doc.get_full_path()

        with open(private_path, "rb") as f:
            content = f.read()

        # Create NEW public file safely
        new_file = save_file(
            fname=file_doc.file_name,
            content=content,
            dt=self.doctype,
            dn=self.name,
            is_private=0
        )

        # Update field to new public file
        self.original_pdf = new_file.file_url

        # Optional: delete old private file record
        file_doc.delete(ignore_permissions=True)

@frappe.whitelist()
def generate_pdf_pages(docname):

    doc = frappe.get_doc("e_sign", docname)

    if not doc.original_pdf:
        return []

    file_path = frappe.get_site_path(
        doc.original_pdf.replace("/files/", "public/files/")
    )

    pdf = fitz.open(file_path)
    pages = []

    for i, page in enumerate(pdf):

        file_name = f"{docname}_page_{i+1}.png"

        # ✅ Check if file already exists
        existing_file = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": doc.doctype,
                "attached_to_name": doc.name,
                "file_name": file_name
            },
            fields=["file_url"],
            limit=1
        )

        if existing_file:
            # 🔁 Reuse existing image
            pages.append({
                "page_number": i + 1,
                "url": existing_file[0]["file_url"]
            })
            continue

        # 🚀 Only generate if not exists
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")

        file_doc = save_file(
            file_name,
            img_bytes,
            doc.doctype,
            doc.name,
            is_private=0
        )

        pages.append({
            "page_number": i + 1,
            "url": file_doc.file_url
        })

    pdf.close()

    return pages


def format_timestamp_utc():
    return now_datetime().strftime("%d-%m-%Y, %H:%M:%S UTC")

@frappe.whitelist(allow_guest=True)
def complete_signing(token=None, fields=None):

    if not token or not fields:
        frappe.throw("Missing data")

    import base64
    from frappe.utils.file_manager import save_file

    fields = frappe.parse_json(fields)

    # 1️⃣ Verification cookie check (same as your old function)
    verification_cookie = frappe.request.cookies.get(f"verify_{token}")

    if not verification_cookie:
        frappe.throw("Verification required")

    verified = frappe.db.exists(
        "Signature Fields",
        {
            "sign_token": token,
            "verification_key": verification_cookie
        }
    )

    if not verified:
        frappe.throw("Unauthorized access")

    # 2️⃣ Process each field
    for item in fields:

        field_name = item.get("field")
        field_type = item.get("type")
        image = item.get("image")

        if not field_name or not image:
            continue

        field = frappe.get_doc("Signature Fields", field_name)

        # decode base64 image
        header, encoded = image.split(",", 1)
        filedata = base64.b64decode(encoded)

        file_doc = save_file(
            f"{field_name}.png",
            filedata,
            field.doctype,
            field.name,
            is_private=0
        )

        field.signature_image = file_doc.file_url
        field.signed = 1
        field.signed_on = format_timestamp_utc()
        field.save(ignore_permissions=True)

    frappe.db.commit()

    # 3️⃣ Check if agreement complete
    agreement = frappe.get_doc("e_sign", field.parent)

    all_signed = all(row.signed for row in agreement.signature_fields)

    if all_signed:

        final_pdf_path = generate_final_signed_pdf(agreement.name)

        if final_pdf_path:
            try:
                generate_certificate_page(agreement.name)
                send_final_signed_email(agreement.name)
            except Exception as e:
                frappe.log_error(str(e), "Certificate Generation Error")

    return {
        "status": "success"
    }

@frappe.whitelist(allow_guest=True)
def save_signature(field_name=None, image=None, token=None):

    if not field_name or not image or not token:
        frappe.throw("Missing data")

    import base64
    from frappe.utils.file_manager import save_file
    from frappe.utils import now

    # 1️⃣ Get clicked field
    field = frappe.get_doc("Signature Fields", field_name)

    # 2️⃣ Security check
    if field.sign_token != token:
        frappe.throw("Invalid token")
        
    verification_cookie = frappe.request.cookies.get(f"verify_{token}")

    if not verification_cookie:
        frappe.throw("Verification required")

    verified = frappe.db.exists(
        "Signature Fields",
        {
            "sign_token": token,
            "verification_key": verification_cookie
        }
    )

    if not verified:
        frappe.throw("Unauthorized access")

    # 3️⃣ If already signed, stop
    if field.signed:
        return {"status": "already_signed"}

    # 4️⃣ Decode signature image
    header, encoded = image.split(",", 1)
    filedata = base64.b64decode(encoded)

    file_doc = save_file(
        f"signature_{token}.png",
        filedata,
        field.doctype,
        field.name,
        is_private=0
    )

    # 5️⃣ 🔥 IMPORTANT: Update ALL fields of this signer
    all_fields = frappe.get_all(
        "Signature Fields",
        filters={"sign_token": token},
        fields=["name"]
    )

    for row in all_fields:
        doc = frappe.get_doc("Signature Fields", row.name)
        doc.signature_image = file_doc.file_url
        doc.signed = 1
        doc.signed_on = format_timestamp_utc()  
        doc.save(ignore_permissions=True)

    frappe.db.commit()

        # 6️⃣ Check if ALL fields of agreement are signed
    agreement = frappe.get_doc("e_sign", field.parent)

    all_signed = all(row.signed for row in agreement.signature_fields)

    if all_signed:
      
        final_pdf_path = generate_final_signed_pdf(agreement.name)
    
        if final_pdf_path:
            try:
                generate_certificate_page(agreement.name)
                
                send_final_signed_email(agreement.name)
            except Exception as e:
                print(f"Error generating certificate: {e}")
        else:
            print("Failed to generate the final signed PDF.")
            
    
    return {
        "status": "success",
        "file_url": file_doc.file_url
    }

@frappe.whitelist()
def send_all_signers(agreement):
    
    print("------------------------------------------------------hi from server -------------------------------------------------")

    doc = frappe.get_doc("e_sign", agreement)

    unique_emails = list(set([
        row.signer_email for row in doc.signature_fields
        if row.signer_email
    ]))

    for email in unique_emails:

        token = str(uuid.uuid4())

        for row in doc.signature_fields:

            if row.signer_email == email:

                if not row.sign_token:
                    row.sign_token = token

                if not row.email_sent_on:
                    row.email_sent_on = format_timestamp_utc()

        link = f"{frappe.utils.get_url()}/sign_document?token={token}"

        frappe.sendmail(
            recipients=[email],
            subject="Please Sign Document",
            message=f"""
                <p>You have a document to sign.</p>
                <p><a href="{link}">Click here to Sign</a></p>
            """,
            delayed=False
        )

    doc.status = "Sent"

    doc.save(ignore_permissions=True)

    return "Emails Sent"

def send_final_signed_email(agreement_name):

    agreement = frappe.get_doc("e_sign", agreement_name)

    if not agreement.signed_pdf:
        frappe.log_error("Signed PDF not found", "Email Send Failed")
        return

    # Get final PDF full path
    file_path = frappe.get_site_path(
        agreement.signed_pdf.replace("/files/", "public/files/")
    )

    # Collect unique emails
    signer_emails = list(set([
        row.signer_email
        for row in agreement.signature_fields
        if row.signer_email
    ]))

    if not signer_emails:
        frappe.log_error("No signer emails found", "Email Send Failed")
        return

    # Read file once (important)
    with open(file_path, "rb") as f:
        pdf_content = f.read()

    # Send individually
    for email in signer_emails:

        frappe.sendmail(
            recipients=[email],  # single recipient
            subject="Final Signed Agreement",
            message=f"""
                <p>Hello,</p>

                <p>The agreement <b>{agreement.name}</b> has been fully signed.</p>

                <p>Please find the final signed document attached.</p>

                <br>
                <p>Thank you.</p>
            """,
            attachments=[{
                "fname": "Final_Signed_Agreement.pdf",
                "fcontent": pdf_content
            }],
            delayed=False
        )

    frappe.logger().info(f"Final signed emails sent for {agreement.name}")
    
@frappe.whitelist()
def send_signer_email(agreement, email):

    doc = frappe.get_doc("e_sign", agreement)

    # 1️⃣ Generate unique token
    token = str(uuid.uuid4())

    # 2️⃣ Save token in all boxes of this signer
    for row in doc.signature_fields:
        if row.signer_email == email:
            if row.sign_token is None: 
                row.sign_token = token
            else:
                token = row.sign_token
            if row.email_sent_on is None: 
                row.email_sent_on = format_timestamp_utc()
                
            

    doc.save(ignore_permissions=True)

    # 3️⃣ Create signing link
    link = f"{frappe.utils.get_url()}/sign_document?token={token}"

    # 4️⃣ Send email
    frappe.sendmail(
        recipients=[email],
        subject="Please Sign Document",
        message=f"""
            <p>You have a document to sign.</p>
            <p><a href="{link}">Click here to Sign</a></p>
        """,
        delayed=False
    )

    return "Email Sent Successfully"

def calculate_file_hash(file_path):
    import hashlib

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def generate_final_signed_pdf(agreement_name):

    agreement = frappe.get_doc("e_sign", agreement_name)

    if not agreement.original_pdf:
        return

    # 1️⃣ Load original PDF
    file_path = frappe.get_site_path(
        agreement.original_pdf.replace("/files/", "public/files/")
    )

    pdf = fitz.open(file_path)

    # 2️⃣ Loop through all signature fields
    for field in agreement.signature_fields:

        if not field.signature_image:
            continue

        if field.page_number < 1 or field.page_number > len(pdf):
            continue
        
        page = pdf[field.page_number - 1]

        # Convert percent to actual coordinates
        rect = page.rect

        x = rect.width * (field.x_percent / 100)
        y = rect.height * (field.y_percent / 100)
        w = rect.width * (field.width_percent / 100)
        h = rect.height * (field.height_percent / 100)

        image_path = frappe.get_site_path(
            field.signature_image.replace("/files/", "public/files/")
        )

        page.insert_image(
            fitz.Rect(x, y, x + w, y + h),
            filename=image_path
        )

    # 3️⃣ Save new signed PDF
    final_path = frappe.get_site_path(
        f"public/files/{agreement.name}_SIGNED.pdf"
    )

    pdf.save(final_path)
    pdf.close()

    # 4️⃣ Attach to doctype
    with open(final_path, "rb") as f:
        file_doc = save_file(
            f"{agreement.name}_SIGNED.pdf",
            f.read(),
            agreement.doctype,
            agreement.name,
            is_private=0
        )

    agreement.signed_pdf = file_doc.file_url
    agreement.status = "Fully Signed"
    agreement.save(ignore_permissions=True)

    frappe.db.commit()
    
    return {"status" : "final pdf upload"}
    

def generate_certificate_page(agreement_name):

    import os
    import io
    from PIL import Image
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from pdfrw import PdfReader, PdfWriter

    agreement = frappe.get_doc("e_sign", agreement_name)

    if not agreement.signed_pdf:
        return

    signed_path = frappe.get_site_path(
        agreement.signed_pdf.replace("/files/", "public/files/")
    )

    # -------------------------
    # GROUP UNIQUE SIGNERS
    # -------------------------
    unique_signers = {}
    for field in agreement.signature_fields:
        if field.signer_email not in unique_signers:
            unique_signers[field.signer_email] = field

    # -------------------------
    # CREATE CERTIFICATE PAGE
    # -------------------------
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)

    width, height = A4
    y = height - 50

    # Header
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, y, "Signature Certificate")
    y -= 40
    
    document_hash = calculate_file_hash(signed_path)

    # Agreement info
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Agreement ID: {agreement.name}")
    y -= 15
    
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Certificate ID: {document_hash}")
    y -= 30

    # -------------------------
    # SIGNERS LOOP
    # -------------------------
    for email, field in unique_signers.items():

        if y < 120:
            c.showPage()
            y = height - 50

        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"Email: {email}")
        y -= 15

        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Sent Time: {field.email_sent_on}")
        y -= 15

        c.drawString(50, y, f"Signed Time: {field.signed_on}")
        y -= 15
        
        c.drawString(50, y, f"Email Verified : {field.verified_on}")
        y -= 15

        # ⭐ Signature preview (FIXED)
        if field.signature_image:
            img_path = frappe.get_site_path(
                field.signature_image.replace("/files/", "public/files/")
            )

            if os.path.exists(img_path):
                img = Image.open(img_path)

                # Flatten transparency
                if img.mode in ("RGBA", "LA"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1])
                    img = bg
                else:
                    img = img.convert("RGB")

                c.drawImage(
                    ImageReader(img),
                    350,
                    y-20,
                    width=150,
                    height=50,
                    preserveAspectRatio=True,
                    mask=None
                )

        y -= 50

        # -------------------------
        # ACTIVITY PER SIGNER
        # -------------------------
        signer_activity = [a for a in agreement.activity if a.email == email]

        if signer_activity:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, "Activity")
            y -= 15

            c.setFont("Helvetica", 10)
            for act in signer_activity:

                if y < 100:
                    c.showPage()
                    y = height - 50

                c.drawString(60, y, f"IP: {act.ip_address}")
                y -= 12
                c.drawString(60, y, f"Visited: {act.visited_at}")
                y -= 15

        y -= 15

    c.save()
    packet.seek(0)

    cert_pdf = PdfReader(packet)

    # -------------------------
    # APPEND TO SIGNED PDF
    # -------------------------
    reader = PdfReader(signed_path)
    writer = PdfWriter()

    for p in reader.pages:
        writer.addpage(p)

    for p in cert_pdf.pages:
        writer.addpage(p)

    writer.write(signed_path)

@frappe.whitelist(allow_guest=True)
def track_ip_and_device(browser=None, os=None, device=None, token=None):

    if not token:
        return {"status": "invalid_token"}

    fields = frappe.get_all(
        "Signature Fields",
        filters={"sign_token": token},
        fields=["parent", "signer_email"]
    )

    if not fields:
        return {"status": "token_not_found"}

    agreement_name = fields[0]["parent"]
    signer_email = fields[0]["signer_email"]

    agreement = frappe.get_doc("e_sign", agreement_name)

    ip_address = frappe.local.request_ip

    agreement.append("activity", {
        "email": signer_email,
        "ip_address": ip_address,
        "browser": browser,
        "os": os,
        "device": device,
        "visited_at": format_timestamp_utc(),
        "agreement" : agreement_name
    })

    agreement.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success"}


@frappe.whitelist(allow_guest=True)
def send_otp(token=None):

    if not token:
        return {"status": "invalid_token"}

    fields = frappe.get_all(
        "Signature Fields",
        filters={"sign_token": token},
        fields=["parent", "signer_email"]
    )

    if not fields:
        return {"status": "token_not_found"}

    email = fields[0]["signer_email"]

    otp = str(random.randint(100000, 999999))

    frappe.cache().set_value(f"otp_{token}", otp, expires_in_sec=300)

    frappe.sendmail(
        recipients=[email],
        subject="Your Verification Code",
        message=f"<p>Your OTP is: <b>{otp}</b></p>",
        delayed = False
    )

    return {"status": "sent"}


@frappe.whitelist(allow_guest=True)
def verify_otp(token=None, otp=None):

    if not token or not otp:
        return {"status": "invalid_request"}

    cached_otp = frappe.cache().get_value(f"otp_{token}")

    if not cached_otp:
        return {"status": "expired"}

    if otp != cached_otp:
        return {"status": "invalid_otp"}

    # ✅ Generate persistent verification key
    verification_key = str(uuid.uuid4())

    # Save verification key to ALL fields of this signer
    rows = frappe.get_all(
        "Signature Fields",
        filters={"sign_token": token},
        fields=["name"]
    )

    for row in rows:
        doc = frappe.get_doc("Signature Fields", row.name)
        doc.verification_key = verification_key
        doc.verified_on = format_timestamp_utc()
        doc.save(ignore_permissions=True)

    frappe.db.commit()
    
    frappe.local.cookie_manager.set_cookie(
        key=f"verify_{token}",
        value=verification_key,
        max_age=60 * 60 * 24 * 7, # 7 days
        secure=True,              # Set to True in production (requires HTTPS)
        httponly=True,
        samesite="Lax"            # Required for modern browsers
        )

    frappe.cache().delete_value(f"otp_{token}")
    return {"status": "verified"}