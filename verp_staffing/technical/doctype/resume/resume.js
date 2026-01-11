// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Resume", {
    refresh(frm) {
        render_notes(frm);

        if (frm.doc.status === "Completed") {
            frm.set_df_property("status", "read_only", 1);
        }

        if (frm.doc.status == "Completed") {
            add_forward_button(frm);
        }

        window.render_customer_related_html({
            frm: frm,
            html_field: "customer_details_html",
            source_doctype: "Lead Detail Form",
            customer: frm.doc.name,
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
    status(frm) {
        if (frm.doc.status == "Completed") {
            add_forward_button(frm);
        }
    }
});

function render_notes(frm) {
    const $wrapper = frm.get_field("notes_html")?.$wrapper;
    if (!$wrapper) return;

    if (!frm.doc.name) {
        $wrapper.html(`<div class="text-muted p-3">Save to view Notes.</div>`);
        return;
    }

    get_notes(frm, $wrapper);
}

function get_notes(frm, $wrapper) {
    $wrapper.html(`<div class="p-3 text-muted">Loading notes...</div>`);

    frappe.call({
        method: "verp_staffing.crm.api.notes.get_notes",
        args: {
            reference_doctype: "Resume",
            reference_name: frm.doc.name
        },
        callback: function (r) {
            const notes = r.message || [];

            if (!notes.length) {
                $wrapper.html(`
                    <div class="p-3 text-center">
                        <div class="text-muted mb-2">No notes yet.</div>
                        <button class="btn btn-primary btn-sm add-note-btn">Add Note</button>
                    </div>
                `);
                $wrapper.find(".add-note-btn").on("click", () => open_add_note_dialog(frm, $wrapper));
                return;
            }

            let html = `
            <div class="mt-2 mb-2">
                    <button class="btn btn-secondary btn-sm add-note-inline">Add Note</button>
                </div>
                <div class="notes-list list-group">
            `;

            notes.forEach(n => {
                const added_on = frappe.datetime.str_to_user(n.added_on);

                html += `
                <div class="list-group-item" data-id="${n.name}">
                    <div class="d-flex justify-content-between">
                        <div>
                            <b>${n.added_by}</b>
                            <span class="text-muted" style="margin-left: 6px;">
                                ${added_on}
                            </span>
                        </div>
                        <div>
                            <span class="text-primary edit-note" style="cursor:pointer;margin-right:10px;">Edit</span>
                            <span class="text-danger delete-note" style="cursor:pointer;">Delete</span>
                        </div>
                    </div>
                    <div class="note-content mt-2">${n.note}</div>
                </div>`;
            });

            html += `
                </div>
                
            `;

            $wrapper.html(html);

            $wrapper.find(".add-note-inline").on("click", () => open_add_note_dialog(frm, $wrapper));
            attach_edit_delete_events(frm, $wrapper);
        }
    });
}


function open_add_note_dialog(frm, $wrapper) {
    const d = new frappe.ui.Dialog({
        title: __("Add Note"),
        fields: [
            { fieldname: "note", fieldtype: "Text Editor", label: "Note", reqd: 1 }
        ],
        primary_action_label: __("Save"),
        primary_action(values) {
            if (!values.note) return;
            d.disable_primary_action();
            frappe.call({
                method: "verp_staffing.crm.api.notes.add_note",
                args: {
                    reference_doctype: "Resume",
                    reference_name: frm.doc.name,
                    note: values.note
                },
                callback(r) {
                    frappe.show_alert({ message: __("Note added"), indicator: "green" });
                    d.hide();
                    // refresh the notes panel
                    get_notes(frm, $wrapper);
                },
                error() {
                    frappe.msgprint(__("Failed to add note"));
                    d.enable_primary_action();
                }
            });
        }
    });
    d.show();
}

function attach_edit_delete_events(frm, $wrapper) {
    // Edit note
    $wrapper.find(".edit-note").on("click", function () {
        const note_id = $(this).closest(".list-group-item").data("id");
        const note_html = $(this).closest(".list-group-item").find(".note-content").html();
        open_edit_note_dialog(frm, $wrapper, note_id, note_html);
    });

    // Delete note
    $wrapper.find(".delete-note").on("click", function () {
        const note_id = $(this).closest(".list-group-item").data("id");

        frappe.confirm("Delete this note?", () => {
            frappe.call({
                method: "verp_staffing.crm.api.notes.delete_note",
                args: { note_id },
                callback: () => {
                    frappe.show_alert("Note deleted");
                    get_notes(frm, $wrapper); // refresh instantly
                }
            });
        });
    });
}


// EDIT Note - dialog
function open_edit_note_dialog(frm, $wrapper, note_id, old_note) {
    const d = new frappe.ui.Dialog({
        title: "Edit Note",
        fields: [{ fieldname: "note", fieldtype: "Text Editor", label: "Note", reqd: 1, default: old_note }],
        primary_action_label: "Update",
        primary_action(values) {
            frappe.call({
                method: "verp_staffing.crm.api.notes.update_note",
                args: {
                    note_id,
                    note: values.note
                },
                callback: () => {
                    frappe.show_alert("Note updated");
                    d.hide();
                    get_notes(frm, $wrapper); // live refresh
                }
            });
        }
    });
    d.show();
}

const ALL_FORWARD_DEPARTMENTS = [
    { label: "Resume", value: "resume" },
    { label: "Technical", value: "technical" },
    { label: "Marketing", value: "marketing" },
];

async function add_forward_button(frm) {
    frm.add_custom_button(
        "Forward Candidate",
        async () => {
            const forwarded = await get_stage_json(frm);

            const available = ALL_FORWARD_DEPARTMENTS.filter(
                d => !forwarded.includes(d.value)
            );

            if (!available.length) {
                frappe.msgprint("Candidate has already been forwarded to all departments.");
                return;
            }

            open_forward_prompt(frm, available);
        },
        "Forward"
    );
}

function open_forward_prompt(frm, available) {
    const d = new frappe.ui.Dialog({
        title: "Forward Candidate",
        fields: [
            {
                fieldname: "department",
                fieldtype: "Select",
                label: "Select Department",
                options: available.map(d => ({
                    label: d.label,
                    value: d.value
                })),
                reqd: 1,
                onchange() {
                    toggle_ruc_note_field(d);
                }
            },
            {
                fieldname: "note",
                fieldtype: "Text Editor",
                label: "Note (Required for RUC)",
                depends_on: "eval:doc.department === 'RUC'",
                hidden: 1
            }
        ],
        primary_action_label: "Forward",
        primary_action(values) {
            if (values.department === "RUC" && !values.note) {
                frappe.msgprint("Note is required when forwarding to RUC.");
                return;
            }

            d.disable_primary_action();

            if (values.department === "RUC") {
                // save note first
                frappe.call({
                    method: "verp_staffing.crm.api.notes.add_note",
                    args: {
                        reference_doctype: "RUC",
                        reference_name: frm.doc.name,
                        note: values.note
                    },
                    callback() {
                        forward_candidate(frm, values.department);
                        d.hide();
                    },
                    error() {
                        frappe.msgprint("Failed to add note");
                        d.enable_primary_action();
                    }
                });
            } else {
                forward_candidate(frm, values.department);
                d.hide();
            }
        }
    });

    d.show();
}

function toggle_ruc_note_field(dialog) {
    const dept = dialog.get_value("department");

    if (dept === "RUC") {
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
                    console.warn("Invalid stage JSON");
                    resolve([]);
                }
            },
            error: function () {
                resolve([]);
            }
        });
    });
}

function forward_candidate(frm, department) {
    frappe.call({
        method: "verp_staffing.crm.api.auto_assign.forward_candidate",
        args: {
            customer: frm.doc.customer,
            department: department
        },
        callback(r) {
            frappe.msgprint(
                `Candidate forwarded to ${department} and assigned automatically.`
            );
            frm.reload_doc();
        }
    });
}