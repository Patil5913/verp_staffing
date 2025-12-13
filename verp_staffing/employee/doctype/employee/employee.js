// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
    refresh(frm) {
        frm.set_query("user", function () {
            return {
                query: "verp_staffing.employee.doctype.employee.employee.get_users_not_linked_to_employee"
            }
        });


    },

    user(frm) {
        if (!frm.doc.user) return;

        frappe.db.get_doc("User", frm.doc.user).then(user_doc => {
            const name = user_doc.full_name || user_doc.first_name || user_doc.name;
            frm.set_value("employee_name", name);
        });
    },

    department(frm) {
        if (!frm.doc.department) return;

        frm._role_hierarchy = null;

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Hierarchy",
                name: frm.doc.department
            },
            callback(r) {
                if (!r.message || !r.message.role_hierarchy_json) {
                    frappe.msgprint("No hierarchy found for this department");
                    return;
                }

                try {
                    frm._role_hierarchy = JSON.parse(r.message.role_hierarchy_json);
                } catch (e) {
                    frappe.throw("Invalid role_hierarchy_json format");
                }

                // collect distinct roles
                let roles = new Set();

                frm._role_hierarchy.forEach(row => {
                    if (row.parent_role) {
                        roles.add(row.parent_role);
                    }
                    if (Array.isArray(row.child_roles)) {
                        row.child_roles.forEach(cr => roles.add(cr));
                    }
                });

                frm.set_df_property(
                    "designation",
                    "options",
                    Array.from(roles).join("\n")
                );

                frm.set_value("designation", null);
                frm.set_value("assigned_to", null);
            }
        });
    },

    designation(frm) {
        if (!frm.doc.designation) return;

        if (!frm._role_hierarchy) {
            frappe.throw("Role hierarchy not loaded. Select department first.");
        }

        let parent_role = null;

        frm._role_hierarchy.forEach(row => {
            if (
                Array.isArray(row.child_roles) &&
                row.child_roles.includes(frm.doc.designation)
            ) {
                parent_role = row.parent_role;
            }
        });        

        if (!parent_role) {
            // top-level role, no manager
            frm.set_query("assigned_to", () => ({
                filters: { name: ["=", ""] }
            }));
            frm.set_value("assigned_to", null);
            return;
        }

        frm.set_query("assigned_to", () => {
            return {
                filters: {
                    designation: parent_role,
                    department: frm.doc.department
                }
            };
        });

        frm.set_value("assigned_to", null);
    }
});