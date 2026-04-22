// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service", {
	refresh(frm) {
		frm.clear_custom_buttons();

		if (!frm.doc.name) return;

		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Department",
				fields: ["name"],
				filters: [["Department Service", "service_name", "=", frm.doc.name]],
				limit_page_length: 1,
			},
			callback: function (r) {
				let is_change = false;
				let department_name = null;
				let button_label = "Select Department";

				if (r.message && r.message.length > 0) {
					is_change = true;
					department_name = r.message[0].name;
					button_label = `Change Department`;
				}

				frm.add_custom_button(button_label, () => {
					open_department_dialog(frm, is_change, department_name);
				});
			},
		});
	},
});

function open_department_dialog(frm, is_change, current_department) {
	let dialog = new frappe.ui.Dialog({
		title: is_change ? "Change Department" : "Select Department",
		fields: [
			{
				label: "Department",
				fieldname: "department",
				fieldtype: "Link",
				options: "Department",
				reqd: 1,
				default: current_department || "", // ✅ show existing department
			},
		],
		primary_action_label: is_change ? "Change" : "Add",
		primary_action(values) {
			if (!values.department) return;

			if (is_change) {
				change_department(frm, values.department, current_department);
			} else {
				add_service_to_department(frm, values.department);
			}

			dialog.hide();
		},
	});

	dialog.show();
}

function add_service_to_department(frm, department_name) {
	if (!frm.doc.name) {
		frappe.msgprint("Please save Service first");
		return;
	}

	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Department",
			name: department_name,
		},
		callback: function (r) {
			let dept = r.message;

			let exists = (dept.services || []).some((row) => row.service_name === frm.doc.name);

			if (!exists) {
				dept.services.push({
					doctype: "Department Service",
					service_name: frm.doc.name,
				});
			}

			frappe.call({
				method: "frappe.client.save",
				args: { doc: dept },
				callback: () => {
					frappe.msgprint("Service updated to department successfully");
					frm.refresh();
				},
			});
		},
	});
}

function change_department(frm, new_department, old_department) {
	if (!old_department) {
		add_service_to_department(frm, new_department);
		return;
	}

	// STEP 1: Remove from old department
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Department",
			name: old_department,
		},
		callback: function (r) {
			let old_dept = r.message;

			old_dept.services = (old_dept.services || []).filter(
				(row) => row.service_name !== frm.doc.name,
			);

			frappe.call({
				method: "frappe.client.save",
				args: { doc: old_dept },
				callback: function () {
					// STEP 2: Add to new department
					add_service_to_department(frm, new_department);
				},
			});
		},
	});
}
