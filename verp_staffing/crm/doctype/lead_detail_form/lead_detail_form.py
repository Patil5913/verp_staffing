# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document
# from frappe.utils import now_datetime
# import json


# class LeadDetailForm(Document):
# 	def before_save(self):
# 		self.capture_signer_identity()
# 		self.capture_signature_metadata()
# 		self.build_audit_trail()


# 	def capture_signer_identity(self):
# 		req = frappe.local.request

# 		# IP Address
# 		self.signer_ip = (
# 			frappe.get_request_header("X-Forwarded-For") or req.remote_addr
# 		)

# 		# Device fingerprint
# 		self.signer_user_agent = frappe.get_request_header("User-Agent")

# 		# Identity now based on entered fields
# 		self.signer_full_name = f"{self.first_name} {self.surname}".strip()
# 		self.signer_email = self.email
# 		self.signer_father_name = self.father_name

	
# 	def capture_signature_metadata(self):
# 		# Timestamp
# 		self.signature_timestamp = now_datetime()

# 		# Frappe Signature field type is always drawn
# 		self.signature_type = "drawn"

#         # Signature base64 is already in self.signature


# 	def build_audit_trail(self):
# 		events = []

# 		events.append({
#             "event": "document_opened",
#             "timestamp": now_datetime(),
#             "ip": self.signer_ip,
#             "user_agent": self.signer_user_agent
#         })

# 		events.append({
# 			"event": "consent_given",
#             "timestamp": now_datetime(),
#             "same_effect_handwritten": self.my_electronic_signature_has_same_effect_as_handwritten,
#             "consent_electronic": self.i_consent_to_receive_sign_and_store_documents_electronically,
#             "intentional_signing": self.i_confirm_my_identity_and_signing_this_document_intentionally
#         })

# 		events.append({
#             "event": "signature_completed",
#             "timestamp": self.signature_timestamp,
#             "signature_type": "drawn"
#         })

# 		# JSON String (NOT a list)
# 		self.audit_trail = json.dumps(events, default=str)

import frappe
from frappe.model.document import Document


class LeadDetailForm(Document):

    def before_save(self):
        import json
        from datetime import datetime

        # Load audit logs sent from JS
        audit_from_js = {}
        try:
            audit_from_js = json.loads(self.audit_trail) if self.audit_trail else {}
        except:
            audit_from_js = {}

        signature_logs = audit_from_js.get("signature update logs", [])
        form_logs = audit_from_js.get("form visit logs", [])

        # Add form submit event
        try:
            form_logs.append({
                "event": "form_submitted",
                "timestamp": datetime.now().strftime("%d-%m-%Y, %H:%M:%S")
            })
        except:
            pass

        # Build final cleaned audit structure
        final_audit = {}

        final_audit["signer location"] = {
            "ip": frappe.get_request_header("X-Forwarded-For") or frappe.local.request.remote_addr,
            "user_agent": frappe.get_request_header("User-Agent")
        }

        # Add signature logs ONLY IF not empty
        if signature_logs:
            final_audit["signature update logs"] = signature_logs

        final_audit["form visit logs"] = form_logs

        self.audit_trail = json.dumps(final_audit, indent=2)

