// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cover Letter", {
	async refresh(frm) {
		window.render_notes(frm);
		window.add_forward_button(frm);
		window.render_activity_section(frm);
		window.fetch_and_render_resume(frm);
		const [display_fields, access_fieldnames] = await Promise.all([
			window.get_display_fields(frm.doctype),
			window.get_access_fields(frm.doctype),
		]);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: display_fields,
		});
		if (access_fieldnames.length) {
			frm._update_detail_fields = _build_update_detail_fields(access_fieldnames);
		}
		window.setup_service_permission_button(frm);
	},
});
