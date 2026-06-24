// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing", {
	async refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);
		window.fetch_and_render_resume(frm);

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
		}

		frappe.call({
			method: "verp_staffing.marketing.doctype.marketing.marketing._is_superior_in_marketing",
			args: {
				assign_to: frm.doc.assign_to,
				current_user: frappe.session.user,
			},
			callback(r) {
				if (!r.message) return;
				const is_superior = r.message.is_superior;
				frm.set_df_property("target", "read_only", !is_superior);
				if(frm.doc.start_date){
					frm.set_df_property("start_date", "read_only", !is_superior);
				}
				const jobGrid = frm.fields_dict["job_application_count"].grid;
				jobGrid.update_docfield_property("date", "read_only", !is_superior);
				frm.refresh_field("target");
			},
			error(err) {
				console.error("Permission check failed", err);
			},
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Marketing";

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

		if (!frm.is_new()) {
			frm.set_df_property("customer", "read_only", 1);
		}
		window.setup_service_permission_button(frm);

		// to display the interview list
		render_interview_list(frm);

		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "customer_details_html",
			customer: frm.doc.customer,
			fields: display_fields,
		});

		window.setup_service_permission_button(frm);
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
	frappe.db.get_single_value("ERP Configuration", "default_interview_status").then((status) => {
		if (!status) {
			frappe.throw("Default Interview Status is not set in ERP Configuration");
		}

		const interview_doc = {
			doctype: "Interview",
			marketing_link: frm.doc.name,
			company: values.company,
			role: values.role,
			status: status, // dynamic now
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
