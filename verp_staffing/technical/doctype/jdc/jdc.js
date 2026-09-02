// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("JDC", {
	async refresh(frm) {
		window.render_notes(frm);
		window.add_forward_button(frm, service_name="JDC");
		window.render_activity_section(frm);
		window.fetch_and_render_resume(frm);
		const display_fields = await window.get_display_fields(frm.doctype);
		window.verp_staffing.render_interview_details(
			frm,
			frm.fields_dict.interview_details,
			frm.doc.interview_round,
		);
		if (frm.doc.interview_round) {
			frm.set_df_property("interview_round", "hidden", 1);
		}

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
			frm.set_df_property("assign_to", "read_only", 1);
		}

		window.verp_staffing.render_document_references_table(frm, {
			fieldname: "proof_of_work",
			wrapper_field: "proof_of_work_html",
			show_fields: ["document", "document_title", "description", "date"],
			locked_statuses: ["Completed"],
			status_field: "status",
		});

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: display_fields,
		});

		frm.set_query("assign_to", () => {
			return {
				query: "verp_staffing.crm.api.helpers.get_assign_to_by_service",
				filters: {
					service: "JDC",
					customer: frm.doc.customer,
				},
			};
		});
		window.setup_service_permission_button(frm);
	},
});
