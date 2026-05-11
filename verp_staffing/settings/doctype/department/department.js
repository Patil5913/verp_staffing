// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Department", {
	refresh(frm) {
		set_service_query(frm);

		if (!frm.doc.name) return;

		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Hierarchy",
				fields: ["name"],
				filters: {
					department: frm.doc.name,
				},
				limit_page_length: 1,
			},
			callback: function (r) {
				if (!r.message || r.message.length === 0) {
					frm.add_custom_button("Make Hierarchy", () => {
						frappe.new_doc("Hierarchy", {
							department: frm.doc.name,
						});
					});
				}
			},
		});
	},
	onload(frm) {
		set_service_query(frm);
	},
});

function set_service_query(frm) {
	frm.set_query("services", function () {
		return {
			query: "verp_staffing.settings.doctype.department.department.get_department_service_query",
			filters: {
				department: frm.doc.name,
			},
		};
	});
}