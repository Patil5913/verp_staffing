// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("RUC", {
	refresh(frm) {
		window.render_notes(frm);
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

		frappe.call({
			method: "verp_staffing.crm.doctype.customer.customer.get_employee_department",
			callback: (r) => {
				window.add_forward_button(frm);
			},
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "RUC Form";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		frm._update_detail_fields = {
			surname: "Surname",
		};
		window.setup_service_permission_button(frm);
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
