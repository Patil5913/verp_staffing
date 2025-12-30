// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing", {
        refresh(frm) {
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


                // to display the lead details 
                window.render_customer_related_html({
                        frm: frm,
                        html_field: "customer_details_html",
                        source_doctype: "Lead Detail Form",
                        customer: frm.doc.customer,
                        fields: [
                                "number_for_marketing",
                        ],
                        label_map: {
                                number_for_marketing: "Lead number for marketing",
                        }
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
                        <a href="#" data-interview="${d.name}">
                            ${d.name}
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
