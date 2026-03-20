frappe.ui.form.on("Lead Detail Form", {
	refresh(frm) {
		apply_lead_detail_readonly(frm);
		update_parent_skills(frm);
		frm.toggle_enable("reference_table", false);
		check_candidate_form_required(frm);
	},

	onload(frm) {
		apply_lead_detail_readonly(frm);
	},

	additional_skills(frm) {
		update_parent_skills(frm);
	},

	surname(frm) {
		frm.trigger("update_title");
	},
	first_name(frm) {
		frm.trigger("update_title");
	},
	father_name(frm) {
		frm.trigger("update_title");
	},

	update_title(frm) {
		let full_name = [frm.doc.surname, frm.doc.first_name, frm.doc.father_name]
			.filter(Boolean)
			.join(" ");
		if (frm.fields_dict.title) {
			frm.set_value("title", full_name);
		}
	},
});

frappe.ui.form.on("Lead Past Experience", {
	skills(frm) {
		update_parent_skills(frm);
	},
	past_experience_table_add(frm) {
		setTimeout(() => update_parent_skills(frm), 0);
	},
	past_experience_table_remove(frm) {
		update_parent_skills(frm);
	},
});

function update_parent_skills(frm) {
	let manual_skills_raw = frm.doc.additional_skills || "";
	let manual_skills = manual_skills_raw
		.split(",")
		.map((s) => s.trim())
		.filter((s) => s.length > 0);
	let child_skills = [];

	(frm.doc.past_experience_table || []).forEach((row) => {
		if (!row.skills) return;
		row.skills.split(",").forEach((s) => {
			let clean = s.trim();
			if (clean) child_skills.push(clean);
		});
	});

	let merged = [...new Set([...manual_skills, ...child_skills])];
	frm.set_value("additional_skills", merged.join(", "));
}

// ── Handles Lead logic: lock email, first_name, surname for lead owner ──
function apply_lead_detail_readonly(frm) {
	if (!frm.doc.reference_table || !frm.doc.reference_table.length) return;

	const lead_row = frm.doc.reference_table.find((row) => row.reference_doctype === "Lead");
	if (!lead_row || !lead_row.reference_person) return;

	const lead_name = lead_row.reference_person;

	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Lead",
			filters: { name: lead_name },
			fieldname: ["status", "lead_owner"],
		},
		callback: function (r) {
			if (!r.message) return;
			const { status, lead_owner } = r.message;
			if (status !== "Opportunity") return;

			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Employee",
					filters: { user: frappe.session.user },
					fieldname: "name",
				},
				callback: function (emp) {
					if (!emp.message) return;
					if (emp.message.name !== lead_owner) return;

					// Lock name fields always
					frm.set_df_property("first_name", "read_only", 1);
					frm.set_df_property("surname", "read_only", 1);
					frm.refresh_field("first_name");
					frm.refresh_field("surname");

					// Lock/unlock email based on permission
					frappe.call({
						method: "verp_staffing.crm.api.permission_request._check_permission_status",
						args: {
							ref_doctype: "Lead", // ← always "Lead"
							ref_name: lead_name, // ← Lead name not frm.doc.name
						},
						callback: function (res) {
							const perm = res.message && res.message.status;
							const lock = perm !== "approved";
							frm.set_df_property("email", "read_only", lock ? 1 : 0);
							frm.refresh_field("email");
							if (!lock) {
								frappe.show_alert(
									{
										message: __(
											"Permission granted. You can now update the email field.",
										),
										indicator: "green",
									},
									5,
								);
							}
						},
					});
				},
			});
		},
	});
}

// ── Handles Customer/Sales Order logic: lock whole form based on Is Candidate Form Required ──
function check_candidate_form_required(frm) {
	if (frm.is_new()) return;

	// Try to find customer from reference_table first
	const customer_row = (frm.doc.reference_table || []).find(
		(row) => row.reference_doctype === "Customer",
	);

	if (customer_row && customer_row.reference_person) {
		// Direct customer reference — use it
		_apply_lock_from_customer(frm, customer_row.reference_person);
	} else {
		// No customer in reference_table — try to find via lead_detail_name
		// Pass lead_detail_name so Python can find the Customer
		if (!frm.doc.name || frm.doc.name === "new lead") return;

		frappe.call({
			method: "verp_staffing.crm.api.permission_request.get_lead_detail_form_lock_status",
			args: { lead_detail_name: frm.doc.name },
			callback: function (r) {
				if (!r.message) return;
				_handle_lock_response(frm, r.message);
			},
		});
	}
}

function _apply_lock_from_customer(frm, customer_name) {
	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_lead_detail_form_lock_status",
		args: { customer_name: customer_name },
		callback: function (r) {
			if (!r.message) return;
			_handle_lock_response(frm, r.message);
		},
	});
}

function _handle_lock_response(frm, message) {
	const { is_owner, candidate_form_required, permission } = message;

	// Only applies when candidate form is required AND user is the owner
	if (!candidate_form_required) return;
	if (!is_owner) return;

	if (permission === "approved") {
		_unlock_all_fields(frm);
		frappe.show_alert(
			{
				message: __("Permission granted. You can now edit this form."),
				indicator: "green",
			},
			5,
		);
	} else {
		_lock_all_fields(frm);

		let msg = __(
			"This form is locked. Request permission from the Customer form to make changes.",
		);
		if (permission === "pending") {
			msg = __("Form is locked. Your permission request is pending manager approval.");
		} else if (permission === "declined") {
			msg = __(
				"Form is locked. Your permission request was declined. Please request again from the Customer form.",
			);
		} else if (permission === "expired") {
			msg = __(
				"Form is locked. Your permission has expired. Please request again from the Customer form.",
			);
		}

		frappe.show_alert({ message: msg, indicator: "orange" }, 7);
	}
}

function _lock_all_fields(frm) {
	const skip_types = [
		"Section Break",
		"Column Break",
		"Tab Break",
		"HTML",
		"Button",
		"Fold",
		"Heading",
	];
	frm.fields.forEach(function (field) {
		if (skip_types.includes(field.df.fieldtype)) return;
		frm.set_df_property(field.df.fieldname, "read_only", 1);
	});
	frm.refresh_fields();
}

function _unlock_all_fields(frm) {
	const skip_types = [
		"Section Break",
		"Column Break",
		"Tab Break",
		"HTML",
		"Button",
		"Fold",
		"Heading",
	];
	frm.fields.forEach(function (field) {
		if (skip_types.includes(field.df.fieldtype)) return;
		frm.set_df_property(field.df.fieldname, "read_only", 0);
	});
	frm.refresh_fields();
}
