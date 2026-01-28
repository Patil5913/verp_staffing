// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cover Letter", {
	refresh(frm) {
        add_forward_button(frm);
        window.render_customer_related_html({
            frm: frm,
            html_field: "lead_details",
            source_doctype: "Lead Detail Form",
            customer: frm.doc.customer,
            fields: [
                "surname",
                "first_name",
                "father_name",
                "personal_phone_number",
                "email",
                "personal_linkedin",
                "date_of_birth",
                "educational_details",
                "past_experience_table",
                "technologies",
                "additional_skills",
                "entry_date",
                "current_address",
                "address_history",
                "certificate_or_completed_course",
                "current_visa_status",
                "experience",
                "passport_number",
                "ssn_digit",
                "availability_for_interview",
                "remarks",
                "ead_card",
                "old_resume"
            ]
        });
	},
});

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
