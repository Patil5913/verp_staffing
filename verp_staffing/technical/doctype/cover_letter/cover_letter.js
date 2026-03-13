// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cover Letter", {
	refresh(frm) {
		window.render_notes(frm);
		window.add_forward_button(frm);
		window.render_activity_section(frm);
		window.fetch_and_render_resume(frm);
		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: [
				"surname",
				"first_name",
				"father_name",
				"personal_phone_number",
				"email",
				"personal_linkedin",
				"date_of_birth",
				"educational_details",
				"past_experience_table",
				"technologies",
				"additional_skills",
				"entry_date",
				"current_address",
				"address_history",
				"certificate_or_completed_course",
				"current_visa_status",
				"experience",
				"passport_number",
				"ssn_digit",
				"availability_for_interview",
				"remarks",
				"ead_card",
				"old_resume",
			],
		});
	},
});
