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

window.get_display_fields = async function (doctype) {
	try {
		const res = await frappe.db.get_single_value(
			"ERP Configuration",
			"department_display_form_fields",
		);
		// console.log("doctype" , doctype)
		const CONFIG = res ? JSON.parse(res) : {};
		// console.log(CONFIG)

		const key = Object.keys(CONFIG).find((k) => k.toLowerCase() === doctype.toLowerCase());
		// console.log("key" , key)

		const fields = key ? CONFIG[key] : [];

		return Array.isArray(fields) ? fields : [];
	} catch (e) {
		console.error("Error fetching display fields:", e);
		return [];
	}
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
			{
				label: "Description",
				fieldname: "description",
				fieldtype: "Small Text",
				reqd: 1,
			},
			{
				label: "Date",
				fieldname: "date",
				fieldtype: "Datetime",
				default: frappe.datetime.now_datetime(),
				reqd: 1,
			},
			{
				label: "Assigned To",
				fieldname: "assigned_to",
				fieldtype: "Link",
				options: "User",
			},
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
					frappe.show_alert({
						message: __("Task created"),
						indicator: "green",
					});
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
				{
					label: "Date",
					fieldname: "date",
					fieldtype: "Datetime",
					default: doc.date,
				},
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
			{
				label: "Description",
				fieldname: "description",
				fieldtype: "Text Editor",
			},
			{
				label: "Assigned To",
				fieldname: "assigned_to",
				fieldtype: "Link",
				options: "User",
			},
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

window.setup_service_permission_button = function (frm) {
	if (!frm.doc.customer || !frm.doc.name) return;

	frappe.call({
		method: "frappe.client.get_value",
		args: { doctype: "Employee", filters: { user: frappe.session.user }, fieldname: "name" },
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
										window._service_open_update_detail_dialog(frm);
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

window._service_open_update_detail_dialog = function (frm) {
	if (!frm.doc.customer) {
		frappe.msgprint("Customer not linked.");
		return;
	}

	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_lead_detail_field_values",
		args: { customer_name: frm.doc.customer },
		callback: function (r) {
			const current_values = r.message || {};

			frappe.call({
				method: "verp_staffing.crm.api.permission_request.get_department_updatable_fields",
				args: { doctype: frm.doc.service || frm.doctype },
				callback: function (fields_res) {
					const dept_fields = fields_res.message || {
						simple_fields: {},
						table_fields: {},
					};
					_open_update_detail_dialog(
						frm,
						current_values,
						dept_fields.simple_fields || {},
						dept_fields.table_fields || {},
						"service",
					);
				},
			});
		},
	});
};

window._service_show_accept_updates = function (frm) {
	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_pending_field_update_request",
		args: { customer_name: frm.doc.customer },
		callback(r) {
			frm.remove_custom_button("Accept Updates");

			if (!r.message || !r.message.has_pending) return;

			frappe.call({
				method: "verp_staffing.crm.api.permission_request.get_department_updatable_fields",
				args: { doctype: frm.doc.service || frm.doctype },
				callback: function (meta_res) {
					const field_meta = meta_res.message?.simple_fields || {};

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
							field_meta,
						);
					});
				},
			});
		},
	});
};

function _open_update_detail_dialog(frm, current_values, fields, table_fields, mode) {
	const customer_name = mode === "service" ? frm.doc.customer : frm.doc.name;
	const api_method =
		mode === "service"
			? "verp_staffing.crm.api.permission_request.request_field_update"
			: "verp_staffing.crm.api.permission_request.request_field_update_by_owner";

	const get_label = (fieldname) => {
		const fm = fields[fieldname];
		if (!fm) return fieldname.replace(/_/g, " ");
		return typeof fm === "string" ? fm : fm.label || fieldname.replace(/_/g, " ");
	};

	const table_fields_html = Object.entries(table_fields || {})
		.map(([fieldname, config]) => {
			const old_rows = current_values[fieldname] || [];

			const tbody_html = old_rows.length
				? old_rows
						.map(
							(row, idx) => `
                <tr data-row-idx="${idx}">
                    ${Object.entries(config.columns)
						.map(
							([col, col_label]) => `
                        <td style="padding:4px 6px;">
                            <input type="text" class="fg-table-cell"
                                data-fieldname="${fieldname}" data-col="${col}"
                                value="${frappe.utils.escape_html(row[col] != null ? String(row[col]) : "")}"
                                placeholder="${col_label}"
                                style="width:100%; border:0.5px solid var(--color-border-secondary);
                                    border-radius:4px; padding:5px 7px; font-size:12px;
                                    background:var(--color-background-primary);
                                    color:var(--color-text-primary); box-sizing:border-box;" />
                        </td>
                    `,
						)
						.join("")}
                    <td style="padding:4px; text-align:center; width:28px;">
                        <button class="fg-table-del-row"
                            style="border:none; background:transparent;
                                color:#E24B4A; cursor:pointer; font-size:15px; line-height:1;">✕</button>
                    </td>
                </tr>
            `,
						)
						.join("")
				: `<tr class="fg-empty-row">
                <td colspan="${Object.keys(config.columns).length + 1}"
                    style="padding:12px; text-align:center; color:var(--color-text-tertiary); font-size:13px;">
                    No rows
                </td>
            </tr>`;

			return `
            <div style="margin-top:8px;">
                <div class="fg-row fg-table-toggle" data-fieldname="${fieldname}">
                    <div class="fg-cb"><div class="fg-tick"></div></div>
                    <span class="fg-label">${frappe.utils.escape_html(config.label)}</span>
                </div>
                <div class="fg-table-editor" data-fieldname="${fieldname}"
                    style="display:none; margin-top:8px;
                        border:0.5px solid var(--color-border-tertiary);
                        border-radius:var(--border-radius-md); overflow:hidden;">
                    <table style="width:100%; border-collapse:collapse;">
                        <thead>
                            <tr style="background:var(--color-background-secondary);">
                                ${Object.values(config.columns)
									.map(
										(col_label) => `
                                    <th style="padding:7px 8px; font-size:11px; font-weight:500;
                                        color:var(--color-text-secondary); text-align:left;
                                        text-transform:uppercase; letter-spacing:0.4px;
                                        border-bottom:0.5px solid var(--color-border-tertiary);">
                                        ${col_label}
                                    </th>
                                `,
									)
									.join("")}
                                <th style="width:28px; border-bottom:0.5px solid var(--color-border-tertiary);"></th>
                            </tr>
                        </thead>
                        <tbody class="fg-table-body" data-fieldname="${fieldname}">
                            ${tbody_html}
                        </tbody>
                    </table>
                    <div style="padding:8px 10px; border-top:0.5px solid var(--color-border-tertiary);">
                        <button class="fg-table-add-row" data-fieldname="${fieldname}"
                            style="font-size:12px; padding:4px 10px;
                                border:0.5px solid var(--color-border-secondary);
                                border-radius:var(--border-radius-md); background:transparent;
                                color:var(--color-text-secondary); cursor:pointer;">
                            + Add Row
                        </button>
                    </div>
                </div>
            </div>
        `;
		})
		.join("");

	const dialog_html = `
        <style>
            .fg-row { display:flex; align-items:center; gap:10px; padding:10px 12px;
                border:0.5px solid var(--color-border-tertiary); border-radius:var(--border-radius-md);
                cursor:pointer; background:var(--color-background-primary); user-select:none; }
            .fg-row:hover { background:var(--color-background-secondary); }
            .fg-row.selected { border-color:#260fea; background:#EEEDFE; }
            .fg-cb { width:16px; height:16px; border-radius:4px;
                border:1.5px solid var(--color-border-secondary); flex-shrink:0;
                display:flex; align-items:center; justify-content:center; }
            .fg-row.selected .fg-cb { background:#260fea; border-color:#260fea; }
            .fg-tick { display:none; width:8px; height:5px;
                border-left:2px solid white; border-bottom:2px solid white;
                transform:rotate(-45deg) translate(1px,-1px); }
            .fg-row.selected .fg-tick { display:block; }
            .fg-label { font-size:13px; font-weight:500; color:var(--color-text-primary); }
            .fg-row.selected .fg-label { color:#3C3489; }
            .fg-input-block { margin-bottom:14px; }
            .fg-input-block:last-child { margin-bottom:0; }
            .fg-input-field-name { font-size:12px; font-weight:500;
                color:var(--color-text-secondary); margin-bottom:8px; }
            .fg-input-cols { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
            .fg-col-label { font-size:11px; color:var(--color-text-tertiary); margin-bottom:4px;
                text-transform:uppercase; letter-spacing:0.4px; font-weight:500; }
            .fg-current-val { padding:8px 10px; background:var(--color-background-secondary);
                border:0.5px solid var(--color-border-tertiary); border-radius:var(--border-radius-md);
                font-size:13px; color:var(--color-text-secondary); min-height:36px; word-break:break-word; }
            .fg-new-input { width:100%; padding:8px 10px;
                border:0.5px solid var(--color-border-secondary); border-radius:var(--border-radius-md);
                font-size:13px; background:var(--color-background-primary);
                color:var(--color-text-primary); box-sizing:border-box; }
            .fg-new-input:focus { outline:none; border-color:#260fea;
                box-shadow:0 0 0 2px rgba(38,15,234,0.12); }
            .fg-divider { border:none; border-top:0.5px solid var(--color-border-tertiary); margin:16px 0; }
        </style>

        <p style="font-size:11px; font-weight:500; color:var(--color-text-tertiary);
            text-transform:uppercase; letter-spacing:0.6px; margin:0 0 12px;">
            ${__("Select fields to update")}
        </p>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;" id="fg-grid">
            ${Object.entries(fields)
				.map(([fieldname, field_meta]) => {
					const label =
						typeof field_meta === "string"
							? field_meta
							: field_meta?.label || fieldname.replace(/_/g, " ");
					const old_val =
						current_values[fieldname] != null ? String(current_values[fieldname]) : "";
					return `
                    <div class="fg-row"
                        data-fieldname="${fieldname}"
                        data-label="${frappe.utils.escape_html(label)}"
                        data-current="${frappe.utils.escape_html(old_val)}">
                        <div class="fg-cb"><div class="fg-tick"></div></div>
                        <span class="fg-label">${frappe.utils.escape_html(label)}</span>
                    </div>
                `;
				})
				.join("")}
        </div>

        ${table_fields_html}

        <div id="fg-inputs-section" style="display:none;">
            <hr class="fg-divider" />
            <div id="fg-inputs-container"></div>
        </div>
    `;

	const dialog = new frappe.ui.Dialog({
		title: __("Update Detail"),
		fields: [
			{ fieldname: "fields_html", fieldtype: "HTML", options: dialog_html },
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

			dialog.$wrapper.find("#fg-grid .fg-row.selected").each(function () {
				const fieldname = $(this).data("fieldname");
				const label = get_label(fieldname);
				const input = dialog.$wrapper.find(
					`#fg-inputs-container .fg-new-input[data-fieldname="${fieldname}"]`,
				);
				let new_val = "";

				if (input.hasClass("fg-file-url")) {
					new_val = input.val();

					if (!new_val) {
						frappe.msgprint(__("Please upload a file."));
						missing_value = true;
						return false;
					}
				} else if (input.attr("type") === "checkbox") {
					new_val = input.is(":checked") ? 1 : 0;
				} else {
					new_val = input.val().trim();
				}
				const old_val = input.data("old") || "";

				if (!new_val) {
					frappe.msgprint(__(`Please enter a new value for "${label}".`));
					missing_value = true;
					return false;
				}

				field_updates[fieldname] = { old: old_val, new: new_val };
				has_selection = true;
			});

			if (missing_value) return;

			dialog.$wrapper.find(".fg-table-toggle.selected").each(function () {
				const fieldname = $(this).data("fieldname");
				const config = table_fields[fieldname];
				const old_rows = current_values[fieldname] || [];
				const new_rows = [];

				dialog.$wrapper
					.find(`.fg-table-body[data-fieldname="${fieldname}"] tr:not(.fg-empty-row)`)
					.each(function () {
						const row = {};
						let has_value = false;
						Object.keys(config.columns).forEach((col) => {
							const val =
								$(this).find(`.fg-table-cell[data-col="${col}"]`).val() || "";
							row[col] = val;
							if (val) has_value = true;
						});
						if (has_value) new_rows.push(row);
					});

				field_updates[fieldname] = { old: old_rows, new: new_rows };
				has_selection = true;
			});

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
					// ── Pass service doctype and name for activity log ──
					service_doctype: mode === "service" ? frm.doctype : null,
					service_name: mode === "service" ? frm.doc.name : null,
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

	dialog.$wrapper.on("change", ".fg-file-input", function () {
		const file = this.files[0];
		const fieldname = $(this).data("fieldname");

		if (!file) return;

		const formData = new FormData();
		formData.append("file", file);
		formData.append("is_private", 0);

		$.ajax({
			url: "/api/method/upload_file",
			type: "POST",
			data: formData,
			processData: false,
			contentType: false,
			headers: {
				"X-Frappe-CSRF-Token": frappe.csrf_token,
			},
			success: function (r) {
				if (r.message) {
					const file_id = r.message.name; // ✅ FILE ID
					const file_url = r.message.file_url; // ✅ URL

					// store ID
					dialog.$wrapper
						.find(`.fg-file-url[data-fieldname="${fieldname}"]`)
						.val(file_id);

					// store URL separately
					dialog.$wrapper
						.find(`.fg-file-url[data-fieldname="${fieldname}"]`)
						.attr("data-file-url", file_url);

					// show ID in UI
					dialog.$wrapper
						.find(`.fg-file-name[data-fieldname="${fieldname}"]`)
						.html(`<span style="color:#260fea;">${file_id}</span>`);
				}
			},
		});
	});

	// Simple field row click
	dialog.$wrapper.on("click", "#fg-grid .fg-row", function () {
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

	// Table field toggle
	dialog.$wrapper.on("click", ".fg-table-toggle", function () {
		const fieldname = $(this).data("fieldname");
		$(this).toggleClass("selected");
		dialog.$wrapper
			.find(`.fg-table-editor[data-fieldname="${fieldname}"]`)
			.toggle($(this).hasClass("selected"));
	});

	// Add row
	dialog.$wrapper.on("click", ".fg-table-add-row", function () {
		const fieldname = $(this).data("fieldname");
		const config = table_fields[fieldname];
		const tbody = dialog.$wrapper.find(`.fg-table-body[data-fieldname="${fieldname}"]`);
		tbody.find(".fg-empty-row").remove();
		tbody.append(`
            <tr>
                ${Object.entries(config.columns)
					.map(
						([col, col_label]) => `
                    <td style="padding:4px 6px;">
                        <input type="text" class="fg-table-cell"
                            data-fieldname="${fieldname}" data-col="${col}"
                            placeholder="${col_label}"
                            style="width:100%; border:0.5px solid var(--color-border-secondary);
                                border-radius:4px; padding:5px 7px; font-size:12px;
                                background:var(--color-background-primary);
                                color:var(--color-text-primary); box-sizing:border-box;" />
                    </td>
                `,
					)
					.join("")}
                <td style="padding:4px; text-align:center; width:28px;">
                    <button class="fg-table-del-row"
                        style="border:none; background:transparent;
                            color:#E24B4A; cursor:pointer; font-size:15px; line-height:1;">✕</button>
                </td>
            </tr>
        `);
	});

	// Delete row
	dialog.$wrapper.on("click", ".fg-table-del-row", function () {
		$(this).closest("tr").remove();
	});
}

function _open_accept_updates_dialog(frm, pending_requests, mode, field_meta = {}) {
	const customer_name = mode === "service" ? frm.doc.customer : frm.doc.name;
	let all_html = "";

	function render_value(val, fieldname) {
		if (val === null || val === undefined || val === "") {
			return `<span style="font-style:italic; color:var(--color-text-tertiary);">empty</span>`;
		}

		if (typeof val === "object" && val.name) {
			val = val.name;
		}

		val = String(val).trim();
		const meta = field_meta[fieldname] || {};
		const fieldtype = meta.fieldtype;

		if (fieldtype === "Link") {
			return `<a href="/app/file/${encodeURIComponent(val)}" target="_blank"
				style="color:#260fea; font-weight:500;">📎 ${frappe.utils.escape_html(val)}</a>`;
		}

		return frappe.utils.escape_html(val);
	}

	function render_table(data, is_new) {
		if (!data || !data.length) {
			return `<div style="padding:8px; color:var(--color-text-tertiary); font-size:12px;">No rows</div>`;
		}

		const columns = Object.keys(data[0]).filter(
			(k) =>
				![
					"name",
					"idx",
					"parent",
					"parenttype",
					"parentfield",
					"owner",
					"modified_by",
					"creation",
					"modified",
					"docstatus",
				].includes(k),
		);

		return `
			<table style="width:100%; border-collapse:collapse; font-size:12px;">
				<thead>
					<tr style="background:var(--color-background-secondary);">
						${columns
							.map(
								(col) => `
							<th style="padding:6px 8px; text-align:left;
								border-bottom:0.5px solid var(--color-border-tertiary);
								color:var(--color-text-secondary);">
								${col.replace(/_/g, " ").toUpperCase()}
							</th>
						`,
							)
							.join("")}
					</tr>
				</thead>
				<tbody>
					${data
						.map(
							(row) => `
						<tr>
							${columns
								.map(
									(col) => `
								<td style="padding:6px 8px;
									border-bottom:0.5px solid var(--color-border-tertiary);
									color:${is_new ? "#3C3489" : "var(--color-text-secondary)"};">
									${frappe.utils.escape_html(row[col] || "")}
								</td>
							`,
								)
								.join("")}
						</tr>
					`,
						)
						.join("")}
				</tbody>
			</table>
		`;
	}

	const dialog_html = `
	<style>
		.au-row {
			display:flex;
			gap:10px;
			padding:10px 12px;
			border:0.5px solid var(--color-border-tertiary);
			border-radius:var(--border-radius-md);
			background:var(--color-background-primary);
			margin-bottom:10px;
		}
		.au-cb {
			width:16px; height:16px;
			border-radius:4px;
			border:1.5px solid #260fea;
			background:#260fea;
			display:flex;
			align-items:center;
			justify-content:center;
			cursor:pointer;
			margin-top:3px;
		}
		.au-tick {
			width:8px; height:5px;
			border-left:2px solid white;
			border-bottom:2px solid white;
			transform:rotate(-45deg) translate(1px,-1px);
		}
		.au-label {
			font-size:13px;
			font-weight:500;
			margin-bottom:6px;
		}

		/* ✅ FIX ADDED HERE */
		.au-cols {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 10px;
		}

		.au-box {
			padding:8px 10px;
			border-radius:var(--border-radius-md);
			font-size:13px;
		}
		.au-old {
			background:var(--color-background-secondary);
			border:0.5px solid var(--color-border-tertiary);
			color:var(--color-text-secondary);
		}
		.au-new {
			background:#EEEDFE;
			border:0.5px solid #260fea;
			color:#3C3489;
			font-weight:500;
		}
		.au-header {
			font-size:11px;
			color:var(--color-text-tertiary);
			margin-bottom:4px;
			text-transform:uppercase;
		}
	</style>
	`;

	pending_requests.forEach((req, idx) => {
		all_html += `
			<div style="margin-bottom:20px;">
				<div style="font-size:13px; font-weight:500;">
					Request ${idx + 1} — <b>${req.requested_by}</b>
				</div>
				<div style="font-size:12px; color:var(--color-text-secondary); margin-bottom:10px;">
					Reason: ${req.reason}
				</div>
		`;

		Object.entries(req.field_updates).forEach(([fieldname, values]) => {
			const label = fieldname.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
			const is_table = Array.isArray(values.old) || Array.isArray(values.new);

			// TABLE → UP/DOWN
			if (is_table) {
				all_html += `
					<div class="au-row">
						<div class="au-cb" data-fieldname="${fieldname}" data-comment="${req.comment_name}">
							<div class="au-tick"></div>
						</div>

						<input type="checkbox" class="approve-field-checkbox"
							data-fieldname="${fieldname}" data-comment="${req.comment_name}"
							checked style="display:none;" />

						<div style="flex:1;">
							<div class="au-label">${label}</div>

							<div style="margin-top:8px;">
								<div class="au-header">Current</div>
								<div class="au-box au-old">
									${render_table(values.old, false)}
								</div>
							</div>

							<div style="margin-top:10px;">
								<div class="au-header">New</div>
								<div class="au-box au-new">
									${render_table(values.new, true)}
								</div>
							</div>
						</div>
					</div>
				`;
				return;
			}

			// NORMAL → LEFT/RIGHT
			all_html += `
				<div class="au-row">
					<div class="au-cb" data-fieldname="${fieldname}" data-comment="${req.comment_name}">
						<div class="au-tick"></div>
					</div>

					<input type="checkbox" class="approve-field-checkbox"
						data-fieldname="${fieldname}" data-comment="${req.comment_name}"
						checked style="display:none;" />

					<div style="flex:1;">
						<div class="au-label">${label}</div>

						<div class="au-cols">
							<div>
								<div class="au-header">Current</div>
								<div class="au-box au-old">
									${render_value(values.old, fieldname)}
								</div>
							</div>
							<div>
								<div class="au-header">New</div>
								<div class="au-box au-new">
									${render_value(values.new, fieldname)}
								</div>
							</div>
						</div>
					</div>
				</div>
			`;
		});

		all_html += `</div>`;
	});

	const d = new frappe.ui.Dialog({
		title: __("Accept Updates"),
		fields: [{ fieldname: "html", fieldtype: "HTML", options: dialog_html + all_html }],
		primary_action_label: __("Accept Selected"),
		primary_action() {
			const by_comment = {};

			d.$wrapper.find(".approve-field-checkbox:checked").each(function () {
				const f = $(this).data("fieldname");
				const c = $(this).data("comment");

				if (!by_comment[c]) by_comment[c] = [];
				by_comment[c].push(f);
			});

			if (!Object.keys(by_comment).length) {
				frappe.msgprint("Select at least one field");
				return;
			}

			d.hide();

			Promise.all(
				Object.entries(by_comment).map(([comment_name, fields]) =>
					frappe.call({
						method: "verp_staffing.crm.api.permission_request.apply_field_updates",
						args: {
							customer_name,
							comment_name,
							approved_fields: JSON.stringify(fields),
						},
					}),
				),
			).then(() => {
				frappe.show_alert("Updated successfully");
				frm.reload_doc();
			});
		},

		secondary_action_label: __("Reject All"),
		secondary_action() {
			frappe.confirm("Reject all updates?", () => {
				Promise.all(
					pending_requests.map((req) =>
						frappe.call({
							method: "verp_staffing.crm.api.permission_request.reject_field_update_request",
							args: {
								customer_name,
								comment_name: req.comment_name,
							},
						}),
					),
				).then(() => {
					frappe.show_alert({ message: "All updates rejected", indicator: "red" });
					d.hide();
					frm.reload_doc();
				});
			});
		},
	});

	d.show();

	d.$wrapper.on("click", ".au-cb", function () {
		const fieldname = $(this).data("fieldname");
		const comment = $(this).data("comment");

		const cb = d.$wrapper.find(
			`.approve-field-checkbox[data-fieldname="${fieldname}"][data-comment="${comment}"]`,
		);

		const checked = cb.prop("checked");
		cb.prop("checked", !checked);

		$(this).css({ background: checked ? "#fff" : "#260fea" });
		$(this).find(".au-tick").toggle(!checked);
	});
}

function _fg_rebuild(dialog, fields, current_values, saved) {
	dialog.$wrapper.find(".fg-new-input").each(function () {
		const fieldname = $(this).data("fieldname");

		if ($(this).hasClass("fg-file-url")) {
			saved[fieldname] = $(this).val();
		} else if ($(this).attr("type") === "checkbox") {
			saved[fieldname] = $(this).is(":checked") ? 1 : 0;
		} else {
			saved[fieldname] = $(this).val();
		}
	});

	const selected = dialog.$wrapper.find("#fg-grid .fg-row.selected");
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
		const field_meta = fields[fieldname];

		const fieldtype = field_meta?.fieldtype || "Data";
		const label = field_meta?.label || fieldname.replace(/_/g, " ");
		const options = field_meta?.options || "";

		const old_val = current_values[fieldname] != null ? String(current_values[fieldname]) : "";
		const saved_val = saved[fieldname] != null ? String(saved[fieldname]) : "";

		let input_html = "";

		// ✅ SELECT
		if (fieldtype === "Select") {
			const opts = options.split("\n").filter((o) => o);

			input_html = `
				<select class="fg-new-input"
					data-fieldname="${fieldname}"
					data-old="${frappe.utils.escape_html(old_val)}">
					<option value="">Select ${label}</option>
					${opts
						.map(
							(opt) => `
						<option value="${frappe.utils.escape_html(opt)}"
							${saved_val === opt ? "selected" : ""}>
							${frappe.utils.escape_html(opt)}
						</option>
					`,
						)
						.join("")}
				</select>
			`;
		}

		// ✅ CHECKBOX
		else if (fieldtype === "Check") {
			input_html = `
				<input type="checkbox"
					class="fg-new-input"
					data-fieldname="${fieldname}"
					data-old="${old_val}"
					${saved_val == "1" || saved_val == 1 ? "checked" : ""} />
			`;
		} else if (fieldtype === "Link") {
			const link_options = options || "";

			let current_display_html;
			if (old_val && link_options === "File") {
				current_display_html = `
            <a href="/app/file/${encodeURIComponent(old_val)}" target="_blank"
                style="color:#260fea; font-weight:500; text-decoration:none; font-size:13px;">
                ${frappe.utils.escape_html(old_val)}
            </a>
        `;
			} else if (old_val) {
				current_display_html = frappe.utils.escape_html(old_val);
			} else {
				current_display_html = `<span style="color:var(--color-text-tertiary);font-style:italic;">empty</span>`;
			}

			container.append(`
        <div class="fg-input-block">
            <div class="fg-input-field-name">${frappe.utils.escape_html(label)}</div>
            <div class="fg-input-cols">
                <div>
                    <div class="fg-col-label">${__("Current")}</div>
                    <div class="fg-current-val">${current_display_html}</div>
                </div>
                <div>
                    <div class="fg-col-label">${__("New")}</div>
                    <div style="display:flex; flex-direction:column; gap:6px;">
                        <input type="file" class="fg-file-input"
                            data-fieldname="${fieldname}"
                            style="font-size:12px;" />
                        <div class="fg-file-name" data-fieldname="${fieldname}"
                            style="font-size:11px; color:var(--color-text-secondary);">
                            ${saved_val ? `<span style="color:#260fea;">${frappe.utils.escape_html(saved_val)}</span>` : ""}
                        </div>
                        <input type="hidden"
                            class="fg-new-input fg-file-url"
                            data-fieldname="${fieldname}"
                            data-old="${frappe.utils.escape_html(old_val)}"
                            value="${frappe.utils.escape_html(saved_val)}" />
                    </div>
                </div>
            </div>
        </div>
    `);
			return;
		} else {
			input_html = `
				<input class="fg-new-input" type="text"
					data-fieldname="${fieldname}"
					data-old="${frappe.utils.escape_html(old_val)}"
					value="${frappe.utils.escape_html(saved_val)}"
					placeholder="${__("Enter new value for")} ${frappe.utils.escape_html(label)}" />
			`;
		}

		container.append(`
			<div class="fg-input-block">
				<div class="fg-input-field-name">${frappe.utils.escape_html(label)}</div>
				<div class="fg-input-cols">
					<div>
						<div class="fg-col-label">${__("Current")}</div>
						<div class="fg-current-val">
							${
								old_val
									? frappe.utils.escape_html(old_val)
									: `<span style="color:var(--color-text-tertiary);font-style:italic;">empty</span>`
							}
						</div>
					</div>
					<div>
						<div class="fg-col-label">${__("New")}</div>
						${input_html}
					</div>
				</div>
			</div>
		`);
	});
}
