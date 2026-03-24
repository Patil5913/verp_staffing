frappe.ui.form.on("Resume", {
	refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
		}

		if (frm.doc.status == "Completed") {
			window.add_forward_button(frm);
		}

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

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Resume Form";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		frm._update_detail_fields = {
			first_name: "First Name",
		};
		window.setup_service_permission_button(frm);
	},
	status(frm) {
		if (frm.doc.status == "Completed") {
			window.add_forward_button(frm);
		}
	},
});
