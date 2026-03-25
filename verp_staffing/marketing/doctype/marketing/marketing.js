// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing", {
	refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);
		window.fetch_and_render_resume(frm);

		frappe.call({
			method: "verp_staffing.marketing.doctype.marketing.marketing.can_edit_marketing",
			args: {
				assign_to: frm.doc.assign_to,
			},
			callback(r) {
				if (!r.message) return;

				const canEdit = r.message.can_edit;
				const canDelete = r.message.can_delete;
				const canAdd = r.message.can_add;

				const targetGrid = frm.fields_dict["target"].grid;

				if (!targetGrid) return;

				targetGrid.docfields.forEach((field) => {
					targetGrid.update_docfield_property(
						field.fieldname,
						"read_only",
						canEdit ? 0 : 1,
					);
				});

				targetGrid.df.cannot_add_rows = !canAdd;
				targetGrid.df.cannot_delete_rows = !canDelete;

				frm.refresh_field("target");
			},
			error(err) {
				console.error("Permission check failed", err);
			},
		});

		frappe.call({
			method: "verp_staffing.marketing.doctype.marketing.marketing.can_edit_job_application_date",
			args: {
				assign_to: frm.doc.assign_to,
			},
			callback(r) {
				const canEditDate = r.message.can_edit_date;
				const jobGrid = frm.fields_dict["job_application_count"].grid;

				if (!canEditDate) {
					// ❌ Lock date field
					jobGrid.update_docfield_property("date", "read_only", 1);

					// 📅 Set default today date
					const today = frappe.datetime.get_today();

					frm.doc.job_application_count.forEach((row) => {
						if (!row.date) {
							row.date = today;
						}
					});
				} else {
					// ✅ Allow edit
					jobGrid.update_docfield_property("date", "read_only", 0);
				}

				frm.refresh_field("job_application_count");
			},
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Marketing Form";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		frm.add_custom_button(__("Create Interview"), () => {
			open_create_interview_dialog(frm);
		});

		frm.set_query("assign_to", () => {
			return {
				query: "verp_staffing.crm.api.helpers.get_subordinate_employees",
				filters: {
					department: "Marketing",
				},
			};
		});

		window.add_forward_button(frm);
		// to display the lead details
		window.render_customer_related_html({
			frm: frm,
			html_field: "customer_details_html",
			customer: frm.doc.customer,
			fields: [
				"surname",
				"first_name",
				"father_name",
				"personal_phone_number",
				"email",
				"number_for_marketing",
				"marketing_linkedin",
				"linkedin_password",
				"technologies",
				"ssn_digit",
				"date_of_birth",
				"current_address",
				"current_visa_status",
				"ead_card",
				"past_experience_table",
				"entry_date",
				"certificate_or_completed_course",
				"availability_for_interview",
				"driving_licence",
			],
		});

		if (!frm.is_new()) {
			frm.set_df_property("customer", "read_only", 1);
		}
		frm._update_detail_fields = {
			email: "Email",
		};
		window.setup_service_permission_button(frm);

		// to display the interview list
		render_interview_list(frm);
	},

	customer(frm) {
		frm.trigger("refresh");
	},
});

function handle_assign_to_permission(frm) {
	if (!frm.doc.assign_to) return;

	frappe.db.get_value("Employee", frm.doc.assign_to, "user").then((r) => {
		if (!r.message) return;

		const employee_user = r.message.user;

		if (frappe.session.user === employee_user) {
			frm.set_df_property("start_date", "read_only", 1);
			frm.set_df_property("target", "read_only", 1);
			frm.set_df_property("target_based_on", "read_only", 1);
			frm.refresh_field("start_date");
		} else {
			frm.set_df_property("start_date", "read_only", 0);
			frm.set_df_property("target", "read_only", 0);
			frm.set_df_property("target_based_on", "read_only", 0);
			frm.refresh_field("start_date");
		}
	});
}

frappe.ui.form.on("Job Application Count", {
	job_application_count_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.date) {
			row.date = frappe.datetime.get_today();
			frm.refresh_field("job_application_count");
		}
	},

	small_application(frm, cdt, cdn) {
		update_job_application_totals(frm, cdt, cdn);
	},

	large_application(frm, cdt, cdn) {
		update_job_application_totals(frm, cdt, cdn);
	},
});

function open_create_interview_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Create Interview"),
		fields: [
			{
				fieldname: "company",
				fieldtype: "Data",
				label: "Company",
				reqd: 1,
			},
			{
				fieldname: "role",
				fieldtype: "Data",
				label: "Role",
				reqd: 1,
			},
		],
		primary_action_label: __("Create Interview"),
		primary_action(values) {
			dialog.hide();
			create_interview(frm, values);
		},
	});

	dialog.show();
}

function create_interview(frm, values) {
	frappe.db.get_single_value("ERP Configuration", "default_interview_status")
		.then((status) => {

			if (!status) {
				frappe.throw("Default Interview Status is not set in ERP Configuration");
			}

			const interview_doc = {
				doctype: "Interview",
				marketing_link: frm.doc.name,
				company: values.company,
				role: values.role,
				status: status, // 🔥 dynamic now
			};

			frappe.call({
				method: "frappe.client.insert",
				args: {
					doc: interview_doc,
				},
				callback(r) {
					if (r.message) {
						frappe.msgprint({
							title: __("Success"),
							message: __("Interview Created Successfully"),
							indicator: "green",
						});

						frappe.set_route("Form", "Interview", r.message.name);
					}
				},
				error(err) {
					frappe.msgprint({
						title: __("Error"),
						message: err?.exc || __("Failed to create Interview"),
						indicator: "red",
					});
				},
			});
		});
}

function render_interview_list(frm) {
	if (!frm.doc.name) return;

	frappe.call({
		method: "verp_staffing.marketing.doctype.marketing.marketing.get_interviews_by_marketing",
		args: {
			marketing: frm.doc.name,
		},
		callback(r) {
			const data = r.message || [];

			if (!data.length) {
				frm.fields_dict.interview_list.$wrapper.html(
					"<div class='text-muted'>No interviews linked</div>",
				);
				return;
			}

			let html = "<ul style='padding-left:15px'>";

			data.forEach((d) => {
				html += `
                    <li>
                        <a href="#" data-interview="${d.company}">
                            ${d.company}
                        </a>
                    </li>
                `;
			});

			html += "</ul>";

			frm.fields_dict.interview_list.$wrapper.html(html);

			// Click handler
			frm.fields_dict.interview_list.$wrapper.find("a").on("click", function (e) {
				e.preventDefault();

				frappe.set_route("List", "Interview", "Kanban", { marketing_link: frm.doc.name });
			});
		},
	});
}

frappe.ui.form.on("Job Application Count", {
	job_application_count_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.date) {
			row.date = frappe.datetime.get_today();
			frm.refresh_field("job_application_count");
		}
	},

	small_application(frm, cdt, cdn) {
		update_job_application_totals(frm, cdt, cdn);
	},

	large_application(frm, cdt, cdn) {
		update_job_application_totals(frm, cdt, cdn);
	},
});

function update_job_application_totals(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	let small = flt(row.small_application);
	let large = flt(row.large_application);

	// Auto-calc only if at least one value exists
	if (small || large) {
		row.total_application = small + large;
		frm.refresh_field("job_application_count");
	}
}
