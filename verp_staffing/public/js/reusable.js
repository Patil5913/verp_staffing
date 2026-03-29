window.LeadCourse = {
	validate_mm_yyyy(value) {
		return /^(0[1-9]|1[0-2])-[0-9]{4}$/.test(value);
	},

	validate_grade(value) {
		value = Number(value || 0);
		return value >= 0 && value <= 10;
	},

	check_row(row) {
		if (row.start_date && !this.validate_mm_yyyy(row.start_date)) {
			frappe.msgprint({
				title: __("Invalid Format"),
				message: __("Start Date must be in MM-YYYY format (example: 02-2025)"),
				indicator: "red",
			});
			row.start_date = "";
		}

		if (row.end_date && !this.validate_mm_yyyy(row.end_date)) {
			frappe.msgprint({
				title: __("Invalid Format"),
				message: __("End Date must be in MM-YYYY format (example: 02-2025)"),
				indicator: "red",
			});
			row.end_date = "";
		}

		if (row.grade && !this.validate_grade(row.grade)) {
			frappe.msgprint({
				title: __("Invalid Format"),
				message: __("Grade must be between 0 and 10"),
				indicator: "red",
			});
			row.grade = "";
		}
	},
};

window.render_customer_related_html = function ({ frm, html_field, customer, fields }) {
	if (!customer) {
		frm.set_df_property(
			html_field,
			"options",
			"<p style='text-align: center; color: #6b7280; padding: 20px;'>No customer selected</p>",
		);
		return;
	}

	frappe.call({
		method: "verp_staffing.vrugle_staffing_erp.utils.customer_data.get_data_by_customer",
		args: { customer, fields },
		callback(r) {
			const records = r.message || [];

			if (!Array.isArray(records) || !records.length) {
				frm.set_df_property(
					html_field,
					"options",
					"<p style='text-align:center;color:#6b7280;padding:20px;'>No records found</p>",
				);
				return;
			}

			window.showFullPreview = function (content) {
				const existing = document.querySelector(".full-preview-overlay");
				if (existing) existing.remove();

				const overlay = document.createElement("div");
				overlay.className = "full-preview-overlay";

				overlay.innerHTML = `
                <div class="full-preview-box">
                    <div class="preview-header">
                        <span>Description</span>
                        <button class="close-preview-btn">Close</button>
                    </div>
                    <div class="preview-body">${content}</div>
                </div>
            `;

				overlay.querySelector(".close-preview-btn").onclick = () => overlay.remove();
				overlay.onclick = (e) => {
					if (e.target === overlay) overlay.remove();
				};

				document.body.appendChild(overlay);
			};

			let html = `
        <style>
            .customer-data-container {
                width: 100%;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            }

            .record-section {
                margin-bottom: 30px;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background: #ffffff;
                overflow: hidden;
            }

            .fields-container {
                padding: 16px;
            }

            .field-row {
                display: grid;
                grid-template-columns: 200px 1fr;
                gap: 16px;
                padding: 10px 0;
                border-bottom: 1px solid #f1f3f5;
            }

            .field-row:last-child {
                border-bottom: none;
            }

            .field-label {
                font-size: 13px;
                font-weight: 600;
                color: #495057;
            }

            .field-value {
                font-size: 13px;
                color: #212529;
                word-break: break-word;
            }

            .table-section {
                margin-top: 20px;
                padding: 16px;
                background: #f8f9fa;
                border-top: 2px solid #dee2e6;
            }

            .table-title {
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 12px;
                color: #374151;
            }

            .table-wrapper {
                overflow-x: auto;
                background: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }

            table.data-table {
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
                font-size: 13px;
                min-width: 600px;
            }

            table.data-table th,
            table.data-table td {
                padding: 10px 12px;
                border-bottom: 1px solid #f1f3f5;
                word-break: break-word;
                overflow-wrap: break-word;
                white-space: normal;
            }

            table.data-table thead {
                background: #e9ecef;
            }

            table.data-table tbody tr:hover {
                background-color: #f8f9fa;
            }

            .full-preview-overlay {
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.55);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            }

            .full-preview-box {
                background: #ffffff;
                width: 90%;
                max-width: 800px;
                max-height: 80vh;
                border-radius: 10px;
                padding: 20px;
                overflow-y: auto;
                box-shadow: 0 10px 30px rgba(0,0,0,0.25);
            }

            .preview-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                font-weight: 600;
                font-size: 16px;
            }

            .close-preview-btn {
                background: #ef4444;
                border: none;
                color: white;
                padding: 6px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
            }

            .close-preview-btn:hover {
                background: #dc2626;
            }

            .preview-body {
                font-size: 14px;
                line-height: 1.6;
                white-space: pre-wrap;
            }
        </style>

        <div class="customer-data-container">
        `;

			records.forEach((record) => {
				html += `<div class="record-section">`;

				if (record.fields?.length) {
					html += `<div class="fields-container">`;

					record.fields.forEach((f) => {
						if (!f.value) return;

						const value = frappe.utils.escape_html(String(f.value));

						html += `
                        <div class="field-row">
                            <div class="field-label">${frappe.utils.escape_html(f.label)}</div>
                            <div class="field-value">${value}</div>
                        </div>
                    `;
					});

					html += `</div>`;
				}

				if (record.tables?.length) {
					record.tables.forEach((table) => {
						if (!table.rows?.length) return;

						const tableLabel =
							table.label ||
							table.fieldname
								.replace(/_/g, " ")
								.replace(/\b\w/g, (l) => l.toUpperCase());

						const isWide = table.columns.length > 7;

						html += `
                        <div class="table-section">
                            <div class="table-title">${frappe.utils.escape_html(tableLabel)}</div>
                            <div class="table-wrapper">
                                <table class="data-table" style="${isWide ? "min-width:1200px;" : ""}">
                                    <thead>
                                        <tr>
                    `;

						table.columns.forEach((col) => {
							html += `<th>${frappe.utils.escape_html(col.label)}</th>`;
						});

						html += `
                                        </tr>
                                    </thead>
                                    <tbody>
                    `;

						table.rows.forEach((row) => {
							html += `<tr>`;

							table.columns.forEach((col) => {
								const cellValue = row[col.fieldname];
								const text = cellValue != null ? String(cellValue) : "";
								const escapedText = frappe.utils.escape_html(text);

								if (text.length > 100) {
									const shortText =
										frappe.utils.escape_html(text.substring(0, 35)) + "...";

									html += `
                                    <td style="width:500px; max-width:500px;">
                                        <span style="cursor:pointer; color:#2563eb; font-weight:500;"
                                              onclick="showFullPreview(\`${escapedText.replace(/`/g, "\\`")}\`)">
                                            ${shortText}
                                        </span>
                                    </td>
                                `;
								} else {
									html += `<td>${escapedText}</td>`;
								}
							});

							html += `</tr>`;
						});

						html += `
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    `;
					});
				}

				html += `</div>`;
			});

			html += `</div>`;

			frm.set_df_property(html_field, "options", html);
		},
	});
};

// --------------------- forward - button --------------------------

window.add_forward_button = async function add_forward_button(frm) {
	frm.add_custom_button("Forward Candidate", async () => {
		let method = "";
		let args = {};

		if (frm.doctype === "Customer") {
			method = "verp_staffing.crm.doctype.customer.customer.get_forwardable_departments";
			args = {
				customer: frm.doc.name,
			};
		} else {
			method =
				"verp_staffing.crm.doctype.customer.customer.get_forwardable_departments_from_service";
			args = {
				doctype: frm.doctype,
				docname: frm.doc.name,
			};
		}

		frappe.call({
			method: method,
			args: args,
			callback(r) {
				let services = r.message || [];

				if (!services.length) {
					frappe.msgprint("No services available for forwarding.");
					return;
				}

				services = services.filter((s) => s.toLowerCase() !== frm.doctype.toLowerCase());

				if (!services.length) {
					frappe.msgprint("No other services available for forwarding.");
					return;
				}

				open_forward_prompt(frm, services);
			},
		});
	});
};

function toggle_manual_assign(dialog) {
	const manual = dialog.get_value("manual_assign");

	dialog.set_df_property("assign_employee", "hidden", !manual);
	dialog.set_df_property("assign_employee", "reqd", manual);

	dialog.refresh();
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
					toggle_fields(d, frm);
				},
			},
			{
				fieldname: "note",
				fieldtype: "Text Editor",
				label: "Required",
				hidden: 1,
			},
			{
				fieldname: "interview",
				fieldtype: "Select",
				label: "Select Interview",
				hidden: 1,
				options: [],
			},
			{
				fieldname: "manual_assign",
				fieldtype: "Check",
				label: "Assign Manually",
				default: 0,
				hidden: 1,
				onchange() {
					toggle_manual_assign(d);
				},
			},
			{
				fieldname: "position",
				label: "Position",
				fieldtype: "Data",
				hidden: 1,
			},

			{
				fieldname: "placement_company",
				label: "Placement Company",
				fieldtype: "Data",
				hidden: 1,
			},

			{
				fieldname: "job_duration",
				label: "Job Type/Duration",
				fieldtype: "Data",
				hidden: 1,
			},

			{
				fieldname: "salary",
				label: "Salary",
				fieldtype: "Currency",
				hidden: 1,
			},

			{
				fieldname: "company_percentage",
				label: "Company Percentage",
				fieldtype: "Float",
				hidden: 1,
			},
			{
				fieldname: "assign_employee",
				label: "Assign To",
				fieldtype: "Link",
				options: "Employee",
				hidden: 1,
				get_query: function () {
					return {
						filters: [["Employee Assignment Detail", "department", "=", "Onboarding"]],
					};
				},
			},
		],
		primary_action_label: "Forward",
		primary_action(values) {
			if (values.service === "RUC" && !values.note) {
				frappe.msgprint("Note is required for RUC.");
				return;
			}

			if (values.service === "JDC" && !values.interview) {
				frappe.msgprint("Please select Interview for JDC.");
				return;
			}
			if (values.service?.toLowerCase() === "onboarding") {
				const required_fields = [
					"position",
					"placement_company",
					"job_duration",
					"salary",
					"company_percentage",
				];

				for (let field of required_fields) {
					if (!values[field]) {
						frappe.msgprint(`${field.replace("_", " ")} is required`);
						return;
					}
				}
			}
			d.disable_primary_action();
			forward_candidate(frm, values);
			d.hide();
		},
	});

	d.show();
}

function toggle_fields(dialog, frm) {
	const service = dialog.get_value("service");
	const serviceLower = service?.toLowerCase();

	// reset everything first
	const fields_to_hide = [
		"note",
		"interview",
		"manual_assign",
		"assign_employee",
		"position",
		"placement_company",
		"job_duration",
		"salary",
		"company_percentage",
	];

	fields_to_hide.forEach((f) => {
		dialog.set_df_property(f, "hidden", 1);
		dialog.set_df_property(f, "reqd", 0);
	});

	if (!service) {
		dialog.refresh();
		return;
	}

	// Onboarding logic
	if (serviceLower === "onboarding") {
		dialog.set_df_property("manual_assign", "hidden", 0);

		const onboarding_fields = [
			"position",
			"placement_company",
			"job_duration",
			"salary",
			"company_percentage",
		];

		onboarding_fields.forEach((f) => {
			dialog.set_df_property(f, "hidden", 0);
			dialog.set_df_property(f, "reqd", 1);
		});

		dialog.refresh();
		return;
	}
	//  CR
	if (serviceLower === "cr") {
		dialog.set_df_property("manual_assign", "hidden", 0);

		dialog.refresh();
		return;
	}

	// ------------------------------
	// Default services logic
	// ------------------------------

	dialog.set_df_property("note", "hidden", 0);

	if (serviceLower === "jdc") {
		frappe.call({
			method: "verp_staffing.crm.api.auto_assign.get_customer_interviews",
			args: {
				customer: frm.doc.customer || frm.doc.name,
			},
			callback(r) {
				const interviews = r.message || [];

				if (!interviews.length) {
					frappe.msgprint({
						title: __("No Interview"),
						message: __("This customer does not have any interview."),
						indicator: "orange",
					});

					dialog.set_df_property("interview", "hidden", 1);
					dialog.set_df_property("interview", "reqd", 0);
					dialog.refresh();
					return;
				}

				dialog.set_df_property("interview", "options", interviews);
				dialog.set_df_property("interview", "hidden", 0);
				dialog.set_df_property("interview", "reqd", 1);
				dialog.refresh();
			},
		});
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
					resolve([]);
					return;
				}

				try {
					const parsedStage = JSON.parse(r.message.stage);
					// parsedStage.count = 0
					resolve(Object.keys(parsedStage), parsedStage);
					// resolve(parsedStage);
				} catch (e) {
					console.warn("Invalid stage JSON");
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
			customer: frm.doc.customer || frm.doc.name,
			service: values.service,
			interview: values.interview || null,
			assign_employee: values.assign_employee || null,
			// Onboarding Fields
			position: values.position || null,
			placement_company: values.placement_company || null,
			job_duration: values.job_duration || null,
			salary: values.salary || null,
			company_percentage: values.company_percentage || null,
		},
		callback(r) {
			const noteDoctype = r.message.doctype;
			if (values.note) {
				frappe.call({
					method: "verp_staffing.crm.api.notes.add_note",
					args: {
						reference_doctype: noteDoctype,
						reference_name: r.message.name,
						current_doctype: frm.doctype,
						note: values.note,
					},
				});
			}
			frappe.msgprint(
				`Candidate forwarded for ${values.service} and assigned automatically.`,
			);

			frm.reload_doc();
		},
	});
}

// --------------------- Notes and Updtea --------------------------

window.render_notes = function (frm) {
	const notes_field = frm.get_field("notes_html");
	const updates_field = frm.get_field("updates_html");

	if (!notes_field || !updates_field) return;

	const $notes_wrapper = notes_field.$wrapper;
	const $updates_wrapper = updates_field.$wrapper;

	if (!frm.doc.name) {
		$notes_wrapper.html(`<div class="text-muted p-3">Save to view Notes.</div>`);
		$updates_wrapper.html(`<div class="text-muted p-3">Save to view Updates.</div>`);
		return;
	}

	load_notes(frm, $notes_wrapper, $updates_wrapper);
};

function load_notes(frm, $notes_wrapper, $updates_wrapper) {
	$notes_wrapper.html(`<div class="p-3 text-muted">Loading...</div>`);
	if (frm.doctype === "Customer" || frm.doctype === "Opportunity" || frm.doctype === "Lead") {
		$updates_wrapper.closest(".form-group, .section-body, .frappe-control").hide();
	} else {
		$updates_wrapper.closest(".form-group, .section-body, .frappe-control").show();
		$updates_wrapper.html(`<div class="p-3 text-muted">Loading...</div>`);
	}
	frappe.call({
		method: "verp_staffing.crm.api.notes.get_notes",
		args: {
			reference_doctype: frm.doctype,
			reference_name: frm.doc.name,
		},
		callback: function (r) {
			if (!r.message) return;

			const notes = r.message.notes || [];
			const updates = r.message.updates || [];

			if (!notes.length) {
				$notes_wrapper.html(`
					<div class="p-3 text-center">
						<div class="text-muted mb-2">No notes yet.</div>
						<button class="btn btn-primary btn-sm add-note-btn">Add Note</button>
					</div>
				`);
			} else {
				let html = `
					<div class="mb-2">
						<button class="btn btn-secondary btn-sm add-note-btn">Add Note</button>
					</div>
					<div class="list-group">
				`;

				notes.forEach((n) => {
					const added_on = frappe.datetime.str_to_user(n.added_on);

					html += `
						<div class="list-group-item" data-id="${n.name}">
							<div class="d-flex justify-content-between">
								<div>
									<b>${n.added_by}</b>
									<span class="text-muted ml-2">${added_on}</span>
								</div>
								<div>
									<span class="text-primary edit-note mr-2" style="cursor:pointer;">Edit</span>
									<span class="text-danger delete-note" style="cursor:pointer;">Delete</span>
								</div>
							</div>
							<div class="note-content mt-2">${n.note}</div>
						</div>
					`;
				});

				html += `</div>`;
				$notes_wrapper.html(html);
			}

			if (!updates.length) {
				$updates_wrapper.html(`
					<div class="p-3 text-muted text-center">
						No updates available.
					</div>
				`);
			} else {
				let html = `<div class="list-group">`;

				updates.forEach((u) => {
					const added_on = frappe.datetime.str_to_user(u.added_on);

					html += `
						<div class="list-group-item">
							<div>
								<b>${u.added_by}</b>
								<span class="text-muted ml-2">${added_on}</span>
							</div>
							<div class="mt-2">${u.note}</div>
						</div>
					`;
				});

				html += `</div>`;
				$updates_wrapper.html(html);
			}

			// Attach events ONLY for notes tab
			$notes_wrapper
				.find(".add-note-btn")
				.on("click", () => open_add_note_dialog(frm, $notes_wrapper));

			attach_edit_delete_events(frm, $notes_wrapper);
		},
	});
}

function refresh_notes(frm) {
	const notes_field = frm.get_field("notes_html");
	const updates_field = frm.get_field("updates_html");

	if (!notes_field || !updates_field) return;

	load_notes(frm, notes_field.$wrapper, updates_field.$wrapper);
}

function open_add_note_dialog(frm, $wrapper) {
	const d = new frappe.ui.Dialog({
		title: __("Add Note"),
		fields: [{ fieldname: "note", fieldtype: "Text Editor", label: "Note", reqd: 1 }],
		primary_action_label: __("Save"),
		primary_action(values) {
			if (!values.note) return;
			d.disable_primary_action();
			frappe.call({
				method: "verp_staffing.crm.api.notes.add_note",
				args: {
					reference_doctype: frm.doctype,
					reference_name: frm.doc.name,
					current_doctype: frm.doctype,
					note: values.note,
				},
				callback(r) {
					frappe.show_alert({ message: __("Note added"), indicator: "green" });
					d.hide();
					refresh_notes(frm, $wrapper);
				},
				error() {
					frappe.msgprint(__("Failed to add note"));
					d.enable_primary_action();
				},
			});
		},
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
					refresh_notes(frm, $wrapper);
				},
			});
		});
	});
}

function open_edit_note_dialog(frm, $wrapper, note_id, old_note) {
	const d = new frappe.ui.Dialog({
		title: "Edit Note",
		fields: [
			{
				fieldname: "note",
				fieldtype: "Text Editor",
				label: "Note",
				reqd: 1,
				default: old_note,
			},
		],
		primary_action_label: "Update",
		primary_action(values) {
			frappe.call({
				method: "verp_staffing.crm.api.notes.update_note",
				args: {
					note_id,
					note: values.note,
				},
				callback: () => {
					frappe.show_alert("Note updated");
					d.hide();
					get_notes(frm, $wrapper);
				},
			});
		},
	});
	d.show();
}

function get_notes(frm, $wrapper) {
	$wrapper.html(`<div class="p-3 text-muted">Loading notes...</div>`);

	frappe.call({
		method: "verp_staffing.crm.api.notes.get_notes",
		args: {
			reference_doctype: frm.doctype,
			reference_name: frm.doc.name,
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
				$wrapper
					.find(".add-note-btn")
					.on("click", () => open_add_note_dialog(frm, $wrapper));
				return;
			}

			let html = `
	            <div class="mt-2 mb-2">
	                    <button class="btn btn-secondary btn-sm add-note-inline">Add Note</button>
	                </div>
	                <div class="notes-list list-group">
	            `;

			notes.forEach((n) => {
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

			$wrapper
				.find(".add-note-inline")
				.on("click", () => open_add_note_dialog(frm, $wrapper));
			attach_edit_delete_events(frm, $wrapper);
		},
	});
}

// --------------------- activity --------------------------

window.render_activity_section = function render_activity_section(frm) {
	if (!frm.doc.name) return;
	let $wrapper = frm.get_field("open_activities_html")?.$wrapper;
	if (!$wrapper) return;
	frappe.call({
		method: "verp_staffing.crm.api.activities.get_open_activities",
		args: {
			reference_doctype: frm.doc.doctype,
			reference_name: frm.doc.name,
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
                        ${
							tasks.length == 0
								? `<p>No open tasks</p>`
								: tasks.map((t) => render_task_card(t, frm)).join("")
						}
                    </div>
                </div>
                <div style="width:50%">
                    <h4>Events 
                        <button class="btn btn-sm btn-secondary add-event-btn" style="margin-left: 10px;">+ Add Event</button>
                    </h4>
                    <div class="event-list">
                        ${
							events.length == 0
								? `<p>No events</p>`
								: events.map((e) => render_event_card(e, frm)).join("")
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
		},
	});
};
//create task
function open_new_task_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Create Task"),
		fields: [
			{ label: "Description", fieldname: "description", fieldtype: "Small Text", reqd: 1 },
			{
				label: "Date",
				fieldname: "date",
				fieldtype: "Datetime",
				default: frappe.datetime.now_datetime(),
				reqd: 1,
			},
			{ label: "Assigned To", fieldname: "assigned_to", fieldtype: "Link", options: "User" },
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
					reference_doctype: frm.doc.doctype,
					reference_name: frm.doc.name,
					description: values.description,
					date: values.date,
					assigned_to: values.assigned_to,
				},
				callback(r) {
					frappe.show_alert({ message: __("Task created"), indicator: "green" });
					d.hide();
					render_activity_section(frm);
				},
				error() {
					frappe.msgprint(__("Failed to add task"));
					d.enable_primary_action();
				},
			});
		},
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
			callback: () => render_activity_section(frm),
		});
	});
}

// edit task
function open_edit_task_dialog(task_name, frm) {
	frappe.db.get_doc("CRM Task", task_name).then((doc) => {
		let d = new frappe.ui.Dialog({
			title: __("Edit Task"),
			fields: [
				{
					label: "Description",
					fieldname: "description",
					fieldtype: "Small Text",
					default: doc.description,
					reqd: 1,
				},
				{ label: "Date", fieldname: "date", fieldtype: "Datetime", default: doc.date },
				{
					label: "Assigned To",
					fieldname: "assigned_to",
					fieldtype: "Link",
					options: "User",
					default: doc.assigned_to,
				},
				{
					label: "Completed?",
					fieldname: "is_completed",
					fieldtype: "Check",
					default: doc.is_completed,
				},
			],
			primary_action_label: __("Update"),
			primary_action(values) {
				frappe.call({
					method: "verp_staffing.crm.api.activities.mark_task_complete",
					args: {
						task_name: task_name,
						completed: values.is_completed ? 1 : 0,
					},
				});

				frappe.db
					.set_value("CRM Task", task_name, {
						description: values.description,
						date: values.date,
						assigned_to: values.assigned_to,
					})
					.then(() => {
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
					},
				});
			},
		});

		d.show();
	});
}

// create event
function open_new_event_dialog(frm) {
	let d = new frappe.ui.Dialog({
		title: __("Create Event"),
		fields: [
			{
				label: "Category",
				fieldname: "category",
				fieldtype: "Select",
				options: "Event\nMeeting\nCall\nFollow Up\nOther",
				reqd: 1,
			},
			{
				label: "Date",
				fieldname: "date",
				fieldtype: "Datetime",
				default: frappe.datetime.now_datetime(),
				reqd: 1,
			},
			{ label: "Summary", fieldname: "summary", fieldtype: "Data", reqd: 1 },
			{ label: "Description", fieldname: "description", fieldtype: "Text Editor" },
			{ label: "Assigned To", fieldname: "assigned_to", fieldtype: "Link", options: "User" },
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			frappe.call({
				method: "verp_staffing.crm.api.activities.create_event",
				args: {
					reference_doctype: frm.doc.doctype,
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
				},
			});
		},
	});

	d.show();
}

// edit event
function open_edit_event_dialog(event_name, frm) {
	frappe.db.get_doc("CRM Event", event_name).then((doc) => {
		let d = new frappe.ui.Dialog({
			title: __("Edit Event"),
			fields: [
				{
					label: "Category",
					fieldname: "category",
					fieldtype: "Select",
					options: "Event\nMeeting\nCall\nFollow Up\nOther",
					default: doc.category,
					reqd: 1,
				},
				{
					label: "Date",
					fieldname: "date",
					fieldtype: "Datetime",
					default: doc.date,
					reqd: 1,
				},
				{
					label: "Summary",
					fieldname: "summary",
					fieldtype: "Data",
					default: doc.summary,
					reqd: 1,
				},
				{
					label: "Description",
					fieldname: "description",
					fieldtype: "Text Editor",
					default: doc.description,
				},
				{
					label: "Assigned To",
					fieldname: "assigned_to",
					fieldtype: "Link",
					options: "User",
					default: doc.assigned_to,
				},
			],
			primary_action_label: __("Update"),
			primary_action(values) {
				frappe.db
					.set_value("CRM Event", event_name, {
						summary: values.summary,
						date: values.date,
						description: values.description,
						category: values.category,
						assigned_to: values.assigned_to,
					})
					.then(() => {
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
					},
				});
			},
		});

		d.show();
	});
}

// Show lates uploaded resume

window.fetch_and_render_resume = function fetch_and_render_resume(frm) {
	if (!frm.doc.customer) {
		frm.set_df_property(
			"resume",
			"options",
			"<div style='color:#888'>No customer selected</div>",
		);
		return;
	}
	frappe.db
		.get_list("Resume", {
			filters: {
				customer: frm.doc.customer,
			},
			fields: ["name", "resume"],
			order_by: "creation desc",
			limit: 1,
		})
		.then((res) => {
			if (!res || !res.length || !res[0].resume) {
				frm.set_df_property(
					"resume",
					"options",
					"<div style='color:#888'>No resume uploaded</div>",
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
};

// ------------------- request for update button ------------------------

// ── Updatable fields — all possible fields across all service doctypes ──
const SERVICE_UPDATABLE_FIELDS = {
	surname: "Surname",
	first_name: "First Name",
	father_name: "Father Name",
	email: "Email",
};

window.setup_service_permission_button = function (frm) {
	if (!frm.doc.customer || !frm.doc.name) return;

	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Employee",
			filters: { user: frappe.session.user },
			fieldname: "name",
		},
		callback: function (emp_res) {
			if (!emp_res.message) return;
			const employee = emp_res.message.name;

			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: frm.doctype,
					filters: { name: frm.doc.name },
					fieldname: "assign_to",
				},
				callback: function (r) {
					if (!r.message) return;
					const is_assignee = employee === r.message.assign_to;

					frappe.call({
						method: "frappe.client.get_value",
						args: {
							doctype: "Customer",
							filters: { name: frm.doc.customer },
							fieldname: "customer_owner",
						},
						callback: function (cust_res) {
							if (!cust_res.message) return;
							const is_owner =
								is_assignee || employee === cust_res.message.customer_owner;

							if (!is_owner) {
								window._service_show_accept_updates(frm);
								return;
							}

							// Check if this employee already has a pending request
							frappe.call({
								method: "frappe.client.get_list",
								args: {
									doctype: "Comment",
									filters: {
										reference_doctype: "Customer",
										reference_name: frm.doc.customer,
										comment_type: "Info",
									},
									fields: ["name", "content"],
									limit_page_length: 20,
									order_by: "creation desc",
								},
								callback: function (comment_res) {
									const comments = comment_res.message || [];
									let has_pending = false;

									for (const c of comments) {
										try {
											const data = JSON.parse(c.content);
											if (
												data.type === "field_update_request" &&
												data.status === "Pending" &&
												data.requested_by_employee === employee
											) {
												has_pending = true;
												break;
											}
										} catch (e) {}
									}

									if (has_pending) {
										frappe.show_alert(
											{
												message: __(
													"Your update request is pending manager approval.",
												),
												indicator: "orange",
											},
											5,
										);
										return;
									}

									frm.add_custom_button(__("Update Detail"), () => {
										window._service_open_update_detail_dialog(
											frm,
											frm._update_detail_fields || null,
										);
									});
								},
							});
						},
					});
				},
			});
		},
	});
};

window._service_open_update_detail_dialog = function (frm, custom_fields) {
	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_lead_detail_field_values",
		args: { customer_name: frm.doc.customer },
		callback: function (r) {
			const current_values = r.message || {};
			const fields = custom_fields || SERVICE_UPDATABLE_FIELDS;
			_open_update_detail_dialog(frm, current_values, fields, "service");
		},
	});
};

window._service_show_accept_updates = function (frm) {
	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_pending_field_update_request",
		args: { customer_name: frm.doc.customer },
		callback(r) {
			$(`button:contains("Accept Updates")`).closest(".btn-group").remove();
			if (!r.message || !r.message.has_pending) return;

			frm.add_custom_button(__("Accept Updates"), () => {
				_open_accept_updates_dialog(
					frm,
					[
						{
							requested_by: r.message.requested_by,
							reason: r.message.reason,
							field_updates: r.message.field_updates,
							comment_name: r.message.comment_name,
						},
					],
					"service",
				);
			});
		},
	});
};

// ── Shared dialog builder — fields param controls which fields appear ──
function _open_update_detail_dialog(frm, current_values, fields, mode) {
	const customer_name = mode === "service" ? frm.doc.customer : frm.doc.name;
	const api_method =
		mode === "service"
			? "verp_staffing.crm.api.permission_request.request_field_update"
			: "verp_staffing.crm.api.permission_request.request_field_update_by_owner";

	const dialog_html = `
        <style>
            .fg-row {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 10px 12px;
                border: 0.5px solid var(--color-border-tertiary);
                border-radius: var(--border-radius-md);
                cursor: pointer;
                background: var(--color-background-primary);
                user-select: none;
            }
            .fg-row:hover { background: var(--color-background-secondary); }
            .fg-row.selected {
                border-color: #260fea;
                background: #EEEDFE;
            }
            .fg-cb {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1.5px solid var(--color-border-secondary);
                flex-shrink: 0;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .fg-row.selected .fg-cb {
                background: #260fea;
                border-color: #260fea;
            }
            .fg-tick {
                display: none;
                width: 8px;
                height: 5px;
                border-left: 2px solid white;
                border-bottom: 2px solid white;
                transform: rotate(-45deg) translate(1px, -1px);
            }
            .fg-row.selected .fg-tick { display: block; }
            .fg-label {
                font-size: 13px;
                font-weight: 500;
                color: var(--color-text-primary);
            }
            .fg-row.selected .fg-label { color: #3C3489; }
            .fg-input-block { margin-bottom: 14px; }
            .fg-input-block:last-child { margin-bottom: 0; }
            .fg-input-field-name {
                font-size: 12px;
                font-weight: 500;
                color: var(--color-text-secondary);
                margin-bottom: 6px;
            }
            .fg-input-cols {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }
            .fg-col-label {
                font-size: 11px;
                color: var(--color-text-tertiary);
                margin-bottom: 4px;
                text-transform: uppercase;
                letter-spacing: 0.4px;
                font-weight: 500;
            }
            .fg-current-val {
                padding: 8px 10px;
                background: var(--color-background-secondary);
                border: 0.5px solid var(--color-border-tertiary);
                border-radius: var(--border-radius-md);
                font-size: 13px;
                color: var(--color-text-secondary);
                min-height: 36px;
            }
            .fg-new-input {
                width: 100%;
                padding: 8px 10px;
                border: 0.5px solid var(--color-border-secondary);
                border-radius: var(--border-radius-md);
                font-size: 13px;
                background: var(--color-background-primary);
                color: var(--color-text-primary);
                box-sizing: border-box;
            }
            .fg-new-input:focus {
                outline: none;
                border-color: #260fea;
                box-shadow: 0 0 0 2px rgba(38,15,234,0.12);
            }
            .fg-divider {
                border: none;
                border-top: 0.5px solid var(--color-border-tertiary);
                margin: 16px 0;
            }
        </style>

        <p style="font-size:11px; font-weight:500; color:var(--color-text-tertiary);
            text-transform:uppercase; letter-spacing:0.6px; margin:0 0 12px;">
            ${__("Select field to update")}
        </p>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;" id="fg-grid">
            ${Object.entries(fields)
				.map(([fieldname, label]) => {
					const old_val = current_values[fieldname] || "";
					return `
                    <div class="fg-row"
                        data-fieldname="${fieldname}"
                        data-label="${label}"
                        data-current="${frappe.utils.escape_html(old_val)}">
                        <div class="fg-cb"><div class="fg-tick"></div></div>
                        <span class="fg-label">${label}</span>
                    </div>
                `;
				})
				.join("")}
        </div>

        <div id="fg-inputs-section" style="display:none;">
            <hr class="fg-divider" />
            <div id="fg-inputs-container"></div>
        </div>
    `;

	const dialog = new frappe.ui.Dialog({
		title: __("Update Detail"),
		fields: [
			{
				fieldname: "fields_html",
				fieldtype: "HTML",
				options: dialog_html,
			},
			{
				fieldname: "reason",
				fieldtype: "Small Text",
				label: __("Reason for Update"),
				reqd: 1,
				description: __("Explain why you need to update these fields."),
			},
		],
		primary_action_label: __("Send"),
		primary_action(values) {
			if (!values.reason) {
				frappe.msgprint(__("Please enter a reason."));
				return;
			}

			const field_updates = {};
			let has_selection = false;
			let missing_value = false;

			dialog.$wrapper.find(".fg-row.selected").each(function () {
				const fieldname = $(this).data("fieldname");
				const input = dialog.$wrapper.find(
					`#fg-inputs-container .fg-new-input[data-fieldname="${fieldname}"]`,
				);
				const new_val = input.val().trim();
				const old_val = input.data("old");

				if (!new_val) {
					frappe.msgprint(__(`Please enter new value for ${fields[fieldname]}.`));
					missing_value = true;
					return false;
				}

				field_updates[fieldname] = { old: old_val, new: new_val };
				has_selection = true;
			});

			if (missing_value) return;

			if (!has_selection) {
				frappe.msgprint(__("Please select at least one field to update."));
				return;
			}

			dialog.hide();

			frappe.call({
				method: api_method,
				args: {
					customer_name: customer_name,
					reason: values.reason,
					field_updates: JSON.stringify(field_updates),
				},
				callback(res) {
					if (res.message && res.message.status === "success") {
						frappe.show_alert(
							{
								message: __(
									`Request sent to manager <b>${res.message.manager_employee}</b>.`,
								),
								indicator: "blue",
							},
							7,
						);
						frm.reload_doc();
					}
				},
			});
		},
	});

	dialog.show();

	const _fg_saved = {};

	dialog.$wrapper.on("click", ".fg-row", function () {
		const fieldname = $(this).data("fieldname");
		const isSelected = $(this).toggleClass("selected").hasClass("selected");
		_fg_rebuild(dialog, fields, current_values, _fg_saved);
		if (isSelected) {
			setTimeout(() => {
				dialog.$wrapper
					.find(`#fg-inputs-container .fg-new-input[data-fieldname="${fieldname}"]`)
					.focus();
			}, 30);
		}
	});
}

function _fg_rebuild(dialog, fields, current_values, saved) {
	dialog.$wrapper.find(".fg-new-input").each(function () {
		saved[$(this).data("fieldname")] = $(this).val();
	});

	const selected = dialog.$wrapper.find(".fg-row.selected");
	const section = dialog.$wrapper.find("#fg-inputs-section");
	const container = dialog.$wrapper.find("#fg-inputs-container");

	if (!selected.length) {
		section.hide();
		container.empty();
		return;
	}

	section.show();
	container.empty();

	selected.each(function () {
		const fieldname = $(this).data("fieldname");
		const label = fields[fieldname];
		const old_val = current_values[fieldname] || "";

		container.append(`
            <div class="fg-input-block">
                <div class="fg-input-field-name">${label}</div>
                <div class="fg-input-cols">
                    <div>
                        <div class="fg-col-label">${__("Current")}</div>
                        <div class="fg-current-val">
                            ${frappe.utils.escape_html(old_val) || "—"}
                        </div>
                    </div>
                    <div>
                        <div class="fg-col-label">${__("New")}</div>
                        <input class="fg-new-input"
                            type="text"
                            data-fieldname="${fieldname}"
                            data-old="${frappe.utils.escape_html(old_val)}"
                            value="${frappe.utils.escape_html(saved[fieldname] || "")}"
                            placeholder="${__("Enter new value")}" />
                    </div>
                </div>
            </div>
        `);
	});
}

function _open_accept_updates_dialog(frm, pending_requests, mode) {
	const customer_name = mode === "service" ? frm.doc.customer : frm.doc.name;
	let all_html = "";

	pending_requests.forEach((req, idx) => {
		all_html += `
            <div style="margin-bottom:20px; border:0.5px solid var(--color-border-tertiary);
                border-radius:var(--border-radius-lg); overflow:hidden;">
                <div style="background:var(--color-background-secondary); padding:10px 15px;
                    border-bottom:0.5px solid var(--color-border-tertiary);">
                    <span style="font-size:13px; font-weight:500; color:var(--color-text-primary);">
                        ${__("Request")} ${idx + 1} — ${__("By:")} <b>${req.requested_by}</b>
                    </span><br>
                    <span style="font-size:12px; color:var(--color-text-secondary);">
                        ${__("Reason:")} ${req.reason}
                    </span>
                </div>
                <div style="padding:15px;">
        `;

		Object.entries(req.field_updates).forEach(([fieldname, values]) => {
			const label = SERVICE_UPDATABLE_FIELDS[fieldname] || fieldname;
			all_html += `
                <div style="display:grid; grid-template-columns:20px 1fr 1fr;
                    gap:10px; margin-bottom:12px; align-items:start;">
                    <div style="padding-top:18px;">
                        <div style="width:16px; height:16px; border-radius:4px;
                            border:1.5px solid #260fea; background:#260fea;
                            display:flex; align-items:center; justify-content:center;
                            cursor:pointer;" class="au-cb-box"
                            data-fieldname="${fieldname}"
                            data-comment="${req.comment_name}">
                            <div class="au-tick" style="width:8px; height:5px;
                                border-left:2px solid white; border-bottom:2px solid white;
                                transform:rotate(-45deg) translate(1px,-1px);"></div>
                        </div>
                        <input type="checkbox" class="approve-field-checkbox"
                            data-fieldname="${fieldname}"
                            data-comment="${req.comment_name}"
                            checked style="display:none;" />
                    </div>
                    <div>
                        <div style="font-size:11px; font-weight:500; color:var(--color-text-tertiary);
                            text-transform:uppercase; letter-spacing:0.4px; margin-bottom:4px;">
                            ${__("Current")}
                        </div>
                        <div style="font-size:12px; font-weight:500;
                            color:var(--color-text-secondary); margin-bottom:4px;">${label}</div>
                        <div style="padding:8px 10px; background:var(--color-background-secondary);
                            border:0.5px solid var(--color-border-tertiary);
                            border-radius:var(--border-radius-md); font-size:13px;
                            color:var(--color-text-secondary);">
                            ${frappe.utils.escape_html(values.old) || "—"}
                        </div>
                    </div>
                    <div>
                        <div style="font-size:11px; font-weight:500; color:var(--color-text-tertiary);
                            text-transform:uppercase; letter-spacing:0.4px; margin-bottom:4px;">
                            ${__("New")}
                        </div>
                        <div style="font-size:12px; font-weight:500;
                            color:var(--color-text-secondary); margin-bottom:4px;">&nbsp;</div>
                        <div style="padding:8px 10px; background:#EEEDFE;
                            border:0.5px solid #260fea;
                            border-radius:var(--border-radius-md); font-size:13px;
                            color:#3C3489; font-weight:500;">
                            ${frappe.utils.escape_html(values.new)}
                        </div>
                    </div>
                </div>
            `;
		});

		all_html += `</div></div>`;
	});

	const accept_dialog = new frappe.ui.Dialog({
		title: __("Accept Updates"),
		fields: [
			{
				fieldname: "fields_review",
				fieldtype: "HTML",
				options: all_html,
			},
		],
		primary_action_label: __("Done"),
		primary_action() {
			const by_comment = {};

			accept_dialog.$wrapper.find(".approve-field-checkbox:checked").each(function () {
				const fieldname = $(this).data("fieldname");
				const comment_name = $(this).data("comment");
				if (!by_comment[comment_name]) by_comment[comment_name] = [];
				by_comment[comment_name].push(fieldname);
			});

			if (!Object.keys(by_comment).length) {
				frappe.msgprint(__("Please approve at least one field."));
				return;
			}

			accept_dialog.hide();

			const promises = Object.entries(by_comment).map(([comment_name, fields]) =>
				frappe.call({
					method: "verp_staffing.crm.api.permission_request.apply_field_updates",
					args: {
						customer_name: customer_name,
						comment_name: comment_name,
						approved_fields: JSON.stringify(fields),
					},
				}),
			);

			Promise.all(promises).then(() => {
				frappe.show_alert(
					{
						message: __("Selected fields have been updated successfully."),
						indicator: "green",
					},
					6,
				);
				frm.reload_doc();
			});
		},
		secondary_action_label: __("Close"),
		secondary_action() {
			accept_dialog.hide();
		},
	});

	accept_dialog.show();

	accept_dialog.$wrapper.on("click", ".au-cb-box", function () {
		const fieldname = $(this).data("fieldname");
		const comment_name = $(this).data("comment");
		const checkbox = accept_dialog.$wrapper.find(
			`.approve-field-checkbox[data-fieldname="${fieldname}"][data-comment="${comment_name}"]`,
		);
		const is_checked = checkbox.prop("checked");
		checkbox.prop("checked", !is_checked);

		if (is_checked) {
			$(this).css({
				background: "var(--color-background-primary)",
				borderColor: "var(--color-border-secondary)",
			});
			$(this).find(".au-tick").hide();
		} else {
			$(this).css({ background: "#260fea", borderColor: "#260fea" });
			$(this).find(".au-tick").show();
		}
	});
}
