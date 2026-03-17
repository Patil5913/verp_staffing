frappe.ui.form.on("Lead Detail Form", {
	refresh(frm) {
		apply_lead_detail_readonly(frm);
		update_parent_skills(frm);
		frm.toggle_enable("reference_table", false);
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

function apply_lead_detail_readonly(frm) {
	// Find the linked Lead from reference_table
	if (!frm.doc.reference_table || !frm.doc.reference_table.length) return;

	const lead_row = frm.doc.reference_table.find((row) => row.reference_doctype === "Lead");

	if (!lead_row || !lead_row.reference_person) return;

	const lead_name = lead_row.reference_person;

	// Get Lead's status and lead_owner
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

			// Get logged-in user's Employee record
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Employee",
					filters: { user: frappe.session.user },
					fieldname: "name",
				},
				callback: function (emp) {
					if (!emp.message) return;

					const is_lead_owner = emp.message.name === lead_owner;

					if (!is_lead_owner) return;

					// Always lock first_name and surname for lead owner
					frm.set_df_property("first_name", "read_only", 1);
					frm.set_df_property("surname", "read_only", 1);
					frm.refresh_field("first_name");
					frm.refresh_field("surname");

					// For email — check if permission has been granted
					frappe.call({
						method: "verp_staffing.crm.api.permission_request.check_permission_status",
						args: { lead_name: lead_name },
						callback: function (res) {
							const permission_status = res.message && res.message.status;

							if (permission_status === "approved") {
								// Permission granted — unlock email
								frm.set_df_property("email", "read_only", 0);
								frm.refresh_field("email");

								frappe.show_alert(
									{
										message: __(
											"Your manager has granted permission. You can now update the email field.",
										),
										indicator: "green",
									},
									5,
								);
							} else {
								// No permission yet — lock email
								frm.set_df_property("email", "read_only", 1);
								frm.refresh_field("email");
							}
						},
						
					});
				},
			});
		},
	});
}
