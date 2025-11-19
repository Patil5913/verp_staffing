// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
refresh(frm) {
        frm.set_query("user", function () {
            return {
                query: "verp_staffing.employee.doctype.employee.employee.get_available_users"
            };
        });

        frm.set_query("manager", function () {
            return {
                query: "verp_staffing.employee.doctype.employee.employee.get_manager_filter",
                filters: {
                    department: frm.doc.department
                }
            };
        });

        frm.set_query("master_manager", function () {
            return {
                query: "verp_staffing.employee.doctype.employee.employee.get_master_manager_filter",
                filters: {
                    department: frm.doc.department
                }
            };
        });
    },

    department(frm) {
        // Refresh filters when department changes
        frm.set_query("manager", function () {
            return {
                query: "verp_staffing.employee.doctype.employee.employee.get_manager_filter",
                filters: {
                    department: frm.doc.department
                }
            };
        });

        frm.set_query("master_manager", function () {
            return {
                query: "verp_staffing.employee.doctype.employee.employee.get_master_manager_filter",
                filters: {
                    department: frm.doc.department
                }
            };
        });
    },

    designation(frm) {
        let designation = frm.doc.designation;
        if(designation == "manager"){
            frm.set_value("manager", null);
        }else if(designation == "master_manager"){
            frm.set_value("master_manager", null);
            frm.set_value("manager", null);
        }
    },
   user(frm) {
    if (!frm.doc.user) return;

   frappe.db.get_doc("User", frm.doc.user).then(user_doc => {
        const name = user_doc.full_name || user_doc.first_name || user_doc.name;
        frm.set_value("employee_name", name);
    });
}
});