// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing", {

        refresh(frm) {

                // console.log("logssss");
                // console.log("current user:", frappe.session.user);frm.set_df_property("date", "read_only", 1);

                frappe.call({
                        method: "verp_staffing.marketing.doctype.marketing.marketing.can_edit_marketing_date",
                        args: {
                                assign_to: frm.doc.assign_to
                        },
                        callback(r) {
                                const grid = frm.fields_dict["job_application_count"].grid;
                                console.log("grid", grid);

                                console.log("assigned", r);

                                if (r.message) {
                                        grid.update_docfield_property("date", "read_only", 0);

                                        console.log("You can edit Marketing date");
                                } else {
                                        grid.update_docfield_property("date", "read_only", 1);
                                        console.log("You cannot edit Marketing date");
                                }
                        },
                        error(err) {
                                console.error("Error checking Marketing edit permission", err);
                        }
                });


                frappe.call({
                        method: "verp_staffing.marketing.doctype.marketing.marketing.can_edit_marketing_target",
                        args: {
                                assign_to: frm.doc.assign_to,
                        },
                        callback(r) {
                                const grid = frm.fields_dict["target"].grid;
                                console.log("target grid", grid);
                                console.log("server response", r);

                                // ✅ backend returns:
                                // { can_edit: true/false, users: [...], chain: [...], current_user: ... }
                                const canEdit = !!(r.message && r.message.can_edit);

                                if (canEdit) {
                                        grid.update_docfield_property("target_date", "read_only", 0);
                                        grid.update_docfield_property("target", "read_only", 0);
                                        console.log("You can edit Marketing target");
                                } else {
                                        grid.update_docfield_property("target_date", "read_only", 1);
                                        grid.update_docfield_property("target", "read_only", 1);
                                        console.log("You cannot edit Marketing target");
                                }

                                // ✅ refresh grid so UI updates immediately
                                frm.refresh_field("target");
                        },
                        error(err) {
                                console.error("Error checking Marketing edit permission", err);
                        },
                });









                frm.add_custom_button("Show Form Tour", () => {
                        const tour_name = 'Marketing Form';

                        frm.tour.init({ tour_name })
                                .then(() => frm.tour.start());
                });

                frm.add_custom_button(__('Create Interview'), () => {
                        open_create_interview_dialog(frm);
                });

                frm.set_query("assign_to", () => {
                        return {
                                query: "verp_staffing.crm.api.helpers.get_subordinate_employees",
                                filters: {
                                        department: "Marketing"
                                }
                        };
                });

                add_forward_button(frm);
                // to display the lead details 
                window.render_customer_related_html({
                        frm: frm,
                        html_field: "customer_details_html",
                        source_doctype: "Lead Detail Form",
                        customer: frm.doc.customer,
                        fields: [
                                "surname", "first_name", "father_name", "personal_phone_number",
                                "email", "number_for_marketing", "marketing_linkedin", "linkedin_password",
                                "technologies", "ssn_digit", "date_of_birth", "current_address",
                                "current_visa_status", "ead_card", "past_experience_table",
                                "entry_date", "certificate_or_completed_course", "availability_for_interview", "driving_licence",
                        ]
                });

                if (!frm.is_new()) {
                        frm.set_df_property("customer", "read_only", 1);
                }

                // to display the interview list
                render_interview_list(frm);
        },

        customer(frm) {
                frm.trigger("refresh");
        }

});




function open_create_interview_dialog(frm) {
        const dialog = new frappe.ui.Dialog({
                title: __('Create Interview'),
                fields: [
                        {
                                fieldname: "company",
                                fieldtype: "Data",
                                label: "Company",
                                reqd: 1
                        },
                        {
                                fieldname: "role",
                                fieldtype: "Data",
                                label: "Role",
                                reqd: 1
                        }
                ],
                primary_action_label: __('Create Interview'),
                primary_action(values) {
                        dialog.hide();
                        create_interview(frm, values);
                }
        });

        dialog.show();
}

function create_interview(frm, values) {
        const interview_doc = {
                doctype: "Interview",
                marketing_link: frm.doc.name,
                company: values.company,
                role: values.role,
                status: "Interview Scheduled"
        };

        frappe.call({
                method: "frappe.client.insert",
                args: {
                        doc: interview_doc
                },
                callback(r) {
                        if (r.message) {
                                frappe.msgprint({
                                        title: __('Success'),
                                        message: __('Interview Created Successfully'),
                                        indicator: 'green'
                                });

                                frappe.set_route("Form", "Interview", r.message.name);
                        }
                },
                error(err) {
                        frappe.msgprint({
                                title: __('Error'),
                                message: err?.exc || __('Failed to create Interview'),
                                indicator: 'red'
                        });
                }
        });
}


function render_interview_list(frm) {
        if (!frm.doc.name) return;

        frappe.call({
                method: "verp_staffing.marketing.doctype.marketing.marketing.get_interviews_by_marketing",
                args: {
                        marketing: frm.doc.name         
                },
                callback(r) {
                        const data = r.message || [];

                        if (!data.length) {
                                frm.fields_dict.interview_list.$wrapper.html(
                                        "<div class='text-muted'>No interviews linked</div>"
                                );
                                return;
                        }

                        let html = "<ul style='padding-left:15px'>";

                        data.forEach(d => {
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
                        frm.fields_dict.interview_list.$wrapper
                                .find("a")
                                .on("click", function (e) {
                                        e.preventDefault();

                                        frappe.set_route(
                                                "List",
                                                "Interview",
                                                "Kanban",
                                                { marketing_link: frm.doc.name }
                                        );
                                });
                }
        })
}

async function add_forward_button(frm) {
        frm.add_custom_button(
                "Forward Candidate",
                async () => {
                        const forwarded = await get_stage_json(frm);
                        frappe.call({
                                method: "verp_staffing.crm.doctype.customer.customer.get_forwardable_departments",
                                args: {
                                        customer: frm.doc.customer
                                },
                                callback(r) {
                                        const services = r.message || [];
                                        const available = services.filter(
                                                s => !forwarded.includes(s.toLowerCase())
                                        )
                                        if (!available.length) {
                                                frappe.msgprint("Candidate has already been forwarded for all services.");
                                                return;
                                        }

                                        open_forward_prompt(frm, available);
                                }
                        });
                }
        );
}

function open_forward_prompt(frm, available) {
        const d = new frappe.ui.Dialog({
                title: "Forward Candidate",
                fields: [
                        {
                                fieldname: "service",
                                fieldtype: "Select",
                                label: "Select Service",
                                options: available,
                                reqd: 1,
                                onchange() {
                                        toggle_ruc_note_field(d);
                                }
                        },
                        {
                                fieldname: "note",
                                fieldtype: "Text Editor",
                                label: "Note (Required for RUC)",
                                depends_on: "eval:doc.service === 'RUC'",
                                hidden: 1
                        }
                ],
                primary_action_label: "Forward",
                primary_action(values) {
                        if (values.service === "RUC" && !values.note) {
                                frappe.msgprint("Note is required when forwarding for RUC.");
                                return;
                        }

                        d.disable_primary_action();
                        forward_candidate(frm, values);
                        d.hide();
                }
        });

        d.show();
}

function toggle_ruc_note_field(dialog) {
        const service = dialog.get_value("service");

        if (service === "RUC") {
                dialog.set_df_property("note", "hidden", 0);
                dialog.set_df_property("note", "reqd", 1);
        } else {
                dialog.set_df_property("note", "hidden", 1);
                dialog.set_df_property("note", "reqd", 0);
                dialog.set_value("note", "");
        }

        dialog.refresh();
}

function get_stage_json(frm) {
        return new Promise((resolve) => {
                frappe.call({
                        method: "frappe.client.get",
                        args: {
                                doctype: "Customer",
                                name: frm.doc.customer,
                        },
                        callback: function (r) {
                                if (!r.message || !r.message.stage) {
                                        resolve([]);   // no stage yet
                                        return;
                                }

                                try {
                                        const parsedStage = JSON.parse(r.message.stage);
                                        resolve(Object.keys(parsedStage));
                                } catch (e) {
                                        console.warn("Something went wrong: Invalid stage json in customer");
                                        resolve([]);
                                }
                        },
                        error: function () {
                                resolve([]);
                        }
                });
        });
}

function forward_candidate(frm, values) {
        frappe.call({
                method: "verp_staffing.crm.api.auto_assign.forward_candidate",
                args: {
                        customer: frm.doc.customer,
                        service: values.service
                },
                callback(r) {
                        if (values.service === "RUC") {
                                frappe.call({
                                        method: "verp_staffing.crm.api.notes.add_note",
                                        args: {
                                                reference_doctype: "RUC",
                                                reference_name: r.message.name,
                                                note: values.note
                                        },
                                        error() {
                                                frappe.msgprint("Failed to add note");
                                                d.enable_primary_action();
                                        }
                                });
                        }
                        frappe.msgprint(
                                `Candidate forwarded for ${values.service} and assigned automatically.`
                        );
                        frm.reload_doc();
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
        }

}
);

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
