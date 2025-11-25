// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead", {
    onload(frm) {
        // Always keep field visible
        frm.set_df_property("lead_owner", "read_only_onload", 1);
        // If lead_owner is empty → auto assign employee of logged-in user
        if (!frm.doc.lead_owner) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Employee",
                    filters: { user: frappe.session.user },
                    fieldname: "name",
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("lead_owner", r.message.name);

                        // Lock the field so user cannot change
                        frm.set_df_property("lead_owner", "read_only", 1);
                    }
                },
            });
        } else {
            // If already set → lock it
            frm.set_df_property("lead_owner", "read_only", 1);
        }
    },


    refresh(frm) {
        render_notes(frm);
        render_activity_section(frm);

        frm.add_custom_button(__('Opportunity'), () => {
            open_create_opportunity_dialog(frm);
        }, __('Create'));

        const roles = frappe.user_roles

        if (roles.includes("Extra Menu Item Not Show")) {
            //    GENERIC REUSABLE HIDE FUNCTION
            const hideElements = ({ selectors = [], keywordSelectors = [], keywords = [] }) => {
                // Hide specific selectors
                selectors.forEach(sel => {
                    const el = document.querySelector(sel);
                    if (el) el.style.display = "none";
                });
                // Hide based on keywords
                keywordSelectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        const text = el.innerText?.trim();
                        if (text && keywords.some(k => text.includes(k))) {
                            el.style.display = "none";

                            // Hide li wrapper if exists (for dropdown)
                            const li = el.closest("li");
                            if (li) li.style.display = "none";
                        }
                    });
                });
            };

            //    MENU CLEANUP
            const MENU_HIDE = ["Links", "Duplicate", "Copy to Clipboard"];

            const cleanMenu = () => {
                // Frappe API removal
                MENU_HIDE.forEach(label => {
                    try { frm.page.remove_menu_item(label); } catch { }
                });
                // DOM cleanup using reusable function
                hideElements({
                    keywordSelectors: [".dropdown-menu .dropdown-item"],
                    keywords: MENU_HIDE
                });
            };

            // Re-clean when dropdown opens
            $(frm.page.wrapper).on("shown.bs.dropdown", cleanMenu);

            //    SIDEBAR CLEANUP
            const SIDEBAR_KEYWORDS = ["Assigned", "Share"];

            const cleanSidebar = () => {
                hideElements({
                    selectors: [
                        ".form-sidebar .assigned-to",
                        ".form-sidebar .btn-share",
                        ".form-sidebar .shared-with"
                    ],
                    keywordSelectors: [
                        ".form-sidebar *"
                    ],
                    keywords: SIDEBAR_KEYWORDS
                });
            };

            //    RUN CLEANUP ONCE + SINGLE RETRY TIMER
            const runCleanup = () => {
                cleanMenu();
                cleanSidebar();
            };

            // Run immediately
            runCleanup();

            // One timer for everything (menu + sidebar)
            let attempts = 0;
            const timer = setInterval(() => {
                runCleanup();
                if (attempts++ > 12) clearInterval(timer);
            }, 200);
        }
    },

    before_save(frm) {
        let rows = frm.doc.education_table;

        if (!Array.isArray(rows) || rows.length === 0) {
            console.log("No rows in education_table table");
            return;
        }

        rows.forEach(row => {
            validate_mm_yyyy(row.start_date, "Start Date");
            validate_mm_yyyy(row.end_date, "End Date");
        });

        function validate_mm_yyyy(value, label) {
            if (!value) return;

            const regex = /^(0[1-9]|1[0-2])-\d{4}$/;

            if (!regex.test(value)) {
                frappe.throw(`${label} must be in format MM-YYYY. Invalid value: ${value}`);
            }
        }
    }
});

function open_create_opportunity_dialog(frm) {
    // If lead isn't saved yet, ask to save first
    if (frm.is_dirty()) {
        frappe.msgprint({
            title: __('Error'),
            message: __('Please save the Lead before creating an Opportunity.'),
            indicator: 'red'
        });
        return;
    }

    // Check if Opportunity already exists for this Lead
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Opportunity",
            filters: { party_name: frm.doc.name, opportunity_from: 'Lead' },
            limit_page_length: 1
        },
        callback: function (r) {
            if (r.message && r.message.length > 0) {
                frappe.msgprint({ title: __('Error'), message: __('An Opportunity already exists for this Lead.'), indicator: 'red' });
            } else {
                // Open a dialog to create Opportunity
                const dialog = new frappe.ui.Dialog({
                    title: __('Create Opportunity from Lead'),
                    fields: [
                        {
                            fieldname: "manual_assign",
                            fieldtype: "Check",
                            label: "Want to assign Opportunity Owner Manually?"
                        },
                        {
                            fieldname: "opportunity_owner",
                            label: "Opportunity Owner",
                            fieldtype: "Link",
                            options: "Employee",
                            depends_on: "eval:doc.manual_assign == 1",
                            mandatory_depends_on: "eval:doc.manual_assign == 1",
                            get_query() {
                                return {
                                    filters: {
                                        department: "Sales" // Only show Sales department employees
                                    }
                                };
                            }
                        }
                    ],
                    primary_action_label: __('Create'),
                    primary_action(values) {
                        dialog.hide();
                        if (values.manual_assign) {
                            // if user select owner manually then direct create
                            update_lead_status(frm.doc.name);
                            create_opportunity(frm, values.opportunity_owner);
                        } else {
                            // else get employee with lowest count and create opportunity
                            auto_assign_opportunity_owner().then(owner => {
                                update_lead_status(frm.doc.name);
                                create_opportunity(frm, owner);
                            })
                        }
                    }
                });
                dialog.show();
            }
        }
    })
}

function auto_assign_opportunity_owner() {
    return new Promise((resolve, reject) => {

        // get all the employees
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Employee",
                filters: { department: "Sales" },
                fields: ["name"]
            },
            callback: function (empRes) {
                employees = empRes.message || [];

                if (!employees.length) {
                    reject("No Employees Found.");
                    return;
                }

                // making array of objects, object: {employee, count}
                let promises = employees.map(emp => {
                    return frappe.db.count("Opportunity", {
                        filters: { "opportunity_owner": emp.name }
                    }).then(count => ({
                        employee: emp.name,
                        count
                    }));
                });

                // sorting array of object and sending the employee with lowest count 
                Promise.all(promises).then(results => {
                    results.sort((a, b) => a.count - b.count)
                    resolve(results[0].employee)
                })
            }
        })
    })
}

function create_opportunity(frm, owner) {
    const opportunity_doc = {
        doctype: 'Opportunity',
        opportunity_from: 'Lead',
        party_name: frm.doc.name,
        opportunity_owner: owner
    };

    frappe.call({
        method: 'frappe.client.insert',
        args: {
            doc: opportunity_doc
        },
        callback: function (response) {
            if (!response.exc && response.message) {
                frappe.msgprint({ title: __('Success'), message: __('Opportunity Created'), indicator: 'green' });
            }
        },
        error: function (err) {
            // show server error (if any)
            frappe.msgprint({
                title: __('Error'),
                message: err && err.exc ? err.exc : __('Failed to create Opportunity'),
                indicator: 'red'
            });
        }
    })
}

// Notes and Activity Section
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
            reference_doctype: "Lead",
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
                    reference_doctype: "Lead",
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
                    reference_doctype: "Lead",
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

        <button class="btn btn-xs btn-secondary edit-task-btn" onclick="open_edit_task_dialog('${t.name}', '${frm}')">Edit</button>
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
                    reference_doctype: "Lead",
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

function update_lead_status(lead_name) {
    frappe.call({
        method: "frappe.client.set_value",
        args: {
            doctype: "Lead",
            name: lead_name,
            fieldname: "status",
            value: "Lead"
        },
        callback() {
            frappe.show_alert({
                message: __("Lead status updated to Lead"),
                indicator: "green"
            });
        }
    });
}
