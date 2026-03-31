frappe.ui.form.on("Resume", {
	async refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
		}

		if (frm.doc.status == "Completed") {
			window.add_forward_button(frm);
		}

		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: display_fields,
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Resume Form";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		window.setup_service_permission_button(frm);
	},

	status(frm) {
		if (frm.doc.status == "Completed") {
			window.add_forward_button(frm);
		}
	},
});
