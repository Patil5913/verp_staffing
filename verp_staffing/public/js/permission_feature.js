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