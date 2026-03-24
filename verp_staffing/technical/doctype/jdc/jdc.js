// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("JDC", {
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
				"old_resume",
			],
		});
		window.setup_service_permission_button(frm);
	},
});
