// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("RUC", {
    refresh(frm) {
        render_notes(frm)
        render_activity_section(frm);
        fetch_and_render_resume(frm);
        window.render_customer_related_html({
            frm: frm,
            html_field: "lead_details",
            customer: frm.doc.customer,
            fields: [
                "surname",
                "first_name",
                "father_name",
                "personal_phone_number",
                "email",
                "personal_linkedin",
                "old_resume"
            ]
        });

        frappe.call({
            method: "verp_staffing.crm.doctype.customer.customer.get_employee_department",
            callback: (r) => {
                if (frm.doc.status == "Completed") {
                    add_forward_button(frm);
                }
            }
        })
    },

    customer(frm) {
        fetch_and_render_resume(frm);
    },
    status(frm) {
        frappe.call({
            method: "verp_staffing.crm.doctype.customer.customer.get_employee_department",
            callback: (r) => {
                if (frm.doc.status == "Completed") {
                    add_forward_button(frm);
                }
            }
        })
    }
});

function fetch_and_render_resume(frm) {
    frappe.db.get_list("Resume", {
        filters: {
            customer: frm.doc.customer
        },
        fields: ["name", "resume"],
        limit: 1
    }).then(res => {
        if (!res || !res.length || !res[0].resume) {
            frm.set_df_property("resume", "options",
                "<div style='color:#888'>No resume uploaded</div>"
            );
            return;
        }

        const file_url = res[0].resume;

        const html = `
            <div style="padding:8px">
                <a href="${file_url}" target="_blank" style="
                    color:#1a73e8;
                    font-weight:600;
                    text-decoration:none;
                ">
                    📄 View Resume
                </a>
            </div>
        `;

        frm.set_df_property("resume", "options", html);
    });
}


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
            reference_doctype: "RUC",
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
                    reference_doctype: frm.doctype,
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

    //edit task
    $wrapper.find(".edit-task-btn").on("click", function () {
        const task_id = $(this).closest(".list-group-item").data("id");
        open_edit_task_dialog(task_id, frm);
    });

    //delete task
    $wrapper.find(".delete-task-btn").on("click", function () {
        const task_id = $(this).closest(".list-group-item").data("id");

        frappe.confirm("Delete this task?\nThis action cannot be undone.", () => {
            frappe.call({
                method: "verp_staffing.crm.api.activities.delete_activity",
                args: { doctype: "CRM Task", name: task_id },
                callback: () => {
                    frappe.show_alert("Task deleted");
                    render_activity_section(frm); // refresh instantly
                }
            });
        });
    });

    //edit event
    $wrapper.find(".edit-event-btn").on("click", function () {
        const event_id = $(this).closest(".list-group-item").data("id");
        open_edit_event_dialog(event_id, frm);
    });

    //delete event
    $wrapper.find(".delete-event-btn").on("click", function () {
        const event_id = $(this).closest(".list-group-item").data("id");

        frappe.confirm("Delete this event?\nThis action cannot be undone.", () => {
            frappe.call({
                method: "verp_staffing.crm.api.activities.delete_activity",
                args: { doctype: "CRM Event", name: event_id },
                callback: () => {
                    frappe.show_alert("Event deleted");
                    render_activity_section(frm); // refresh instantly
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

// activity
function render_activity_section(frm) {
    if (!frm.doc.name) return;
    let $wrapper = frm.get_field("open_activities_html")?.$wrapper;
    if (!$wrapper) return;
    frappe.call({
        method: "verp_staffing.crm.api.activities.get_open_activities",
        args: {
            reference_doctype: frm.doc.doctype,
            reference_name: frm.doc.name
        },
        callback: function (r) {
            let tasks = r.message.tasks;
            let events = r.message.events;
            let html = `
            <div style="display:flex; gap:20px;">
                
                <div style="width:50%">
                    <h4>Tasks 
                        <button class="btn btn-sm btn-secondary add-task-btn" style="margin-left: 10px;">+ Add Task</button>
                    </h4>
                    <div class="task-list">
                        ${tasks.length == 0
                    ? `<p>No open tasks</p>`
                    : tasks.map(t => render_task_card(t, frm)).join("")
                }
                    </div>
                </div>
                <div style="width:50%">
                    <h4>Events 
                        <button class="btn btn-sm btn-secondary add-event-btn" style="margin-left: 10px;">+ Add Event</button>
                    </h4>
                    <div class="event-list">
                        ${events.length == 0
                    ? `<p>No events</p>`
                    : events.map(e => render_event_card(e, frm)).join("")
                }
                    </div>
                </div>

            </div>
            `;

            $wrapper.html(html);
            $wrapper.find(".add-task-btn").on("click", () => open_new_task_dialog(frm));
            $wrapper.find(".add-event-btn").on("click", () => open_new_event_dialog(frm));
            attach_edit_delete_events(frm, $wrapper);
            bind_task_checkbox_actions(frm);
        }
    });
}

//create task
function open_new_task_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Create Task"),
        fields: [
            { label: "Description", fieldname: "description", fieldtype: "Small Text", reqd: 1 },
            { label: "Date", fieldname: "date", fieldtype: "Datetime", default: frappe.datetime.now_datetime(), reqd: 1 },
            { label: "Assigned To", fieldname: "assigned_to", fieldtype: "Link", options: "User" }
        ],
        primary_action_label: __("Create"),
        primary_action(values) {
            if (!values.description || !values.date) return;
            if (!values.assigned_to) {
                values.assigned_to = frappe.session.user;
            }
            d.disable_primary_action();
            frappe.call({
                method: "verp_staffing.crm.api.activities.create_task",
                args: {
                    reference_doctype: "RUC",
                    reference_name: frm.doc.name,
                    description: values.description,
                    date: values.date,
                    assigned_to: values.assigned_to
                },
                callback(r) {
                    frappe.show_alert({ message: __("Task created"), indicator: "green" });
                    d.hide();
                    render_activity_section(frm);
                },
                error() {
                    frappe.msgprint(__("Failed to add task"));
                    d.enable_primary_action();
                }
            });
        }
    });

    d.show();
}

function render_task_card(t, frm) {
    return `
    <div class="task-card list-group-item" data-id="${t.name}" style="padding:10px; border:1px solid #ccc; border-radius:6px; margin-bottom:8px; display:flex; align-items:center; gap:10px;">
        <input type="checkbox" class="task-complete" data-id="${t.name}" />

        <div style="flex:1">
            <b>${t.description}</b><br>
            <small>Due: ${t.date || "No date"} | Assigned: ${t.assigned_to || "N/A"}</small>
        </div>
        <button class="btn btn-xs btn-secondary edit-task-btn"">Edit</button>
        <button class="btn btn-xs btn-secondary delete-task-btn text-danger">Delete</button>

    </div>
    `;
}

function render_event_card(e, frm) {
    return `
    <div class="event-card list-group-item" data-id="${e.name}" style="padding:10px; border:1px solid #ccc; border-radius:6px; margin-bottom:8px;">
        <b>${e.category}</b> <br>
        <small>Date: ${e.date || "No date"} | Assigned: ${e.assigned_to || "N/A"}</small>
        <button class="btn btn-xs btn-secondary edit-event-btn" style="margin-left:10px">Edit</button>
        <button class="btn btn-xs btn-secondary delete-event-btn text-danger" style="margin-left:10px">Delete</button>
    </div>
    `;
}

function bind_task_checkbox_actions(frm) {
    $(".task-complete").on("change", function () {
        let task_id = $(this).data("id");

        frappe.call({
            method: "verp_staffing.crm.api.activities.mark_task_complete",
            args: { task_name: task_id, completed: 1 },
            callback: () => render_activity_section(frm)
        });
    });
}


// edit task
function open_edit_task_dialog(task_name, frm) {

    frappe.db.get_doc("CRM Task", task_name).then(doc => {
        let d = new frappe.ui.Dialog({
            title: __("Edit Task"),
            fields: [
                { label: "Description", fieldname: "description", fieldtype: "Small Text", default: doc.description, reqd: 1 },
                { label: "Date", fieldname: "date", fieldtype: "Datetime", default: doc.date },
                { label: "Assigned To", fieldname: "assigned_to", fieldtype: "Link", options: "User", default: doc.assigned_to },
                { label: "Completed?", fieldname: "is_completed", fieldtype: "Check", default: doc.is_completed },
            ],
            primary_action_label: __("Update"),
            primary_action(values) {
                frappe.call({
                    method: "verp_staffing.crm.api.activities.mark_task_complete",
                    args: {
                        task_name: task_name,
                        completed: values.is_completed ? 1 : 0
                    }
                });

                frappe.db.set_value("CRM Task", task_name, {
                    description: values.description,
                    date: values.date,
                    assigned_to: values.assigned_to
                }).then(() => {
                    frappe.show_alert("Task updated");
                    d.hide();
                    render_activity_section(frm);
                });
            },
            secondary_action_label: __("Delete"),
            secondary_action() {
                frappe.call({
                    method: "verp_staffing.crm.api.activities.delete_activity",
                    args: { doctype: "CRM Task", name: task_name },
                    callback() {
                        frappe.show_alert("Task deleted");
                        d.hide();
                        render_activity_section(frm);
                    }
                });
            }
        });

        d.show();
    });
}



// create event
function open_new_event_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __("Create Event"),
        fields: [
            { label: "Category", fieldname: "category", fieldtype: "Select", options: "Event\nMeeting\nCall\nFollow Up\nOther", reqd: 1 },
            { label: "Date", fieldname: "date", fieldtype: "Datetime", default: frappe.datetime.now_datetime(), reqd: 1 },
            { label: "Summary", fieldname: "summary", fieldtype: "Data", reqd: 1 },
            { label: "Description", fieldname: "description", fieldtype: "Text Editor" },
            { label: "Assigned To", fieldname: "assigned_to", fieldtype: "Link", options: "User" }
        ],
        primary_action_label: __("Create"),
        primary_action(values) {
            frappe.call({
                method: "verp_staffing.crm.api.activities.create_event",
                args: {
                    reference_doctype: "RUC",
                    reference_name: frm.doc.name,
                    summary: values.summary,
                    date: values.date,
                    category: values.category,
                    assigned_to: values.assigned_to,
                },
                callback() {
                    frappe.show_alert("Event created");
                    d.hide();
                    render_activity_section(frm);
                }
            });
        }
    });

    d.show();
}



// edit event
function open_edit_event_dialog(event_name, frm) {
    frappe.db.get_doc("CRM Event", event_name).then(doc => {
        let d = new frappe.ui.Dialog({
            title: __("Edit Event"),
            fields: [
                { label: "Category", fieldname: "category", fieldtype: "Select", options: "Event\nMeeting\nCall\nFollow Up\nOther", default: doc.category, reqd: 1 },
                { label: "Date", fieldname: "date", fieldtype: "Datetime", default: doc.date, reqd: 1 },
                { label: "Summary", fieldname: "summary", fieldtype: "Data", default: doc.summary, reqd: 1 },
                { label: "Description", fieldname: "description", fieldtype: "Text Editor", default: doc.description },
                { label: "Assigned To", fieldname: "assigned_to", fieldtype: "Link", options: "User", default: doc.assigned_to }
            ],
            primary_action_label: __("Update"),
            primary_action(values) {
                frappe.db.set_value("CRM Event", event_name, {
                    summary: values.summary,
                    date: values.date,
                    description: values.description,
                    category: values.category,
                    assigned_to: values.assigned_to
                }).then(() => {
                    frappe.show_alert("Event updated");
                    d.hide();
                    render_activity_section(frm);
                });
            },
            secondary_action_label: __("Delete"),
            secondary_action() {
                frappe.call({
                    method: "verp_staffing.crm.api.activities.delete_activity",
                    args: { doctype: "CRM Event", name: event_name },
                    callback() {
                        frappe.show_alert("Event deleted");
                        d.hide();
                        render_activity_section(frm);
                    }
                });
            }
        });

        d.show();
    });
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
