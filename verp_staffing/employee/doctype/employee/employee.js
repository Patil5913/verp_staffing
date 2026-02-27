// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
    refresh(frm) {
        frm.set_query("user", function () {
            return {
                query: "verp_staffing.employee.doctype.employee.employee.get_users_not_linked_to_employee"
            }
        });

        toggle_linkedin_section(frm);




        frm.fields_dict.employee_assignment_details_table.grid.wrapper
            .on('focus', '[data-fieldname="designation"]', function (e) {
                const $target = $(e.target);
                const $row = $target.closest('.grid-row');
                const cdn = $row.attr('data-name');
                const cdt = 'Employee Assignment Detail'; // Hardcode if lookup fails
                // toggle_linkedin_section(frm);

                console.log("cdn: ", cdn)
                if (!cdn) {
                    console.warn("Row not ready yet");
                    return;
                }
                const row = locals[cdt][cdn];
                console.log("Focused row:", row);

                fetch_department_hierarchy(frm, row);
            });

        frm.fields_dict.employee_assignment_details_table.grid
            .get_field("assigned_to").get_query = function (doc, cdt, cdn) {
                console.log("cdt: ", cdt)
                const row = locals[cdt][cdn];
                if (!row || !row.department || !row.designation) {
                    return {};
                }
                console.log("first row", row);


                const hierarchy = frm._department_hierarchy?.[row.department];
                if (!hierarchy) {
                    return {};
                }


                let parent_role = null;

                hierarchy.forEach(r => {
                    console.log("child row", r.child_roles);
                    console.log("parentrow", r.parent_role);


                    if (
                        Array.isArray(r.child_roles) &&
                        r.child_roles.includes(row.designation)
                    ) {
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
                        designation: parent_role
                    }
                };
            };
    },
   

    user(frm) {
        if (!frm.doc.user) return;

        frappe.db.get_doc("User", frm.doc.user).then(user_doc => {
            const name = user_doc.full_name || user_doc.first_name || user_doc.name;
            frm.set_value("employee_name", name);
        });
    },


});



async function fetch_department_hierarchy(frm, row) {
    if (!frm._department_hierarchy) {
        frm._department_hierarchy = {};
    }
    console.log("hello", frm._department_hierarchy);

    // use cache if already loaded
    if (frm._department_hierarchy[row.department]) {
        apply_designation_options(frm, row);
        return;
    }

    const r = await frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Hierarchy",
            name: row.department
        }
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
    console.log("hierarchy", hierarchy);

    apply_designation_options(frm, row);
}


function apply_designation_options(frm, row) {
    const hierarchy = frm._department_hierarchy[row.department];
    console.log("hierarchy 2 ", hierarchy);


    let roles = new Set();

    hierarchy.forEach(r => {
        if (r.parent_role) roles.add(r.parent_role);
        if (Array.isArray(r.child_roles)) {
            r.child_roles.forEach(cr => roles.add(cr));
        }
    });

    const options = Array.from(roles).join("\n");
    console.log("role", roles);
    console.log("options", options);



    // THIS is the correct target
    frm.fields_dict.employee_assignment_details_table.grid.update_docfield_property(
        "designation",
        "options",
        options
    );

    // row.designation = null;
    row.assigned_to = null;

    frm.refresh_field("employee_assignment_details_table");
}


function apply_assigned_to_filter(frm, cdt, cdn) {
    console.log("function called");

    frm.fields_dict.employee_assignment_details_table.grid
        .get_field("assigned_to").get_query = function (doc, cdt_inner, cdn_inner) {
            console.log("inside get_query");


            const row = locals[cdt_inner][cdn_inner];
            console.log("row", row);
            console.log("row.department", row.department);
            console.log("row.designation", row.designation);

            if (!row || !row.department || !row.designation) {
                return {};
            }

            const hierarchy = frm._department_hierarchy[row.department];
            console.log("hierarchy", hierarchy);

            if (!hierarchy) {
                return {};
            }

            let parent_role = null;

            hierarchy.forEach(r => {
                if (
                    Array.isArray(r.child_roles) &&
                    r.child_roles.includes(row.designation)
                ) {
                    parent_role = r.parent_role;
                }
            });

            console.log("parent_role", parent_role);


            if (!parent_role) {
                return { filters: { name: ["=", ""] } };
            }

            return {
                query: "verp_staffing.employee.doctype.employee.employee.get_employees_by_assignment",
                filters: {
                    department: row.department,
                    designation: parent_role
                }
            };
        };

    frappe.model.set_value(cdt, cdn, "assigned_to", null);
}


function toggle_linkedin_section(frm) {
    let show = false;

    (frm.doc.employee_assignment_details_table || []).forEach(row => {
        if (row.department === "Lead") {
            show = true;
        }
    });

    frm.toggle_display("linkedin_credentials", show);
}

frappe.ui.form.on("Employee Assignment Detail", {
    department(frm) {
        toggle_linkedin_section(frm);
    },

    // employee_assignment_details_table_remove(frm) {
    //     toggle_linkedin_section(frm);
    // }
}); 