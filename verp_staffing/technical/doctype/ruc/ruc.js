// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("RUC", {
	async refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);
		window.fetch_and_render_resume(frm);

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
			frm.set_df_property("assign_to", "read_only", 1);
		}

		frappe.call({
			method: "verp_staffing.crm.doctype.customer.customer.get_employee_department",
			callback: (r) => {
				window.add_forward_button(frm);
			},
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "RUC";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: display_fields,
		});

		window.setup_service_permission_button(frm);
		
		frm.set_query("assign_to", () => {
			return {
				query: "verp_staffing.crm.api.helpers.get_assign_to_by_service",
				filters: {
					service: "RUC",
					customer: frm.doc.customer,
				},
			};
		});
	},

	customer(frm) {
		window.fetch_and_render_resume(frm);
	},
	status(frm) {
		frappe.call({
			method: "verp_staffing.crm.doctype.customer.customer.get_employee_department",
			callback: (r) => {
				window.add_forward_button(frm);
			},
		});
	},
});
