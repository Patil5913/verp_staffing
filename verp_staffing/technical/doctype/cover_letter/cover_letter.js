// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cover Letter", {
	async refresh(frm) {
		window.render_notes(frm);
		window.add_forward_button(frm);
		window.render_activity_section(frm);
		window.fetch_and_render_resume(frm);
		const display_fields = await window.get_display_fields(frm.doctype);

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
		}

		window.verp_staffing.render_document_references_table(frm, {
			fieldname: "proof_of_work",
			wrapper_field: "proof_of_work_html",
			show_fields: ["document", "document_title", "description", "date"],
			locked_statuses: ["Completed"],
		});

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: display_fields,
		});

		window.setup_service_permission_button(frm);
	},
});
