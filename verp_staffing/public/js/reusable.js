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
		method: "verp_staffing.quota.utils.customer_data.get_data_by_customer",
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
						let current_display_html = value
							? `<a href="https://${value}" target="_blank"
        style="color:#260fea;font-weight:500;text-decoration:none;">${f.fieldname == "personal_linkedin" ? value : "📎 View Current File"}</a>`
							: `<span style="color:var(--color-text-tertiary);font-style:italic;">No file</span>`;

						let display_value = value;

						if (f.fieldname === "email") {
							display_value = `
                <a href="#"
                  class="open-email-composer"
                  data-email="${frappe.utils.escape_html(value)}"
                  style="color:#2563eb;font-weight:500;text-decoration:none;">
                  ${frappe.utils.escape_html(value)}
                </a>
              `;
						} else if (f.fieldtype == "Link" || f.fieldname == "personal_linkedin") {
							display_value = current_display_html;
						}

						html += `
              <div class="field-row">
                <div class="field-label">${frappe.utils.escape_html(f.label)}</div>
                <div class="field-value">${display_value}</div>
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

			const $wrapper = frm.fields_dict[html_field].$wrapper;

			// Prevent duplicate handlers on refresh
			$wrapper.off("click", ".open-email-composer");

			$wrapper.on("click", ".open-email-composer", function (e) {
				e.preventDefault();

				const email = $(this).data("email");

				new frappe.views.CommunicationComposer({
					doc: frm.doc,
					recipients: email,
				});
			});
		},
	});
};

window.get_display_fields = async function (doctype) {
	try {
		const res = await frappe.db.get_single_value(
			"ERP Configuration",
			"department_display_form_fields",
		);
		const CONFIG = res ? JSON.parse(res) : {};

		const key = Object.keys(CONFIG).find((k) => k.toLowerCase() === doctype.toLowerCase());

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
				const response = r.message;

				// Handle new shaped response {blocked, options} and legacy plain array
				const isNewShape =
					response && typeof response === "object" && !Array.isArray(response);
				// --- Blocked: customer already active in CR or Onboarding ---
				if (isNewShape && response.blocked) {
					const depts = response.active_in.join(" and ");
					frappe.msgprint({
						title: "Forwarding Not Allowed",
						indicator: "red",
						message: `This customer is currently active in <b>${depts}</b>. 
                                  No further forwarding is allowed.`,
					});
					return;
				}
				// Normalize services list from either shape
				let services = isNewShape ? response.options || [] : response || [];
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
					d.set_value("assign_employee", null);
					toggle_fields(d, frm);
				},
			},
			{
				fieldname: "interview",
				fieldtype: "Select",
				label: "Select Interview",
				hidden: 1,
				options: [],
			},
			{
				fieldname: "note",
				fieldtype: "Text Editor",
				label: "Note (Optional)",
				hidden: 1,
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
					const selected_service = d.get_value("service");

					return {
						filters: [
							["Employee Assignment Detail", "department", "=", selected_service],
						],
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

			attach_edit_delete_events_for_note(frm, $notes_wrapper);
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

function attach_edit_delete_events_for_note(frm, $wrapper) {
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
					refresh_notes(frm, $wrapper);
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
			attach_edit_delete_events_for_note(frm, $wrapper);
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
			tasks.sort((a, b) => a.is_completed - b.is_completed);
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
			attach_edit_delete_events_for_task_and_event(frm, $wrapper);
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
    <div class="task-card list-group-item" data-id="${t.name}" style="padding:10px; border:1px solid #ccc; border-radius:6px; margin-bottom:8px; display:flex; align-items:center; gap:10px; ${
		t.is_completed ? "opacity:0.5; filter: grayscale(0.3);" : ""
	}">
        <input type="checkbox" ${t.is_completed ? "checked" : ""} class="task-complete" data-id="${t.name}" />

        <div style="flex:1">
            <b>${t.description}</b><br>
            <small>Due: ${t.date || "No date"} | Assigned: ${t.assigned_to || "N/A"}</small>
        </div>
        <button class="btn btn-xs btn-secondary edit-task-btn" 
			${t.is_completed ? "disabled" : ""}>
			Edit
		</button>

		<button class="btn btn-xs btn-secondary delete-task-btn text-danger" 
			${t.is_completed ? "disabled" : ""}>
			Delete
		</button>
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
				frappe.db
					.set_value("CRM Task", task_name, {
						description: values.description,
						date: values.date,
						assigned_to: values.assigned_to,
						is_completed: values.is_completed ? 1 : 0,
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
				onchange: function () {
					let value = d.get_value("category");

					if (value === "Other") {
						d.set_df_property("custom_title", "hidden", 0);
						d.set_df_property("custom_title", "reqd", 1);
					} else {
						d.set_df_property("custom_title", "hidden", 1);
						d.set_df_property("custom_title", "reqd", 0);
					}
				},
			},
			{
				label: "Title (Enter Name of Event)",
				fieldname: "custom_title",
				fieldtype: "Data",
				hidden: 1,
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
					onchange: function () {
						let value = d.get_value("category");

						if (value === "Other") {
							d.set_df_property("custom_title", "hidden", 0);
							d.set_df_property("custom_title", "reqd", 1);
						} else {
							d.set_df_property("custom_title", "hidden", 1);
							d.set_df_property("custom_title", "reqd", 0);
						}
					},
				},
				{
					label: "Title (Enter Name of Event)",
					fieldname: "custom_title",
					fieldtype: "Data",
					hidden: 1,
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

function attach_edit_delete_events_for_task_and_event(frm, $wrapper) {
	$wrapper.find(".edit-task-btn").on("click", function () {
		let task_id = $(this).closest(".task-card").data("id");
		open_edit_task_dialog(task_id, frm);
	});

	$wrapper.find(".delete-task-btn").on("click", function () {
		let task_id = $(this).closest(".task-card").data("id");

		frappe.call({
			method: "verp_staffing.crm.api.activities.delete_activity",
			args: { doctype: "CRM Task", name: task_id },
			callback() {
				frappe.show_alert("Task deleted");
				render_activity_section(frm);
			},
		});
	});

	$wrapper.find(".edit-event-btn").on("click", function () {
		let event_id = $(this).closest(".event-card").data("id");
		open_edit_event_dialog(event_id, frm);
	});

	$wrapper.find(".delete-event-btn").on("click", function () {
		let event_id = $(this).closest(".event-card").data("id");

		frappe.call({
			method: "verp_staffing.crm.api.activities.delete_activity",
			args: { doctype: "CRM Event", name: event_id },
			callback() {
				frappe.show_alert("Event deleted");
				render_activity_section(frm);
			},
		});
	});
}

// Show lates uploaded resume

window.fetch_and_render_resume = function fetch_and_render_resume(frm) {
	if (!frm.doc.customer) {
		frm.set_df_property(
			"resume",
			"options",
			'<div style="color:#888">No customer selected</div>',
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
					'<div style="color:#888">No resume uploaded</div>',
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
