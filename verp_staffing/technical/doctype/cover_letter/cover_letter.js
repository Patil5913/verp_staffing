// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cover Letter", {
	refresh(frm) {
        render_notes(frm);
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
            reference_doctype: "Cover Letter",
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
                    get_notes(frm, $wrapper);
                }
            });
        });
    });
}

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
                    get_notes(frm, $wrapper);
                }
            });
        }
    });
    d.show();
}

async function add_forward_button(frm) {
	frm.add_custom_button("Forward Candidate", async () => {
		const forwarded = await get_stage_json(frm);

		frappe.call({
			method: "verp_staffing.crm.doctype.customer.customer.get_forwardable_departments",
			args: {
				customer: frm.doc.customer,
			},
			callback(r) {
				let services = r.message;
				services = services.filter((i) => i !== frm.doctype);				if (services.length === 0) {
					frappe.msgprint("No services available for forwarding.");
					return;
				}

				open_forward_prompt(frm, services);
			},
		});
	});
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
				},
			},
			{
				fieldname: "note",
				fieldtype: "Text Editor",
				label: "Required",
				// depends_on: "eval:doc.service === 'RUC'",
				hidden: 1,
			},
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
		},
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
				name: frm.doc.customer,
			},
			callback: function (r) {
				if (!r.message || !r.message.stage) {
					resolve([]); // no stage yet
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
			},
		});
	});
}

function forward_candidate(frm, values) {
	frappe.call({
		method: "verp_staffing.crm.api.auto_assign.forward_candidate",
		args: {
			customer: frm.doc.customer,
			service: values.service,
		},
		callback(r) {
			// const excludeServices = ["resume", "ruc", "jdc", "training", "cover letter", "marketing"];

			const noteDoctype = r.message.doctype;
			console.log("noteDoctype: ", noteDoctype);
			frappe.call({
				method: "verp_staffing.crm.api.notes.add_note",
				args: {
					reference_doctype: noteDoctype,
					reference_name: r.message.name,
					note: values.note,
				},
				error() {
					frappe.msgprint("Failed to add note");
					d.enable_primary_action();
				},
			});

			frappe.msgprint(
				`Candidate forwarded for ${values.service} and assigned automatically.`,
			);
			frm.reload_doc();
		},
	});
}
