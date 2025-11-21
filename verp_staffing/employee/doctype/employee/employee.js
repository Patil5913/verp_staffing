// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh(frm) {
        frm.set_query("user", function() {
            return{
                query: "verp_staffing.employee.doctype.employee.employee.get_users_not_linked_to_employee"
            }
        });
	},
});

