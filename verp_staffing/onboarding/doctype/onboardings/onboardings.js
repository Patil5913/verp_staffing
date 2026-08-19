// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt
let interview_offset = 0;
const interview_limit = 5;

frappe.ui.form.on("Onboardings", {
	setup(frm) {
		$(frm.wrapper).on("shown.bs.tab", ".nav-link", () => {
			render_tab_data(frm);
		});
	},

	refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Onboarding",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();
		showOnboarding_data(frm);

		if (frm.doc.status === "Completed") {
			frm.disable_form();
			frm.disable_save();
		}
		window.add_forward_button(frm);
		render_tab_data(frm);
		frm.set_query("assign_to", () => {
			return {
				query: "verp_staffing.crm.api.helpers.get_subordinate_employees",
				filters: {
					department: "Onboarding",
				},
			};
		});
	},
	sales_order: function (frm) {
		frappe.new_doc("Sales Order", { customer: frm.doc.customer });
	},
	status: function (frm) {
		if (frm.doc.status === "Completed") {
			frappe.confirm(
				"Marking this as Completed cannot be undone. Proceed?",
				() => {
					// User clicked 'Yes'
					frm.set_df_property("status", "read_only", 1);
					frm.save();
				},
				() => {
					// User clicked 'No' - Revert to previous value
					// frm.doc.__onsave holds values from the last save
					let previous_status = frm.doc.__onsave ? frm.doc.__onsave.status : "Draft";
					frm.set_value("status", previous_status);
				},
			);
		}
	},
});

function render_tab_data(frm) {
	if (frm.is_new()) return;
	const active_tab = frm.active_tab_map && frm.active_tab_map[frm.doc.name];
	if (active_tab.df.fieldname === "history_tab") {
		load_customer_history_if_needed(frm);
	} else if (active_tab.df.fieldname === "sales_order_tab") {
		window.render_owned_sales_orders(frm, "sales_content", frm.doc.customer);
	} else if (active_tab.df.fieldname === "customer_information_tab") {
		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details_html",
			customer: frm.doc.customer,
			fields: [
				"agreement_link",
				"signature_image",
				"my_electronic_signature_has_same_effect_as_handwritten",
				"i_consent_to_receive_sign_and_store_documents_electronically",
				"i_confirm_my_identity_and_signing_this_document_intentionally",
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
				"number_for_marketing",
				"google_voice_number",
				"marketing_linkedin",
				"passport_number",
				"ssn_digit",
				"availability_for_interview",
				"remarks",
				"visa_copy",
				"ead_card",
				"driving_licence",
				"old_resume",
			],
		});
	}
}

function load_customer_history_if_needed(frm) {
	if (!frm.doc.customer) return;
	if (frm.__history_loaded_for === frm.doc.name) return; // already loaded for this doc

	frm.__history_loaded_for = frm.doc.name;

	if (frm.fields_dict.customer_details) {
		frm.fields_dict.customer_details.$wrapper.html(
			"<p style='color:#888'>Loading history...</p>",
		);
	}

	window.verp_staffing.render_customer_history_widget(frm, {
		fieldname: "customer_details",
		customer: frm.doc.customer,
		doctype: "Customer",
	});
}

function showOnboarding_data(frm) {
	if (!frm.doc.customer) return;

	frappe.call({
		method: "verp_staffing.onboarding.doctype.onboardings.onboardings.get_after_placement_details",
		args: {
			customer: frm.doc.customer,
		},
		callback(r) {
			const data = r.message;

			if (!data || !data.position) {
				frm.fields_dict.after_placement_details.$wrapper.html(
					"<div style='color:#888'>No placement details available</div>",
				);
				return;
			}

			const html = `
				<div style="padding:10px">
					<p><b>Position:</b> ${data.position}</p>
					<p><b>Placement Company:</b> ${data.placement_company}</p>
					<p><b>Job Duration:</b> ${data.job_duration}</p>
					<p><b>Salary:</b> ${data.salary}</p>

					<div style="margin-top:10px">
						<label><b>Company Percentage</b></label>
						<input 
							type="number" 
							id="company_percentage_input"
							value="${data.company_percentage || 0}"
							style="width:100%; padding:6px; margin-top:4px"
						/>
					</div>

					<button 
						class="btn btn-primary"
						style="margin-top:10px"
						id="save_company_percentage"
					>
						Save
					</button>
				</div>
			`;

			const wrapper = frm.fields_dict.after_placement_details.$wrapper;

			wrapper.html(html);

			// bind click
			wrapper.off("click", "#save_company_percentage");

			wrapper.on("click", "#save_company_percentage", function () {
				const value = wrapper.find("#company_percentage_input").val();

				if (!value) {
					frappe.msgprint("Company Percentage is required");
					return;
				}

				frappe.call({
					method: "verp_staffing.crm.doctype.customer.customer.update_company_percentage",
					args: {
						lead_name: data.lead_name,
						company_percentage: value,
					},
					callback() {
						frappe.msgprint("Updated successfully");
						frm.refresh();
					},
				});
			});
		},
	});
}
