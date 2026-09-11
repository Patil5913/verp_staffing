// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Onboardings", {
	setup(frm) {
		$(frm.wrapper).on("shown.bs.tab", ".nav-link", () => {
			render_tab_data(frm);
		});
	},
	refresh(frm) {
		frappe.breadcrumbs.clear();
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Onboarding",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();
		render_tab_data(frm);

		if (frm.doc.status !== "Active") {
			frm.disable_form();
		} else if (frm.doc.status === "Returned") {
			window.add_forward_button(frm, (service_name = "Onboarding"));
		}

		const assign_to_query = () => ({
			query: "verp_staffing.crm.api.helpers.get_subordinate_employees",
			filters: { department: "Onboarding" },
		});
		frm.set_query("assign_to", assign_to_query);
		frm.set_query("assign_to", "onboarding_history", assign_to_query);

		lock_history_grid(frm);
		add_resolution_buttons(frm);
	},
	sales_order: function (frm) {
		frappe.new_doc("Sales Order", { customer: frm.doc.customer });
	},
});

function get_latest_onboarding_history_row(rows) {
	if (!rows || !rows.length) return null;
	return rows.reduce((latest, row) => {
		if (!latest) return row;
		const a = row.forwarded_on ? new Date(row.forwarded_on) : new Date(0);
		const b = latest.forwarded_on ? new Date(latest.forwarded_on) : new Date(0);
		if (a > b) return row;
		if (a.getTime() === b.getTime() && row.idx > latest.idx) return row;
		return latest;
	}, null);
}

function lock_history_grid(frm) {
	const grid = frm.fields_dict.onboarding_history.grid;

	grid.cannot_add_rows = true;
	grid.df.cannot_delete_rows = true;
	grid.refresh();
}

function patch_onboarding_history_row_actions(grid) {
	if (grid.__onboarding_history_drag_patched) return;
	grid.__onboarding_history_drag_patched = true;

	["mousedown", "touchstart"].forEach((evt) => {
		grid.wrapper.on(evt, ".sortable-handle, .row-index", function (e) {
			if (grid.wrapper.hasClass("onboarding-history-reorder-locked")) {
				e.stopImmediatePropagation();
				e.preventDefault();
				return false;
			}
		});
	});
}

function add_resolution_buttons(frm) {
	if (frm.is_new() || !frm.doc.onboarding_history || !frm.doc.onboarding_history.length) return;

	const latest = get_latest_onboarding_history_row(frm.doc.onboarding_history);
	if (!latest || latest.status !== "Active") return;

	frm.add_custom_button("Mark Completed", () => confirm_resolution(frm, "Completed"), "Actions");
	frm.add_custom_button("Mark Returned", () => confirm_resolution(frm, "Returned"), "Actions");
}

function confirm_resolution(frm, action) {
	frappe.confirm(`Mark this Onboarding as ${action}? This cannot be undone.`, () => {
		frappe.call({
			method: "verp_staffing.onboarding.doctype.onboardings.onboardings.resolve_onboarding",
			args: { onboarding_name: frm.doc.name, action: action },
			callback() {
				frm.reload_doc();
			},
		});
	});
}

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
				"marketing_email_id",
				"marketing_email_password",
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
	if (frm.__history_loaded_for === frm.doc.name) return;
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
