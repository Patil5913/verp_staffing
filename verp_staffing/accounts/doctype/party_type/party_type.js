// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Party Type", {
	refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Accounting",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();
	},
});
