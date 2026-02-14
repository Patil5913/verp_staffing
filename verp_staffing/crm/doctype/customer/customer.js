// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer", {
    refresh(frm) {
        render_notes(frm);
        render_activity_section(frm);
        toggle_tab_view(frm);
        inject_department_css();
        inject_status_badge_css();
        load_department_panels(frm);

        if (!frm.is_new()) {
            show_sales_order(frm);
        }

        window.render_customer_related_html({
            frm: frm,
            html_field: "lead_details",
            source_doctype: "Lead Detail Form",
            customer: frm.doc.name,
            fields: [
                "agreement_link",
                "signature_method",
                "signature_image",
                "my_electronic_signature_has_same_effect_as_handwritten",
                "i_consent_to_receive_sign_and_store_documents_electronically",
                "i_confirm_my_identity_and_signing_this_document_intentionally",
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
                "number_for_marketing",
                "google_voice_number",
                "marketing_linkedin",
                "passport_number",
                "ssn_digit",
                "availability_for_interview",
                "remarks",
                "visa_copy",
                "ead_card",
                "driving_licence",
                "old_resume"
            ]
        });

        // show forward button only when form is filled
        frappe.call({
            method: "verp_staffing.crm.doctype.customer.customer.get_employee_department",
            callback: (r) => {
                let dept = r.message
                apply_tab_visibility(frm, dept)
                if (dept.includes("Sales") || frappe.user.has_role("System Manager")) {
                    add_forward_button(frm);
                }
            }
        })

        frm.add_custom_button("Show Form Tour", () => {
            const tour_name = 'Customer Form';

            frm.tour.init({ tour_name })
                .then(() => frm.tour.start());
        });

        // show forward button only when form is filled
        frappe.call({
            method: "verp_staffing.crm.doctype.customer.customer.get_employee_department",
            callback: (r) => {
                let dept = r.message
                apply_tab_visibility(frm, dept)
                add_forward_button(frm);
            }
        });
    },

    from_opportunity: function(frm) {
        if (!frm.doc.from_opportunity) return;

        frappe.db.get_value(
            'Opportunity',
            frm.doc.from_opportunity,
            'title'
        ).then(r => {
            if (r.message && r.message.title) {
                frm.set_value('customer_name', r.message.title);
            }
        });
    },

    from_lead: function(frm) {
        if (!frm.doc.from_lead) return;

        frappe.db.get_value(
            'Lead',
            frm.doc.from_lead,
            'name1'
        ).then(r => {
            if (r.message && r.message.name1) {
                frm.set_value('customer_name', r.message.name1);
            }
        });
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
            reference_doctype: "Customer",
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
                    reference_doctype: "Customer",
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
                    reference_doctype: "Customer",
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
                    reference_doctype: "Customer",
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

//toogle tab view
function toggle_tab_view(frm) {
    frappe.call({
        method: "frappe.client.get_value",
        args: {
            doctype: "Employee",
            filters: { user: frappe.session.user },
            fieldname: ["employee_assignment_details_table"]
        },
        callback: function (r) {
            if (!r.message) return;

            const department = r.message.employee_assignment_details_table.map((d) => d.department);
            // Hide other tabs based on department
            if (department.includes("Technical")) {
                frm.toggle_display("sales_tab", false);
                frm.toggle_display("sales_content", false);
                frm.toggle_display("marketing_tab", false);
                frm.toggle_display("marketing_content", false);
            }

            if (department.includes("Marketing")) {
                frm.toggle_display("sales_tab", false);
                frm.toggle_display("sales_content", false);
                frm.toggle_display("technical_tab", false);
                frm.toggle_display("technical_content", false);
            }
        }
    });
}

function show_sales_order(frm) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Sales Order",
            filters: { customer: frm.doc.name },
            fields: ["name", "title", "date", "customer"],
            limit_page_length: 50,
            order_by: "creation desc"
        },
        callback(r) {
            let sales_orders = r.message || [];

            if (sales_orders.length === 0) {
                frm.fields_dict.sales_content.$wrapper.html("<p>No Sales Orders found.</p>");
                return;
            }

            let html = `<div style="padding: 10px;">`;

            html += `<h3>Sales Orders (${sales_orders.length})</h3><hr/>`;

            sales_orders.forEach((so, idx) => {
                html += `
                    <div style="border:1px solid #ddd; padding:15px; border-radius:6px; margin-bottom:15px;">
                        
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h4>Sales Order: ${so.name}</h4>

                            <button class="btn btn-primary go-to-so-btn" 
                                data-so="${so.name}" 
                                style="font-size:13px;">
                                go to Sales Order
                            </button>
                        </div>

                        <p><b>Title:</b> ${so.title || ""}</p>
                        <p><b>Date:</b> ${so.date || ""}</p>
                        <p><b>Customer:</b> ${so.customer || ""}</p>

                        <div id="terms_${so.name}">
                            <i>Loading Payment Terms...</i>
                        </div>
                    </div>
                `;

                // Fetch payment terms for each SO
                load_payment_terms(so.name, frm);
            });

            html += `</div>`;

            frm.fields_dict.sales_content.$wrapper.html(html);

            // Attach click events for all update buttons
            frm.fields_dict.sales_content.$wrapper
                .find(".go-to-so-btn")
                .on("click", function () {
                    const so_name = $(this).data("so");
                    frappe.set_route("Form", "Sales Order", so_name);
                });
        }
    });
}


// Fetch payment terms for each SO block dynamically
function load_payment_terms(so_name, frm) {
    frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Sales Order",
            name: so_name,
        },
        callback: function (r) {
            console.log("r: ", r);

            if (!r.message) return;

            let so = r.message;
            let html = `
                <h5>Payment Terms</h5>
                <table class="table table-bordered" style="width:100%; margin-top:10px;">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Received?</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            (so.payment_terms || []).forEach((row, i) => {
                html += `
                    <tr>
                        <td>${i + 1}</td>
                        <td>${row.date || ""}</td>
                        <td>${row.amount || ""}</td>
                        <td>${row.is_received ? "Yes" : "No"}</td>
                    </tr>
                `;
            });

            html += `</tbody></table>`;

            frm.fields_dict.sales_content.$wrapper
                .find(`#terms_${so_name}`)
                .html(html);
        }
    });
}

function render_lead_details(frm) {
    frm.set_df_property(
        "lead_details",
        "options",
        `<p style="color:#888;padding:10px;">Loading Lead Details...</p>`
    );

    // STEP 1: Check existence
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Lead Detail Form",
            filters: {
                customer: frm.doc.name
            },
            fields: ["name"],
            limit_page_length: 1
        },
        callback: function (res) {

            // ✅ CASE 1: No Lead Detail linked
            if (!res.message || res.message.length === 0) {
                frm.set_df_property(
                    "lead_details",
                    "options",
                    `
                    <div style="padding:15px;color:#999;">
                        <h4>Lead Details</h4>
                        <p>No Lead Detail form not filled yet by customer.</p>
                    </div>
                    `
                );
                return;
            }

            // STEP 2: Fetch full document
            const c_name = res.message[0].name;

            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "Lead Detail Form",
                    name: c_name
                },
                callback: function (lead_res) {

                    if (!lead_res.message) {
                        frm.set_df_property(
                            "lead_details",
                            "options",
                            `<p style="color:red;">Failed to load Lead Details.</p>`
                        );
                        return;
                    }

                    const lead = lead_res.message;

                    let html = `
                        <div style="padding:15px;">
                            <h4 style="margin-bottom:15px;">Lead Details</h4>
                            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                    `;

                    const exclude = [
                        "doctype", "name", "owner", "modified", "creation", "modified_by",
                        "docstatus", "_comments", "_assign", "_user_tags", "idx"
                    ];

                    // Helper for Link fields
                    const fetchLinkValue = (field, value, key) => {
                        frappe.call({
                            method: "frappe.client.get",
                            args: {
                                doctype: field.options,
                                name: value
                            },
                            callback: function (data) {
                                const finalValue = data.message?.name || value;
                                $(`#field-${key}`).text(finalValue);
                            }
                        });
                    };

                    Object.keys(lead).forEach(key => {
                        const value = lead[key];

                        if (
                            exclude.includes(key) ||
                            value === null ||
                            value === "" ||
                            key === "past_experience" ||
                            key === "education_table"
                        ) return;

                        const field = frappe.meta.get_docfield("Lead Detail Form", key);
                        const label = frappe.model.unscrub(key);

                        if (field && field.fieldtype === "Link") {
                            html += `
                                <div style="border:1px solid #e5e5e5;padding:10px;border-radius:8px;">
                                    <strong>${label}</strong><br>
                                    <span id="field-${key}">Loading...</span>
                                </div>`;
                            fetchLinkValue(field, value, key);

                        } else if (typeof value !== "object") {
                            html += `
                                <div style="border:1px solid #e5e5e5;padding:10px;border-radius:8px;">
                                    <strong>${label}</strong><br>
                                    <span>${value}</span>
                                </div>`;
                        }
                    });

                    html += `</div><br>`;

                    // Child tables
                    ["past_experience", "education_table"].forEach(tblKey => {
                        if (Array.isArray(lead[tblKey]) && lead[tblKey].length > 0) {
                            html += `<h4 style="margin-top:20px;">${frappe.model.unscrub(tblKey)}</h4>`;
                            html += `<table class="table table-bordered" style="width:100%;font-size:13px;">
                                        <tr>`;

                            Object.keys(lead[tblKey][0]).forEach(col => {
                                html += `<th>${frappe.model.unscrub(col)}</th>`;
                            });

                            html += `</tr>`;

                            lead[tblKey].forEach(row => {
                                html += `<tr>`;
                                Object.keys(row).forEach(col => {
                                    html += `<td>${row[col] || "-"}</td>`;
                                });
                                html += `</tr>`;
                            });

                            html += `</table>`;
                        }
                    });

                    html += `</div>`;
                    frm.set_df_property("lead_details", "options", html);
                }
            });
        }
    });
}


const DEPARTMENT_VISIBILITY = {
    sales: ["lead_details", "sales_tab", "resume_tab", "technical_tab", "marketing_tab"],
    resume: ["lead_details", "resume_tab"],
    technical: ["lead_details", "resume_tab", "technical_tab"],
    marketing: ["lead_details", "resume_tab", "technical_tab", "marketing_tab"]
};

function apply_tab_visibility(frm, department) {
    const allowed = DEPARTMENT_VISIBILITY[department] || [];

    const all_tabs = [
        "sales_tab",
        "resume_tab",
        "technical_tab",
        "marketing_tab",
        "note_tab",
        "activities_tab"
    ];

    all_tabs.forEach(tab => {
        frm.set_df_property(tab, "hidden", !allowed.includes(tab));
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
                    customer: frm.doc.name
                },
                callback(r) {
                    const services = r.message;
                    if (services.length === 0) {
                        frappe.msgprint("No services available for forwarding.");
                        return;
                    }

                    open_forward_prompt(frm, services);
                }
            });
        }
    );
}

function open_forward_prompt(frm, services) {
    const d = new frappe.ui.Dialog({
        title: "Forward Candidate",
        fields: [
            {
                fieldname: "service",
                fieldtype: "Select",
                label: "Select Service",
                options: services,
                reqd: 1,
                onchange() {
                    toggle_ruc_note_field(d);
                }
            },
            {
                fieldname: "note",
                fieldtype: "Text Editor",
                label: "Required",
                // depends_on: "eval:doc.service === 'RUC'",
                hidden: 1
            }
        ],
        primary_action_label: "Forward",
        primary_action(values) {
            if (!values.note) {
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

    if (service) {
        dialog.set_df_property("note", "hidden", 0);
        dialog.set_df_property("note", "reqd", 1);
    } 

    dialog.refresh();
}

function get_stage_json(frm) {
    return new Promise((resolve) => {
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Customer",
                name: frm.doc.name,
            },
            callback: function (r) {
                if (!r.message || !r.message.stage) {
                    resolve([]);   // no stage yet
                    return;
                }

                try {
                    const parsedStage = JSON.parse(r.message.stage);
                    // parsedStage.count = 0
                    console.log("daata" , parsedStage)
                    resolve(Object.keys(parsedStage) , parsedStage)
                    // resolve(parsedStage);
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

function forward_candidate(frm, values) {
    frappe.call({
        method: "verp_staffing.crm.api.auto_assign.forward_candidate",
        args: {
            customer: frm.doc.name,
            service: values.service
        },
        callback(r) {
    const excludeServices = ["Resume", "RUC", "JDC", "Training", "Cover letter", "Marketing"];
    
    const noteDoctype = !excludeServices.includes(values.service) 
        ? "Technical Other Services" 
        : values.service;
    
    frappe.call({
        method: "verp_staffing.crm.api.notes.add_note",
        args: {
            reference_doctype: noteDoctype,
            reference_name: r.message.name,
            note: values.note
        },
        error() {
            frappe.msgprint("Failed to add note");
            d.enable_primary_action();
        }
    });
    
    frappe.msgprint(
        `Candidate forwarded for ${values.service} and assigned automatically.`
    );
    frm.reload_doc();
    }

    });
}

function inject_department_css() {
    if (!document.getElementById("status-badge-css")) {

        const style = document.createElement("style");
        style.id = "status-badge-css";
        style.innerHTML = `
        .status-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-success {
            background: #e6f4ea;
            color: #1e7e34;
        }

        .status-warning {
            background: #fff4e5;
            color: #b26a00;
        }

        .status-neutral {
            background: #f0f0f0;
            color: #555;
        }
        `;
        document.head.appendChild(style);
    }
    if (!document.getElementById("department-panel-css")) {

        const style = document.createElement("style");
        style.id = "department-panel-css";
        style.innerHTML = `
        .department-box {
            border: 1px solid #e0e0e0;
            padding: 12px;
            border-radius: 6px;
            background: #fafafa;
            margin-bottom: 10px;
        }
    `;
        document.head.appendChild(style);
    }
}

//load data of each department
function load_department_panels(frm) {
    frappe.call({
        method: "verp_staffing.crm.api.customer.get_customer_department_panels",
        args: {
            customer: frm.doc.name
        },
        callback(r) {
            if (!r.message) return;

            render_resume_panel(frm, r.message.resume);
            render_technical_panel(frm, r.message.technical);
            render_marketing_panel(frm, r.message.marketing);
        }
    });
}

function render_resume_panel(frm, data) {
    const wrapper = frm.fields_dict.resume_html.$wrapper;

    if (!data) {
        wrapper.html(`<div class="text-muted">Resume not forwarded yet.</div>`);
        return;
    }

    const status_html = get_status_badge(data.status);

    const html = `
        <div class="department-box">
            <h4>Resume Department</h4>
            <p><strong>Status:</strong> ${status_html}</p>
            <p><strong>Assigned To:</strong> ${frappe.utils.escape_html(
        data.assign_to || "-"
    )}</p>
            <p class="text-muted">
                Last Updated: ${frappe.datetime.str_to_user(data.last_updated)}
            </p>
        </div>
    `;

    wrapper.html(html);
}

function render_technical_panel(frm, data) {
    const wrapper = frm.fields_dict.technical_content.$wrapper;

    if (!data || !data.length) {
        wrapper.html(`<div class="text-muted">Not forwarded to Technical yet.</div>`);
        return;
    }

    let html = "";

    data.forEach(item => {
        const status_html = get_status_badge(item.status);

        html += `
            <div class="department-box">
                <h4> Services : ${item.name}</h4>
                <p><strong>Status:</strong> ${status_html}</p>
                <p><strong>Assigned To:</strong> ${frappe.utils.escape_html(
                    item.assign_to || "-"
                )}</p>
                <p class="text-muted">
                    Last Updated: ${frappe.datetime.str_to_user(item.last_updated)}
                </p>
            </div>
        `;
    });

    wrapper.html(html);
}

function render_marketing_panel(frm, data) {
    const wrapper = frm.fields_dict.marketing_content.$wrapper;

    if (!data) {
        wrapper.html(`<div class="text-muted">Not forwarded to Marketing yet.</div>`);
        return;
    }

    let status_label = "No Interviews";
    let badge_class = "gray";

    if (data.current_interviews > 0) {
        status_label = "In Progress";
        badge_class = "blue";
    } else if (data.total_interviews > 0) {
        status_label = "Completed";
        badge_class = "green";
    }

    const html = `
        <div class="department-box">
            <h4>Marketing Department</h4>

            <p>
                <strong>Status:</strong>
                <span class="indicator ${badge_class}">${status_label}</span>
            </p>

            <p>
                <strong>Assigned To:</strong>
                ${frappe.utils.escape_html(data.assign_to || "-")}
            </p>

            <p>
                <strong>Total Interviews:</strong> ${data.total_interviews}
            </p>

            <p>
                <strong>Current Interviews:</strong> ${data.current_interviews}
            </p>

            <p class="text-muted">
                Last Updated: ${frappe.datetime.str_to_user(data.last_updated)}
            </p>
        </div>
    `;

    wrapper.html(html);
}

function get_status_badge(status) {
    const s = (status || "").toLowerCase();

    if (s.includes("completed") || s.includes("done")) {
        return `<span class="status-badge status-success">${frappe.utils.escape_html(status)}</span>`;
    }

    if (s.includes("pending") || s.includes("open")) {
        return `<span class="status-badge status-warning">${frappe.utils.escape_html(status)}</span>`;
    }

    return `<span class="status-badge status-neutral">${frappe.utils.escape_html(status || "-")}</span>`;
}

function inject_status_badge_css() {

}
