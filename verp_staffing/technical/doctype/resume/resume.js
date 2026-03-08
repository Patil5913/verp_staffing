// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

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
                "old_resume"
            ]
        });
    },
    status(frm) {
        if (frm.doc.status == "Completed") {
            window.add_forward_button(frm);
        }
    }
});

function render_customer_details(frm) {
	const wrapper = frm.fields_dict.customer_details_html.$wrapper;

	if (!frm.doc.name) {
		wrapper.html(`<p class="text-muted">Customer not saved yet.</p>`);
		return;
	}

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Lead Detail Form",
			filters: {
				customer: frm.doc.customer,
			},
			limit_page_length: 1,
		},
		callback(r) {
			if (!r.message || !r.message.length) {
				wrapper.html(`
                    <div class="text-muted">
                        No Lead Details available for this customer.
                    </div>
                `);
				return;
			}

			const lead_name = r.message[0].name;

			frappe.call({
				method: "frappe.client.get",
				args: {
					doctype: "Lead Detail Form",
					name: lead_name,
				},
				callback(res) {
					if (!res.message) {
						wrapper.html(`<p class="text-muted">Unable to load Lead Details.</p>`);
						return;
					}

					const lead = res.message;

					const EXCLUDE_FIELDS = [
						"name",
						"doctype",
						"owner",
						"creation",
						"modified",
						"modified_by",
						"docstatus",
						"idx",
						"customer",
					];

					let html = `
                        <div style="padding:15px;">
                            <h4>Customer Details</h4>
                            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
                    `;

					Object.keys(lead).forEach((key) => {
						if (EXCLUDE_FIELDS.includes(key)) return;

						const value = lead[key];
						if (value === null || value === "") return;
						if (typeof value === "object") return;

						const df = frappe.meta.get_docfield("Lead Detail Form", key);
						const label = df?.label || frappe.model.unscrub(key);

						html += `
                            <div style="
                                border:1px solid #e5e5e5;
                                padding:10px;
                                border-radius:8px;
                                background:#fafafa;
                            ">
                                <strong>${label}</strong><br>
                                <span>${frappe.utils.escape_html(value)}</span>
                            </div>
                        `;
					});

					html += `</div></div>`;

					wrapper.html(html);
				},
			});
		},
	});
}
