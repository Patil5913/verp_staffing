// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer", {
	refresh(frm) {
        render_notes(frm);
        add_note_button(frm);
	},
});

function add_note_button(frm) {
    frm.add_custom_button(__("Add Note"), function () {
        frappe.new_doc("Note", {
            reference_doctype: "Customer",
            reference_name: frm.doc.name,
            public: 0
        });
    }, __("Create"));
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
                <div class="mt-2">
                    <button class="btn btn-secondary btn-sm add-note-inline">Add Note</button>
                </div>
            `;

            $wrapper.html(html);

            $wrapper.find(".add-note-inline").on("click", () => open_add_note_dialog(frm, $wrapper));
            attach_edit_delete_events(frm, $wrapper);
        }
    });
}


function open_add_note_dialog(frm,$wrapper) {
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
                    get_notes(frm,$wrapper);
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


// EDIT - dialog
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
