// Copyright (c) 2025, Vrugle and contributors

frappe.ui.form.on("Employee", {
	async refresh(frm) {
		await apply_employee_read_only_restriction(frm);

		frm.set_query("user", () => {
			return {
				query: "verp_staffing.employee.doctype.employee.employee.get_users_not_linked_to_employee",
			};
		});
		if(frappe.session.user === "Administrator"){
			await render_headline(frm);
		}
		const has_sales_department = (frm.doc.employee_assignment_details_table || []).some(
			(row) => row.department === "Sales",
		);

		if (has_sales_department) {
			frm.add_custom_button("Revenue Report", () => {
				if (!frm.doc.name) {
					frappe.msgprint("Please save the Employee first");
					return;
				}

				frappe.set_route("query-report", "Revenue Of Employee", {
					employee: frm.doc.name,
				});
			});
		}
		toggle_linkedin_section(frm);
		toggle_revenue_target_section(frm);

		if (!frm._department_hierarchy) {
			frm._department_hierarchy = {};
		}

		const rows = frm.doc.employee_assignment_details_table || [];
		const departments = [...new Set(rows.map((r) => r.department).filter(Boolean))];

		for (const dept of departments) {
			if (frm._department_hierarchy[dept]) continue;

			try {
				const r = await frappe.call({
					method: "frappe.client.get",
					args: {
						doctype: "Hierarchy",
						name: dept,
					},
				});

				if (r.message?.role_hierarchy_json) {
					frm._department_hierarchy[dept] = JSON.parse(r.message.role_hierarchy_json);
				}
			} catch (e) {
				console.error("Failed to load hierarchy", dept, e);
			}
		}

		// -------------------------------
		// DEPARTMENT UNIQUE FILTER
		// -------------------------------
		frm.fields_dict.employee_assignment_details_table.grid.get_field("department").get_query =
			function (doc, cdt, cdn) {
				const row = locals[cdt][cdn];

				let selected_departments = (frm.doc.employee_assignment_details_table || [])
					.filter((d) => d.name !== row.name)
					.map((d) => d.department)
					.filter(Boolean);

				if (!selected_departments.length) return {};

				return {
					filters: {
						name: ["not in", selected_departments],
					},
				};
			};

		frm.fields_dict.employee_assignment_details_table.grid.get_field("designation").get_query =
			function (doc, cdt, cdn) {
				const row = locals[cdt][cdn];

				if (!row.department) return {};

				const hierarchy = frm._department_hierarchy?.[row.department];
				if (!hierarchy) return {}; // avoid race condition

				let roles = new Set();

				hierarchy.forEach((r) => {
					if (r.parent_role) roles.add(r.parent_role);
					if (Array.isArray(r.child_roles)) {
						r.child_roles.forEach((cr) => roles.add(cr));
					}
				});

				let role_list = Array.from(roles);

				// remove already selected roles in other rows
				let selected_roles = (frm.doc.employee_assignment_details_table || [])
					.filter((d) => d.name !== row.name)
					.map((d) => d.designation)
					.filter(Boolean);

				role_list = role_list.filter((role) => !selected_roles.includes(role));

				return {
					filters: {
						name: ["in", role_list],
					},
				};
			};

		frm.fields_dict.employee_assignment_details_table.grid.get_field("assigned_to").get_query =
			function (doc, cdt, cdn) {
				const row = locals[cdt][cdn];

				if (!row.department || !row.designation) {
					return { filters: { name: ["=", ""] } };
				}

				const hierarchy = frm._department_hierarchy?.[row.department];
				if (!hierarchy) {
					return { filters: { name: ["=", ""] } };
				}
				const parent_roles = hierarchy
					.filter(
						(r) =>
							Array.isArray(r.child_roles) &&
							r.child_roles.includes(row.designation),
					)
					.map((r) => r.parent_role);
				if (!parent_roles.length) {
					return { filters: { name: ["=", ""] } };
				}

				return {
					query: "verp_staffing.employee.doctype.employee.employee.get_employees_by_assignment",
					filters: {
						department: row.department,
						designation: parent_roles,
					},
				};
			};

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Employee";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
	},

	validate(frm) {
		(frm.doc.employee_assignment_details_table || []).forEach((row) => {
			if (!row.department || !row.designation) return;

			const hierarchy = frm._department_hierarchy?.[row.department];
			if (!hierarchy) return;

			let all_child_roles = new Set();

			hierarchy.forEach((r) => {
				if (Array.isArray(r.child_roles)) {
					r.child_roles.forEach((cr) => all_child_roles.add(cr));
				}
			});

			let is_top_role = !all_child_roles.has(row.designation);

			// if (!is_top_role && !row.assigned_to) {
			// 	frappe.throw(`Row ${row.idx}: Assigned To is required`);
			// }
		});
	},

	user(frm) {
		if (!frm.doc.user) return;

		frappe.db.get_doc("User", frm.doc.user).then((user_doc) => {
			const name = user_doc.full_name || user_doc.first_name || user_doc.name;
			frm.set_value("employee_name", name);
		});
	},
});

async function apply_employee_read_only_restriction(frm) {
	// Administrator / System Manager bypass
	if (
		frappe.session.user === "Administrator" ||
		frappe.user.has_role("System Manager")
	) {
		return;
	}

	const { message: departments = [] } = await frappe.call({
		method: "verp_staffing.crm.api.helpers.get_user_departments",
	});

	const is_hr_user = departments.some(
		(dept) => (dept || "").toLowerCase() === "hr",
	);

	if (is_hr_user) {
		return;
	}

	// Make form read only
	frm.set_read_only();

	// Hide save actions
	frm.disable_save();

	// Hide common action buttons
	frm.page.btn_primary?.hide();

	// Prevent child table editing
	frm.fields.forEach((field) => {
		if (field.df.fieldtype === "Table") {
			field.grid.cannot_add_rows = true;
			field.grid.only_sortable();
			field.grid.refresh();
		}
	});
}

async function render_headline(frm) {
	const r = await frappe.call({
		method: "verp_staffing.utils.onboarding_setup_helper.get_setup_progress",
	});

	const progress = r.message;

	if (
		progress.current_step !== "erp_configuration" &&
		progress.current_step !== "pdf_agreement_template" &&
		progress.current_step !== "completed"
	) {
		return;
	}

	const configs = {
		erp_configuration: {
			message:
				"Finished Creating Employee? The next step is configuring the ERP so the system can automate your workflow.",
			button: "Configure ERP Settings",
			route: "/app/erp-configuration",
			color: "blue",
		},
		pdf_agreement_template: {
			message:
				"ERP configuration is complete. Create an agreement template to streamline candidate onboarding.",
			button: "Create Agreement Template",
			route: "/app/pdf-agreement-template/new",
			color: "blue",
		},
		completed: {
			message:
				"Congratulations. Your organization setup is complete and ready for operations.",
			button: "Go To Dashboard",
			route: "/app",
			color: "blue",
		},
	};

	const cfg = configs[progress.current_step];

	frm.dashboard.set_headline_alert(
		__(
			`${cfg.message}
			<a href="${cfg.route}"
				class="btn btn-sm btn-primary"
				style="margin-left:8px;vertical-align:middle;">
				${cfg.button}
			</a>`,
		),
		cfg.color,
	);
}

frappe.ui.form.on("Employee Assignment Detail", {
	async department(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.department) return;

		if (!frm._department_hierarchy) {
			frm._department_hierarchy = {};
		}

		// fetch if not cached
		if (!frm._department_hierarchy[row.department]) {
			try {
				const r = await frappe.call({
					method: "frappe.client.get",
					args: {
						doctype: "Hierarchy",
						name: row.department,
					},
				});

				if (r.message?.role_hierarchy_json) {
					frm._department_hierarchy[row.department] = JSON.parse(
						r.message.role_hierarchy_json,
					);
				}
			} catch (e) {
				console.error("Hierarchy fetch failed", e);
			}
		}

		// reset dependent fields
		frappe.model.set_value(cdt, cdn, "designation", null);
		frappe.model.set_value(cdt, cdn, "assigned_to", null);

		frm.refresh_field("employee_assignment_details_table");
	},
	designation(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.department) return;

		const hierarchy = frm._department_hierarchy?.[row.department];
		if (!hierarchy) return;

		let validRoles = new Set();
		let all_child_roles = new Set();

		hierarchy.forEach((r) => {
			if (r.parent_role) {
				validRoles.add(r.parent_role);
			}

			if (Array.isArray(r.child_roles)) {
				r.child_roles.forEach((cr) => {
					validRoles.add(cr);
					all_child_roles.add(cr);
				});
			}
		});

		// validate designation
		if (!validRoles.has(row.designation)) {
			frappe.model.set_value(cdt, cdn, "designation", null);
		}

		frappe.model.set_value(cdt, cdn, "assigned_to", null);

		frm.refresh_field("employee_assignment_details_table");
	},
});

function toggle_linkedin_section(frm) {
	let show = false;

	(frm.doc.employee_assignment_details_table || []).forEach((row) => {
		if (row.department === "Lead") show = true;
	});

	frm.toggle_display("linkedin_credentials", show);
}

function toggle_revenue_target_section(frm) {
	let show = false;

	(frm.doc.employee_assignment_details_table || []).forEach((row) => {
		if (row.department === "Sales") show = true;
	});

	frm.toggle_display("section_break_qppd", show);
}
