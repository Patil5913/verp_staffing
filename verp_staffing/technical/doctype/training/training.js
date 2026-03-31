// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Training", {
	async refresh(frm) {
		window.render_notes(frm);
		window.fetch_and_render_resume(frm);
		window.add_forward_button(frm);
		window.render_activity_section(frm);
		
		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: display_fields,
		});
		
		window.setup_service_permission_button(frm);
	},
});
