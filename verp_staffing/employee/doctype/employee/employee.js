// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh(frm) {
		frm.set_query("user", function () {
			return {
				query: "verp_staffing.employee.doctype.employee.employee.get_users_not_linked_to_employee",
			};
		});

		toggle_linkedin_section(frm);
		toggle_revenue_target_section(frm);

		// DESIGNATION FILTER
		frm.fields_dict.employee_assignment_details_table.grid.get_field("designation").get_query =
			function (doc, cdt, cdn) {
				const row = locals[cdt][cdn];

				if (!row.department) {
					let selected_roles = (frm.doc.employee_assignment_details_table || [])
						.filter((d) => d.name !== row.name)
						.map((d) => d.designation)
						.filter(Boolean);

					if (!selected_roles.length) {
						return { filters: { name: ["=", ""] } };
					}

					return {
						filters: {
							name: ["not in", selected_roles],
						},
					};
				}

				const hierarchy = frm._department_hierarchy?.[row.department];

				if (!hierarchy) {
					return { filters: { name: ["=", ""] } };
				}

				let roles = new Set();

				hierarchy.forEach((r) => {
					if (r.parent_role) roles.add(r.parent_role);

					if (Array.isArray(r.child_roles)) {
						r.child_roles.forEach((cr) => roles.add(cr));
					}
				});

				let role_list = Array.from(roles);

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

		// ASSIGNED TO FILTER
		frm.fields_dict.employee_assignment_details_table.grid.get_field("assigned_to").get_query =
			function (doc, cdt, cdn) {
				const row = locals[cdt][cdn];

				if (!row || !row.department || !row.designation) {
					return {};
				}

				const hierarchy = frm._department_hierarchy?.[row.department];

				if (!hierarchy) {
					return {};
				}

				let parent_role = null;

				hierarchy.forEach((r) => {
					if (Array.isArray(r.child_roles) && r.child_roles.includes(row.designation)) {
						parent_role = r.parent_role;
					}
				});

				if (!parent_role) {
					return { filters: { name: ["=", ""] } };
				}

				return {
					query: "verp_staffing.employee.doctype.employee.employee.get_employees_by_assignment",
					filters: {
						department: row.department,
						designation: parent_role,
					},
				};
			};

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Employee Form";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
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

// CHILD TABLE EVENTS
frappe.ui.form.on("Employee Assignment Detail", {
	async department(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.department) return;

		if (!frm._department_hierarchy) {
			frm._department_hierarchy = {};
		}

		// already cached
		if (frm._department_hierarchy[row.department]) {
			return;
		}

		const r = await frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Hierarchy",
				name: row.department,
			},
		});

		if (!r.message || !r.message.role_hierarchy_json) {
			frappe.throw("No role hierarchy found for selected department");
		}

		let hierarchy;

		try {
			hierarchy = JSON.parse(r.message.role_hierarchy_json);
		} catch (e) {
			frappe.throw("Invalid role_hierarchy_json");
		}

		frm._department_hierarchy[row.department] = hierarchy;
	},

	designation(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		row.assigned_to = null;
		frm.refresh_field("employee_assignment_details_table");
	},
});

function apply_assigned_to_filter(frm, cdt, cdn) {
	frm.fields_dict.employee_assignment_details_table.grid.get_field("assigned_to").get_query =
		function (doc, cdt_inner, cdn_inner) {
			const row = locals[cdt_inner][cdn_inner];

			if (!row || !row.department || !row.designation) {
				return {};
			}

			const hierarchy = frm._department_hierarchy[row.department];

			if (!hierarchy) {
				return {};
			}

			let parent_role = null;

			hierarchy.forEach((r) => {
				if (Array.isArray(r.child_roles) && r.child_roles.includes(row.designation)) {
					parent_role = r.parent_role;
				}
			});

			if (!parent_role) {
				return { filters: { name: ["=", ""] } };
			}

			return {
				query: "verp_staffing.employee.doctype.employee.employee.get_employees_by_assignment",
				filters: {
					department: row.department,
					designation: parent_role,
				},
			};
		};

	frappe.model.set_value(cdt, cdn, "assigned_to", null);
}

function toggle_linkedin_section(frm) {
	let show = false;

	(frm.doc.employee_assignment_details_table || []).forEach((row) => {
		if (row.department === "Lead") {
			show = true;
		}
	});

	frm.toggle_display("linkedin_credentials", show);
}

frappe.ui.form.on("Employee Assignment Detail", {
	department(frm) {
		toggle_linkedin_section(frm);
		toggle_revenue_target_section(frm);
	},

	// employee_assignment_details_table_remove(frm) {
	//     toggle_linkedin_section(frm);
	// }
});

function toggle_revenue_target_section(frm) {
	let show = false;

	(frm.doc.employee_assignment_details_table || []).forEach((row) => {
		if (row.department === "Sales") {
			show = true;
		}
	});

	frm.toggle_display("section_break_qppd", show);
}
