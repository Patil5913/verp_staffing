window._ftbl_state = window._ftbl_state || {};
window._ftbl_active_dialog = null;
window._perm_ftbl_state = window._perm_ftbl_state || {};
window._perm_active_dialog = null;

window.__perm_close_dialog_ = function () {
	const ad = window._perm_active_dialog;
	if (!ad) return;
	_collectValues(ad.dialog, ad.tableId, ad.rowIdx, ad.columns, ad.uid);
	ad.dialog.$wrapper.off("hide.bs.modal");
	ad.dialog.hide();
	window.rebuildFtblBody(ad.tableId);
	window._perm_active_dialog = null;
};

window.__perm_dlg_delete_ = function (tableId, rowIdx) {
	const ad = window._perm_active_dialog;
	if (ad) {
		ad.dialog.$wrapper.off("hide.bs.modal");
		ad.dialog.hide();
		window._perm_active_dialog = null;
	}
	const state = window._perm_ftbl_state[tableId];
	if (!state) return;
	state.rows.splice(rowIdx, 1);
	window.rebuildFtblBody(tableId);
};

window.__perm_dlg_insert_ = function (tableId, rowIdx, where) {
	const ad = window._perm_active_dialog;
	if (ad) {
		_collectValues(ad.dialog, tableId, ad.rowIdx, ad.columns, ad.uid);
		ad.dialog.$wrapper.off("hide.bs.modal");
		ad.dialog.hide();
		window._perm_active_dialog = null;
	}
	const state = window._perm_ftbl_state[tableId];
	if (!state) return;
	const newRow = {};
	const insertAt = where === "above" ? rowIdx : rowIdx + 1;
	state.rows.splice(insertAt, 0, newRow);
	window.rebuildFtblBody(tableId);
	window.openRowDialog(tableId, insertAt);
};

window.__perm_dlg_duplicate_ = function (tableId, rowIdx) {
	const ad = window._perm_active_dialog;
	if (ad) {
		_collectValues(ad.dialog, tableId, ad.rowIdx, ad.columns, ad.uid);
		ad.dialog.$wrapper.off("hide.bs.modal");
		ad.dialog.hide();
		window._perm_active_dialog = null;
	}
	const state = window._perm_ftbl_state[tableId];
	if (!state) return;
	const copy = { ...state.rows[rowIdx] };
	delete copy.name;
	state.rows.splice(rowIdx + 1, 0, copy);
	window.rebuildFtblBody(tableId);
	window.openRowDialog(tableId, rowIdx + 1);
};

window.__perm_open_row_ = function (tableId, rowIdx) {
	window.openRowDialog(tableId, rowIdx);
};

window.__perm_addrow_ = function (tableId) {
	const state = window._perm_ftbl_state[tableId];
	if (!state) {
		console.error("STATE NOT FOUND", tableId);
		return;
	}
	state.rows.push({});
	window.rebuildFtblBody(tableId);
	window.openRowDialog(tableId, state.rows.length - 1);
};

window.__perm_toggleall_ = function (tableId, el) {
	document
		.querySelectorAll(`.ftbl-chk[data-tableid="${tableId}"]`)
		.forEach((chk) => (chk.checked = el.checked));
	window._ftbl_rowCheckChange(tableId);
};

window.__perm_chkchg_ = function (tableId) {
	window._ftbl_rowCheckChange(tableId);
};

window.__perm_delsel_ = function (tableId) {
	const toDelete = [
		...document.querySelectorAll(`.ftbl-chk[data-tableid="${tableId}"]:checked`),
	].map((el) => el.dataset.rowid);
	const state = window._perm_ftbl_state[tableId];
	if (!state) return;
	state.rows = state.rows.filter((r, i) => !toDelete.includes(r.name || `new-${tableId}-${i}`));
	window.rebuildFtblBody(tableId);
};

// ─── field-name classifiers ──────────────────────────────────────────────────
window._ftbl_EMAIL_FIELDS = new Set(["email", "email_id", "email_address"]);
window._ftbl_MONTH_YEAR_FIELDS = new Set(["start_date", "end_date", "entry_date"]);
window._ftbl_PHONE_FIELDS = new Set([
	"phone_number",
	"phone",
	"mobile",
	"mobile_no",
	"personal_phone_number",
]);
window._ftbl_isEmail = (f) => window._ftbl_EMAIL_FIELDS.has(f.toLowerCase());
window._ftbl_isPhone = (f) => window._ftbl_PHONE_FIELDS.has(f.toLowerCase());
window._ftbl_isMonthYear = (f) => window._ftbl_MONTH_YEAR_FIELDS.has(f.toLowerCase());

window._ftbl_toMonthYear = function (v) {
	if (!v) return "";
	const p = v.split("-");
	return p.length >= 2 ? `${p[1]}-${p[0]}` : v;
};
window._ftbl_fromMonthYear = function (v) {
	if (!v) return "";
	const m = v.match(/^(\d{2})-(\d{4})$/);
	return m ? `${m[2]}-${m[1]}-01` : v;
};
window._ftbl_isValidMY = function (v) {
	const m = v.match(/^(\d{2})-(\d{4})$/);
	if (!m) return false;
	const mo = parseInt(m[1], 10),
		yr = parseInt(m[2], 10);
	return mo >= 1 && mo <= 12 && yr >= 1900 && yr <= 2100;
};

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
											const d = JSON.parse(c.content);
											if (
												d.type === "field_update_request" &&
												d.status === "Pending" &&
												d.requested_by_employee === employee
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
									frm.add_custom_button(__("Update Detail"), () =>
										window._service_open_update_detail_dialog(frm),
									);
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
					const dept = fields_res.message || { simple_fields: {}, table_fields: {} };
					_open_update_detail_dialog(
						frm,
						current_values,
						dept.simple_fields || {},
						dept.table_fields || {},
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

// ─── _open_update_detail_dialog ───────────────────────────────────────────────
function _open_update_detail_dialog(frm, current_values, fields, table_fields, mode) {
	const customer_name = mode === "service" ? frm.doc.customer : frm.doc.name;
	const api_method =
		mode === "service"
			? "verp_staffing.crm.api.permission_request.request_field_update"
			: "verp_staffing.crm.api.permission_request.request_field_update_by_owner";

	const get_label = (fn) => {
		const fm = fields[fn];
		if (!fm) return fn.replace(/_/g, " ");
		return typeof fm === "string" ? fm : fm.label || fn.replace(/_/g, " ");
	};

	// ── field-name classifiers ────────────────────────────────────────────────
	const EMAIL_FIELDS = new Set(["email", "email_id", "email_address"]);
	const MONTH_YEAR_FIELDS = new Set(["start_date", "end_date", "entry_date"]);
	const PHONE_FIELDS = new Set([
		"phone_number",
		"phone",
		"mobile",
		"mobile_no",
		"personal_phone_number",
	]);
	const isPhoneField = (f) => PHONE_FIELDS.has(f.toLowerCase());
	const isEmailField = (f) => EMAIL_FIELDS.has(f.toLowerCase());
	const isMonthYearField = (f) => MONTH_YEAR_FIELDS.has(f.toLowerCase());

	// ── date helpers ──────────────────────────────────────────────────────────
	function toMonthYear(value) {
		if (!value) return "";
		const parts = value.split("-");
		return parts.length >= 2 ? `${parts[1]}-${parts[0]}` : value;
	}
	function fromMonthYear(value) {
		if (!value) return "";
		const match = value.match(/^(\d{2})-(\d{4})$/);
		return match ? `${match[2]}-${match[1]}-01` : value;
	}
	function isValidMonthYear(value) {
		const match = value.match(/^(\d{2})-(\d{4})$/);
		if (!match) return false;
		const month = parseInt(match[1], 10);
		const year = parseInt(match[2], 10);
		return month >= 1 && month <= 12 && year >= 1900 && year <= 2100;
	}

	// ── error helpers ─────────────────────────────────────────────────────────
	function clearError(input) {
		input.style.border = "";
		const wrapper =
			input.closest(".ftbl-dialog-field") ||
			input.closest(".control-input") ||
			input.parentNode;
		const old = wrapper?.querySelector(".error-text");
		if (old) old.remove();
	}
	function markInvalid(input, message) {
		input.style.border = "1px solid #e24b4a";
		const wrapper =
			input.closest(".ftbl-dialog-field") ||
			input.closest(".control-input") ||
			input.parentNode;
		const existing = wrapper?.querySelector(".error-text");
		if (existing) existing.remove();
		const error = document.createElement("div");
		error.className = "error-text";
		error.style.cssText = "color:#e24b4a;font-size:11px;margin-top:3px;";
		error.innerText = message;
		wrapper.appendChild(error);
	}

	// ── cell display (read-only text in grid) ─────────────────────────────────
	function formatCellDisplay(col, value) {
		if (value === null || value === undefined || value === "")
			return `<span style="color:var(--color-text-tertiary,#bbb);">—</span>`;
		if (col.fieldtype === "Check") return value ? "✓" : "";
		if (isMonthYearField(col.fieldname)) return toMonthYear(String(value));
		const str = String(value);
		return frappe.utils?.escape_html ? frappe.utils.escape_html(str) : str;
	}

	// ── build one dialog field input ──────────────────────────────────────────
	function buildDialogInput(col, currentVal, uid) {
		const id = `dlg-${uid}-${col.fieldname}`;
		const val = currentVal ?? "";

		let noteHtml = col.description
			? `<div style="font-size:11px;color:var(--color-text-secondary,#888);margin-top:3px;">NOTE: ${col.description}</div>`
			: "";

		const baseStyle = `width:100%;height:32px;padding:0 10px;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.25));border-radius:6px;font-size:13px;font-family:inherit;background:var(--color-background-secondary,#F3F3F3);color:var(--color-text-primary);outline:none;`;

		let inputHtml;

		if (col.fieldtype === "Check") {
			return `<div class="ftbl-dialog-field" data-fieldname="${col.fieldname}" style="width:100%;padding:0 8px;margin-bottom:10px;">
					<label style="display:inline-flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">
						<input id="${id}" type="checkbox" ${val ? "checked" : ""} style="width:14px;height:14px;accent-color:#378add;cursor:pointer;" />
						${col.label || frappe.model.unscrub(col.fieldname)}
					</label>${noteHtml}
				</div>`;
		}

		if (isEmailField(col.fieldname)) {
			inputHtml = `<input id="${id}" type="email" value="${val}" data-override="email" style="${baseStyle}" placeholder="Exp: example@email.com" />`;
		} else if (isPhoneField(col.fieldname)) {
			inputHtml = `<input id="${id}" type="tel" value="${val}" data-override="phone" style="${baseStyle}" placeholder="+91-9876543210" />`;
		} else if (isMonthYearField(col.fieldname)) {
			inputHtml = `<input id="${id}" type="text" value="${toMonthYear(val)}" data-override="month-year" maxlength="7" style="${baseStyle}" placeholder="MM-YYYY" />`;
			noteHtml = `<div style="font-size:11px;color:var(--color-text-secondary,#888);margin-top:3px;">NOTE: Use date format: MM-YYYY</div>`;
		} else if (col.fieldtype === "Select") {
			let opts = [];

			if (col.options) {
				// ✅ Array support
				if (Array.isArray(col.options)) {
					opts = col.options;
				}
				// ✅ Newline string (Frappe standard)
				else if (typeof col.options === "string" && col.options.includes("\n")) {
					opts = col.options.split(/\r?\n/).filter((o) => o && o.trim());
				}
				// ✅ Comma separated (extra support)
				else if (typeof col.options === "string" && col.options.includes(",")) {
					opts = col.options.split(",").map((o) => o.trim());
				}
				// ❌ REMOVE this wrong logic
				else if (frappe.meta.docfield_map[col.options]) {
					opts = [];
				}

				// ✅ fallback
				else {
					opts = [col.options];
				}
			}

			inputHtml = `<select id="${id}" style="${baseStyle}">
		<option value="">Select…</option>
		${opts.map((o) => `<option value="${o}" ${o == val ? "selected" : ""}>${o}</option>`).join("")}
	</select>`;
		} else if (["Text", "Small Text", "Long Text"].includes(col.fieldtype)) {
			const minH = col.fieldname === "description" ? "150px" : "70px";
			inputHtml = `<textarea id="${id}" style="width:100%;min-height:${minH};padding:8px 10px;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.25));border-radius:6px;font-size:13px;font-family:inherit;background:var(--color-background-secondary,#F3F3F3);color:var(--color-text-primary);outline:none;resize:vertical;line-height:1.5;" placeholder="Exp: ${col.label || frappe.model.unscrub(col.fieldname)}">${val}</textarea>`;
			if (col.fieldname === "description")
				noteHtml = `<div style="font-size:11px;color:var(--color-text-secondary,#888);margin-top:3px;">NOTE: Minimum length: 800 characters (excluding spaces).</div>`;
		} else if (["Int", "Float", "Currency"].includes(col.fieldtype)) {
			inputHtml = `<input id="${id}" type="number" value="${val}" style="${baseStyle}" />`;
		} else if (col.fieldtype === "Date") {
			inputHtml = `<input id="${id}" type="date" value="${(val || "").split(" ")[0] || ""}" style="${baseStyle}" />`;
		} else {
			inputHtml = `<input id="${id}" type="text" value="${val}" style="${baseStyle}" placeholder="Exp: ${col.label || frappe.model.unscrub(col.fieldname)}" />`;
		}

		const isWide = ["Text", "Small Text", "Long Text"].includes(col.fieldtype);
		const labelHtml = `<div style="font-size:12px;font-weight:500;color:var(--color-text-secondary,#6b6b6b);margin-bottom:5px;">
				${col.label || frappe.model.unscrub(col.fieldname)}${col.reqd ? '<span style="color:#e24b4a;margin-left:2px;">*</span>' : ""}
			</div>`;

		return `<div class="ftbl-dialog-field" data-fieldname="${col.fieldname}"
				style="width:${isWide ? "100%" : "calc(50% - 8px)"};min-width:${isWide ? "100%" : "200px"};padding:0 8px;margin-bottom:10px;">
				${labelHtml}${inputHtml}${noteHtml}
			</div>`;
	}

	// ── collect values from an open dialog back into state ────────────────────
	window._collectValues = function _collectValues(dialog, tableId, rowIdx, columns, uid) {
		const state = window._perm_ftbl_state[tableId];
		if (!state || !state.rows[rowIdx]) return;
		columns.forEach((col) => {
			const el = dialog.$wrapper[0].querySelector(`#dlg-${uid}-${col.fieldname}`);
			if (!el) return;
			let val = el.type === "checkbox" ? (el.checked ? 1 : 0) : el.value;
			if (isMonthYearField(col.fieldname) && val) val = fromMonthYear(val) || val;
			state.rows[rowIdx][col.fieldname] = val;
		});
	};

	function _collectAndClose(dialog, tableId, rowIdx, columns, uid) {
		_collectValues(dialog, tableId, rowIdx, columns, uid);
		dialog.$wrapper.off("hide.bs.modal");
		dialog.hide();
	}

	// ── rebuild tbody from state ──────────────────────────────────────────────
	window.rebuildFtblBody = function rebuildFtblBody(tableId) {
		const state = window._perm_ftbl_state[tableId];
		if (!state) return;
		const tbody = document.getElementById(`tbody-${tableId}`);
		if (!tbody) return;
		tbody.innerHTML = state.rows.length
			? state.rows.map((row, i) => buildFtblRow(tableId, state.previewCols, row, i)).join("")
			: `<div class="ftbl-empty" style="padding:20px 16px;text-align:center;color:var(--color-text-tertiary,#aaa);font-size:13px;">No rows. Click "Add Row" to begin.</div>`;
		_ftbl_updateCount(tableId);
		window._ftbl_rowCheckChange(tableId);
	};

	// ── count display ─────────────────────────────────────────────────────────
	function _ftbl_updateCount(tableId) {
		const state = window._perm_ftbl_state[tableId];
		const el = document.getElementById(`row-count-${tableId}`);
		if (el && state)
			el.textContent = state.rows.length
				? `${state.rows.length} row${state.rows.length !== 1 ? "s" : ""}`
				: "";
	}

	// ── checkbox sync ─────────────────────────────────────────────────────────
	window._ftbl_rowCheckChange = function (tableId) {
		const all = document.querySelectorAll(`.ftbl-chk[data-tableid="${tableId}"]`);
		const checked = document.querySelectorAll(`.ftbl-chk[data-tableid="${tableId}"]:checked`);
		const allChk = document.getElementById(`chk-all-${tableId}`);
		const delBtn = document.getElementById(`ftbl-del-sel-${tableId}`);

		if (allChk) {
			allChk.checked = checked.length > 0 && checked.length === all.length;
			allChk.indeterminate = checked.length > 0 && checked.length < all.length;
		}

		if (delBtn) {
			delBtn.style.display = checked.length > 0 ? "inline-flex" : "none";
		}
	};

	// ── open row-edit dialog ──────────────────────────────────────────────────
	window.openRowDialog = function openRowDialog(tableId, rowIdx) {
		const state = window._perm_ftbl_state[tableId];
		if (!state) return;
		const row = state.rows[rowIdx];
		const columns = state.columns;
		const total = state.rows.length;
		const uid = `${tableId}-${rowIdx}-${Date.now()}`;

		const fieldsHtml = columns
			.map((col) => buildDialogInput(col, row[col.fieldname], uid))
			.join("");

		// ── button style matching lead.js exactly ─────────────────────────────
		const btnStyle = `height:30px;padding:0 10px;border:1px solid rgba(0,0,0,0.15);background:#fff;color:#344054;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;display:inline-flex;align-items:center;gap:4px;transition:all 0.15s;font-family:inherit;white-space:nowrap;`;

		const bodyHtml = `
<div>
	<!-- ── Header bar: title left, action buttons right ── -->
	<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid var(--color-border-tertiary,rgba(0,0,0,0.1));gap:8px;">
		<div style="font-size:15px;font-weight:600;color:var(--color-text-primary);flex-shrink:0;">Editing Row #${rowIdx + 1}</div>
		<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end;">
			<button onclick="window.__perm_dlg_delete_('${tableId}',${rowIdx})"
				style="width:30px;height:30px;border:none;background:#f04438;color:#fff;border-radius:6px;cursor:pointer;font-size:13px;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;"
				title="Delete this row"
				onmouseenter="this.style.background='#d92d20'" onmouseleave="this.style.background='#f04438'">🗑</button>
			<div style="width:1px;height:18px;background:rgba(0,0,0,0.12);margin:0 2px;flex-shrink:0;"></div>
			<button onclick="window.__perm_dlg_insert_('${tableId}',${rowIdx},'above')" style="${btnStyle}"
				onmouseenter="this.style.background='#f9fafb'" onmouseleave="this.style.background='#fff'">↑ Above</button>
			<button onclick="window.__perm_dlg_insert_('${tableId}',${rowIdx},'below')" style="${btnStyle}"
				onmouseenter="this.style.background='#f9fafb'" onmouseleave="this.style.background='#fff'">↓ Below</button>
			<button onclick="window.__perm_dlg_duplicate_('${tableId}',${rowIdx})" style="${btnStyle}"
				onmouseenter="this.style.background='#f9fafb'" onmouseleave="this.style.background='#fff'">⧉ Duplicate</button>
			<button onclick="window.__perm_close_dialog_()"
				style="width:30px;height:30px;border:none;background:transparent;color:#667085;border-radius:6px;cursor:pointer;font-size:20px;line-height:1;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;"
				onmouseenter="this.style.background='#f2f4f7'" onmouseleave="this.style.background='transparent'">×</button>
		</div>
	</div>

	<!-- ── Fields grid: flex-wrap, 50/50 for normal, 100% for wide ── -->
	<div style="display:flex;flex-wrap:wrap;gap:0;margin:0 -8px;align-items:flex-start;">${fieldsHtml}</div>
</div>`;

		const dialog = new frappe.ui.Dialog({
			title: " ",
			fields: [{ fieldtype: "HTML", fieldname: "row_form", options: bodyHtml }],
			size: "large",
		});

		dialog.$wrapper.find(".modal-header").hide();
		dialog.$wrapper
			.find(".modal-body")
			.css({ "padding-top": "20px", "padding-bottom": "10px" });
		dialog.$wrapper.find(".modal-footer").hide();

		// Keyboard shortcuts
		dialog.$wrapper.on("keydown", (e) => {
			if (e.ctrlKey && e.key === "ArrowUp" && rowIdx > 0) {
				_collectAndClose(dialog, tableId, rowIdx, columns, uid);
				window.rebuildFtblBody(tableId);
				window.openRowDialog(tableId, rowIdx - 1);
			}
			if (e.ctrlKey && e.key === "ArrowDown" && rowIdx < total - 1) {
				_collectAndClose(dialog, tableId, rowIdx, columns, uid);
				window.rebuildFtblBody(tableId);
				window.openRowDialog(tableId, rowIdx + 1);
			}
		});

		// Commit + rebuild on ESC / backdrop / × close
		dialog.$wrapper.on("hide.bs.modal", () => {
			_collectValues(dialog, tableId, rowIdx, columns, uid);
			window.rebuildFtblBody(tableId);
			window._perm_active_dialog = null;
		});

		window._perm_active_dialog = { dialog, tableId, rowIdx, columns, uid };

		dialog.show();

		// ── match lead.js dialog width ─────────────────────────────────────────
		dialog.$wrapper.find(".modal-dialog").css({
			display: "flex",
			alignItems: "center",
			minHeight: "100vh",
			margin: "0 auto",
			maxWidth: "780px",
			width: "90%",
		});
	};

	// ── build one preview row ─────────────────────────────────────────────────
	function buildFtblRow(tableId, previewCols, row, idx) {
		const rowId = row.name || `new-${tableId}-${idx}`;
		const colCells = previewCols
			.map(
				(col) => `
<div class="ftbl-cell" onclick="window.__perm_open_row_('${tableId}',${idx})"
	style="padding:6px 10px;display:flex;align-items:center;min-height:34px;border-right:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.07));font-size:13px;color:var(--color-text-primary);cursor:pointer;overflow:hidden;">
	<span style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis;max-width:100%;">${formatCellDisplay(col, row[col.fieldname])}</span>
</div>`,
			)
			.join("");

		return `
<div class="ftbl-row" data-rowid="${rowId}" data-tableid="${tableId}" data-idx="${idx}"
	style="display:grid;grid-template-columns:32px 44px ${previewCols.map(() => "1fr").join(" ")} 38px;border-bottom:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.08));transition:background 0.1s;"
	onmouseenter="this.style.background='var(--color-background-secondary,#F3F3F3)'"
	onmouseleave="this.style.background=''">
	<div style="padding:6px 8px;display:flex;align-items:center;justify-content:center;">
		<input type="checkbox" class="ftbl-chk" data-tableid="${tableId}" data-rowid="${rowId}"
			onchange="window.__perm_chkchg_('${tableId}')"
			onclick="event.stopPropagation()"
			style="width:13px;height:13px;accent-color:#378add;cursor:pointer;" />
	</div>
	<div onclick="window.__perm_open_row_('${tableId}',${idx})"
		style="padding:6px 8px;display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--color-text-secondary,#888);font-weight:500;cursor:pointer;">
		${idx + 1}
	</div>
	${colCells}
	<div style="padding:6px 6px;display:flex;align-items:center;justify-content:center;">
		<button onclick="event.stopPropagation();window.__perm_open_row_('${tableId}',${idx})"
			style="width:24px;height:24px;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.2));background:transparent;color:var(--color-text-secondary,#666);cursor:pointer;border-radius:5px;font-size:12px;display:inline-flex;align-items:center;justify-content:center;"
			title="Edit row">✏</button>
	</div>
</div>`;
	}

	// ── build the full table widget HTML ──────────────────────────────────────
	function buildFtblHTML(tableId, rows, previewCols) {
		const colHeaders = previewCols
			.map(
				(col) => `
<div style="padding:7px 10px;font-size:11px;font-weight:500;color:var(--color-text-secondary,#6b6b6b);text-transform:uppercase;letter-spacing:0.04em;border-right:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.1));">
	${col.label || col.fieldname.replace(/_/g, " ")}${col.reqd ? '<span style="color:#e24b4a;margin-left:2px;">*</span>' : ""}
</div>`,
			)
			.join("");

		const bodyHtml = rows.length
			? rows.map((row, i) => buildFtblRow(tableId, previewCols, row, i)).join("")
			: `<div class="ftbl-empty" style="padding:20px 16px;text-align:center;color:var(--color-text-tertiary,#aaa);font-size:13px;">No rows. Click "Add Row" to begin.</div>`;

		return `
<div class="frappe-child-table" data-tableid="${tableId}"
	style="border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.2));border-radius:var(--border-radius-md,8px);overflow:hidden;margin-top:4px;">
	<div style="display:grid;grid-template-columns:32px 44px ${previewCols.map(() => "1fr").join(" ")} 38px;background:var(--color-background-secondary,#F3F3F3);border-bottom:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.12));">
		<div style="padding:7px 8px;display:flex;align-items:center;justify-content:center;">
			<input type="checkbox" id="chk-all-${tableId}" onchange="window.__perm_toggleall_('${tableId}',this)"
				style="width:13px;height:13px;accent-color:#378add;cursor:pointer;" />
		</div>
		<div style="padding:7px 10px;font-size:11px;font-weight:500;color:var(--color-text-secondary,#6b6b6b);text-transform:uppercase;letter-spacing:0.04em;">No.</div>
		${colHeaders}
		<div style="padding:7px 8px;"></div>
	</div>
	<div id="tbody-${tableId}" class="ftbl-body" data-tableid="${tableId}">${bodyHtml}</div>
	<div style="padding:6px 10px;border-top:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.1));background:var(--color-background-secondary,#F3F3F3);display:flex;align-items:center;gap:6px;">
		<button id="ftbl-del-sel-${tableId}" onclick="window.__perm_delsel_('${tableId}')"
			style="display:none;align-items:center;gap:5px;height:28px;padding:0 14px;background:#e24b4a;color:#fff;border:none;border-radius:5px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;">
			Delete
		</button>
		<button onclick="window.__perm_addrow_('${tableId}')"
			style="height:28px;padding:0 14px;background:none;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.25));color:var(--color-text-primary);border-radius:5px;font-size:12px;font-weight:500;cursor:pointer;font-family:inherit;">
			Add Row
		</button>
		<span id="row-count-${tableId}" style="margin-left:auto;font-size:12px;color:var(--color-text-secondary,#6b6b6b);">
			${rows.length ? rows.length + " row" + (rows.length !== 1 ? "s" : "") : ""}
		</span>
	</div>
</div>`;
	}

	// ── build table widgets — cols now read full metadata from config.columns ─
	const tableWidgetHtml = Object.entries(table_fields || {})
		.map(([fieldname, config]) => {
			const tableId = `upd-${fieldname}`;

			// ── FIXED: config.columns supports both { fn: "label" } and
			//           { fn: { label, fieldtype, options, reqd, description } }
			const cols = Object.entries(config.columns || {}).map(([fn, meta]) => {
				if (typeof meta === "string") {
					return {
						fieldname: fn,
						label: meta,
						fieldtype: "Data", // fallback only
					};
				}
				// full metadata object from updated API
				return {
					fieldname: fn,
					label: meta.label || fn.replace(/_/g, " "),
					fieldtype: meta.fieldtype || "Data",
					options: meta.options || "",
					reqd: meta.reqd || 0,
					description: meta.description || "",
				};
			});

			const initRows = (current_values[fieldname] || []).map((r) => ({ ...r }));
			const previewCols = cols.slice(0, 4);

			// register into global state
			window._perm_ftbl_state[tableId] = {
				rows: [...initRows],
				columns: cols,
				previewCols,
				childDoctype: config.child_doctype || null,
			};

			const widgetHtml = buildFtblHTML(tableId, initRows, previewCols);

			return `
<div style="margin-top:12px;">
	<div class="fg-row fg-table-toggle" data-fieldname="${fieldname}" data-tableid="${tableId}"
		style="display:flex;align-items:center;gap:10px;padding:12px 14px;border:2px solid #00000020;border-radius:10px;cursor:pointer;background:white;transition:all 0.2s ease;"
		onmouseenter="this.style.borderColor='black'" onmouseleave="if(!this.classList.contains('selected'))this.style.borderColor='#00000020'"
		onclick="window._perm_toggleTableField(this,'${tableId}')">
		<div class="fg-cb" style="width:16px;height:16px;border-radius:4px;border:2px solid black;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:white;">
			<div class="fg-tick" style="display:none;width:8px;height:5px;border-left:2px solid white;border-bottom:2px solid white;transform:rotate(-45deg) translate(1px,-1px);"></div>
		</div>
		<span class="fg-label" style="font-size:13px;font-weight:500;color:var(--color-text-primary);">${frappe.utils.escape_html(config.label)}</span>
	</div>
	<div id="ftbl-section-${tableId}" style="display:none;margin-top:8px;">${widgetHtml}</div>
</div>`;
		})
		.join("");

	// ── simple fields grid ────────────────────────────────────────────────────
	const simpleHtml = `
<p style="font-size:11px;font-weight:500;text-transform:uppercase;margin-bottom:12px;">${__("Select fields to update")}</p>
<div id="fg-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;">
	${Object.entries(fields)
		.map(([fn, fm]) => {
			const lbl = typeof fm === "string" ? fm : fm?.label || fn.replace(/_/g, " ");
			const old = current_values[fn] || "";
			return `<div class="fg-row" data-fieldname="${fn}" data-label="${frappe.utils.escape_html(lbl)}" data-current="${frappe.utils.escape_html(old)}"
	style="display:flex;align-items:center;gap:10px;padding:12px 14px;border:2px solid #00000020;border-radius:10px;cursor:pointer;background:white;transition:all 0.2s ease;min-width:0;"
	onmouseenter="this.style.borderColor='black'" onmouseleave="if(!this.classList.contains('selected'))this.style.borderColor='#00000020'">
	<div class="fg-cb" style="width:16px;height:16px;border-radius:4px;border:2px solid black;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:white;">
		<div class="fg-tick" style="display:none;width:8px;height:5px;border-left:2px solid white;border-bottom:2px solid white;transform:rotate(-45deg) translate(1px,-1px);"></div>
	</div>
	<span class="fg-label" style="font-size:13px;font-weight:500;color:var(--color-text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${frappe.utils.escape_html(lbl)}</span>
</div>`;
		})
		.join("")}
</div>
${tableWidgetHtml}
<div id="fg-inputs-section" style="display:none;margin-top:16px;"><hr style="border:none;border-top:1px solid var(--color-border-tertiary);margin:0 0 16px;" /><div id="fg-inputs-container"></div></div>`;

	const dialog = new frappe.ui.Dialog({
		title: __("Update Detail"),
		fields: [
			{ fieldname: "fields_html", fieldtype: "HTML", options: simpleHtml },
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
			let has_selection = false,
				missing = false;

			// simple fields
			dialog.$wrapper.find("#fg-grid .fg-row.selected").each(function () {
				const fn = $(this).data("fieldname");
				const label = get_label(fn);
				const inp = dialog.$wrapper.find(
					`#fg-inputs-container .fg-new-input[data-fieldname="${fn}"]`,
				);
				let nv = "";
				if (inp.hasClass("fg-file-url")) {
					nv = inp.val();
					if (!nv) {
						frappe.msgprint(__("Please upload a file."));
						missing = true;
						return false;
					}
				} else if (inp.attr("type") === "checkbox") nv = inp.is(":checked") ? 1 : 0;
				else nv = inp.val().trim();
				if (!nv) {
					frappe.msgprint(__(`Please enter a new value for "${label}".`));
					missing = true;
					return false;
				}
				field_updates[fn] = { old: inp.data("old") || "", new: nv };
				has_selection = true;
			});
			if (missing) return;

			// table fields — read from _perm_ftbl_state
			dialog.$wrapper.find(".fg-table-toggle.selected").each(function () {
				const fn = $(this).data("fieldname");
				const tableId = $(this).data("tableid");
				const rows = (window._perm_ftbl_state[tableId] || {}).rows || [];
				field_updates[fn] = { old: current_values[fn] || [], new: rows };
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
					customer_name,
					reason: values.reason,
					field_updates: JSON.stringify(field_updates),
					service_doctype: mode === "service" ? frm.doctype : null,
					service_name: mode === "service" ? frm.doc.name : null,
				},
				callback(res) {
					if (res.message?.status === "success") {
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

	function toggleReasonField(dialog) {
		const hasSimple = dialog.$wrapper.find("#fg-grid .fg-row.selected").length > 0;
		const hasTable = dialog.$wrapper.find(".fg-table-toggle.selected").length > 0;
		if (hasSimple || hasTable) {
			dialog.get_field("reason").$wrapper.show();
		} else {
			dialog.get_field("reason").$wrapper.hide();
			dialog.set_value("reason", "");
		}
	}

	dialog.get_field("reason").$wrapper.hide();
	dialog.$wrapper.find(".modal-dialog").css({ "max-width": "1200px", width: "45%" });

	const _saved = {};

	// simple field row click
	dialog.$wrapper.on("click", "#fg-grid .fg-row", function () {
		const fn = $(this).data("fieldname");
		const selected = $(this).toggleClass("selected").hasClass("selected");
		$(this).find(".fg-tick").toggle(selected);
		$(this)
			.find(".fg-cb")
			.css("background", selected ? "black" : "white");
		_fg_rebuild(dialog, fields, current_values, _saved);
		toggleReasonField(dialog);
		if (selected)
			setTimeout(
				() =>
					dialog.$wrapper
						.find(`#fg-inputs-container .fg-new-input[data-fieldname="${fn}"]`)
						.focus(),
				30,
			);
	});

	const _fg_files = {};
	dialog.$wrapper.on("change", ".fg-file-input", function () {
		const file = this.files[0];
		const fieldname = $(this).data("fieldname");
		if (!file) return;
		_fg_files[fieldname] = file;
		dialog.$wrapper.find(`.fg-file-name[data-fieldname="${fieldname}"]`).text(file.name);
	});
}

// ── table field toggle ────────────────────────────────────────────────────────
window._perm_toggleTableField = function (el, tableId) {
	const $el = $(el);
	const selected = $el.toggleClass("selected").hasClass("selected");

	$el.css("border-color", selected ? "black" : "#00000020");
	$el.css("background", selected ? "#eeeeee" : "white");
	$el.find(".fg-tick").toggle(selected);
	$el.find(".fg-cb").css("background", selected ? "black" : "white");

	$(`#ftbl-section-${tableId}`).toggle(selected);

	const dialog = $el.closest(".modal").data("dialog") || cur_dialog;
	if (dialog && dialog.get_field) {
		const hasSimple = dialog.$wrapper.find("#fg-grid .fg-row.selected").length > 0;
		const hasTable = dialog.$wrapper.find(".fg-table-toggle.selected").length > 0;
		if (hasSimple || hasTable) {
			dialog.get_field("reason").$wrapper.show();
		} else {
			dialog.get_field("reason").$wrapper.hide();
			dialog.set_value("reason", "");
		}
	}
};

// ─── _open_accept_updates_dialog ─────────────────────────────────────────────
function _open_accept_updates_dialog(frm, pending_requests, mode, field_meta = {}) {
	const customer_name = mode === "service" ? frm.doc.customer : frm.doc.name;

	function render_value(val, fn) {
		if (val === null || val === undefined || val === "")
			return `<span style="font-style:italic;color:var(--color-text-tertiary);">empty</span>`;
		if (typeof val === "object" && val.name) val = val.name;
		val = String(val).trim();
		const meta = field_meta[fn] || {};
		if (meta.fieldtype === "Link")
			return `<a href="/app/file/${encodeURIComponent(val)}" target="_blank" style="color:#260fea;font-weight:500;">📎 ${frappe.utils.escape_html(val)}</a>`;
		return frappe.utils.escape_html(val);
	}

	function render_table_readonly(rows, accentColor) {
		if (!rows || !rows.length)
			return `<div style="padding:8px;color:var(--color-text-tertiary);font-size:12px;">No rows</div>`;
		const keys = Object.keys(rows[0]).filter(
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
		const thStyle =
			"padding:7px 8px;font-size:11px;font-weight:500;color:var(--color-text-secondary,#6b6b6b);text-align:left;text-transform:uppercase;letter-spacing:0.4px;border-bottom:0.5px solid var(--color-border-tertiary);";
		const tdStyle = `padding:6px 8px;border-bottom:0.5px solid var(--color-border-tertiary);color:${accentColor || "var(--color-text-primary)"};font-size:13px;`;
		return `<div style="border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.2));border-radius:var(--border-radius-md,8px);overflow:hidden;">
			<table style="width:100%;border-collapse:collapse;">
				<thead><tr style="background:var(--color-background-secondary,#F3F3F3);">${keys.map((k) => `<th style="${thStyle}">${k.replace(/_/g, " ")}</th>`).join("")}</tr></thead>
				<tbody>${rows.map((row) => `<tr>${keys.map((k) => `<td style="${tdStyle}">${frappe.utils.escape_html(row[k] || "")}</td>`).join("")}</tr>`).join("")}</tbody>
			</table>
		</div>`;
	}

	let all_html = "";
	pending_requests.forEach((req, idx) => {
		all_html += `<div style="margin-bottom:20px;">
			<div style="font-size:13px;font-weight:500;">Request ${idx + 1} — <b>${req.requested_by}</b></div>
			<div style="font-size:12px;color:var(--color-text-secondary);margin-bottom:10px;">Reason: ${req.reason}</div>`;

		Object.entries(req.field_updates).forEach(([fn, vals]) => {
			const lbl = fn.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
			const is_table = Array.isArray(vals.old) || Array.isArray(vals.new);

			const inner = is_table
				? `
<div style="margin-top:8px;">
	<div style="font-size:11px;color:#666;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;font-weight:500;">Current</div>
	${render_table_readonly(vals.old, "var(--color-text-secondary)")}
</div>
<div style="margin-top:10px;">
	<div style="font-size:11px;color:#666;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;font-weight:500;">New</div>
	${render_table_readonly(vals.new, "#3C3489")}
</div>`
				: `
<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:6px;">
	<div>
		<div style="font-size:11px;color:#666;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;font-weight:500;">Current</div>
		<div style="padding:8px 10px;background:#f8f9fa;border:1px solid #ddd;border-radius:8px;font-size:13px;min-height:36px;">${render_value(vals.old, fn)}</div>
	</div>
	<div>
		<div style="font-size:11px;color:#666;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;font-weight:500;">New</div>
		<div style="padding:8px 10px;background:white;border:1px solid #ccc;border-radius:8px;font-size:13px;min-height:36px;font-weight:500;">${render_value(vals.new, fn)}</div>
	</div>
</div>`;

			all_html += `
<div class="fg-row au-field-row" data-fieldname="${fn}" data-comment="${req.comment_name}"
	style="display:flex;align-items:flex-start;gap:10px;padding:12px 14px;border:2px solid #00000020;border-radius:10px;cursor:pointer;background:white;margin-bottom:10px;transition:all 0.2s ease;"
	onmouseenter="this.style.borderColor='black'" onmouseleave="if(this.classList.contains('selected'))this.style.borderColor='black';else this.style.borderColor='#00000020'">
	<div class="fg-cb" style="width:16px;height:16px;border-radius:4px;border:2px solid black;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:black;margin-top:3px;">
		<div class="fg-tick" style="width:8px;height:5px;border-left:2px solid white;border-bottom:2px solid white;transform:rotate(-45deg) translate(1px,-1px);"></div>
	</div>
	<input type="checkbox" class="approve-field-checkbox" data-fieldname="${fn}" data-comment="${req.comment_name}" checked style="display:none;" />
	<div style="flex:1;">
		<span style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;">${frappe.utils.escape_html(lbl)}</span>
		${inner}
	</div>
</div>`;
		});
		all_html += `</div>`;
	});

	const d = new frappe.ui.Dialog({
		title: __("Accept Updates"),
		fields: [
			{
				fieldname: "html",
				fieldtype: "HTML",
				options: `<p style="font-size:11px;font-weight:500;text-transform:uppercase;margin-bottom:12px;">${__("Select fields to accept")}</p>${all_html}`,
			},
		],
		primary_action_label: __("Accept Selected"),
		primary_action() {
			const by_comment = {};
			d.$wrapper.find(".approve-field-checkbox:checked").each(function () {
				const f = $(this).data("fieldname"),
					c = $(this).data("comment");
				if (!by_comment[c]) by_comment[c] = [];
				by_comment[c].push(f);
			});
			if (!Object.keys(by_comment).length) {
				frappe.msgprint(__("Select at least one field."));
				return;
			}
			d.hide();
			Promise.all(
				Object.entries(by_comment).map(([cn, fs]) =>
					frappe.call({
						method: "verp_staffing.crm.api.permission_request.apply_field_updates",
						args: {
							customer_name,
							comment_name: cn,
							approved_fields: JSON.stringify(fs),
						},
					}),
				),
			).then(() => {
				frappe.show_alert({ message: __("Updated successfully"), indicator: "green" });
				frm.reload_doc();
			});
		},
		secondary_action_label: __("Reject All"),
		secondary_action() {
			frappe.confirm(__("Reject all updates?"), () => {
				Promise.all(
					pending_requests.map((req) =>
						frappe.call({
							method: "verp_staffing.crm.api.permission_request.reject_field_update_request",
							args: { customer_name, comment_name: req.comment_name },
						}),
					),
				).then(() => {
					frappe.show_alert({ message: __("All updates rejected"), indicator: "red" });
					d.hide();
					frm.reload_doc();
				});
			});
		},
	});

	d.show();

	d.$wrapper.find(".modal-dialog").css({
		display: "flex",
		maxWidth: "850px",
		width: "90%",
	});

	d.$wrapper.on("click", ".fg-row.au-field-row", function () {
		const selected = $(this).toggleClass("selected").hasClass("selected");
		$(this).css("border-color", selected ? "black" : "#00000020");
		$(this)
			.find(".fg-cb")
			.css("background", selected ? "black" : "white");
		$(this)
			.find(".fg-tick")
			.css("display", selected ? "block" : "none");
		const fn = $(this).data("fieldname"),
			cn = $(this).data("comment");
		d.$wrapper
			.find(`.approve-field-checkbox[data-fieldname="${fn}"][data-comment="${cn}"]`)
			.prop("checked", selected);
	});
}

function _fg_rebuild(dialog, fields, current_values, saved) {
	dialog.$wrapper.find(".fg-new-input").each(function () {
		const fn = $(this).data("fieldname");
		if ($(this).hasClass("fg-file-url")) saved[fn] = $(this).val();
		else if ($(this).attr("type") === "checkbox") saved[fn] = $(this).is(":checked") ? 1 : 0;
		else saved[fn] = $(this).val();
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
		const fn = $(this).data("fieldname");
		const fm = fields[fn];
		const fieldtype = fm?.fieldtype || "Data";
		const label = fm?.label || fn.replace(/_/g, " ");
		const options = fm?.options || "";
		const old_val = current_values[fn] != null ? String(current_values[fn]) : "";
		const saved_val = saved[fn] != null ? String(saved[fn]) : "";

		let inp_html = "";
		if (fieldtype === "Select") {
			const opts = options.split("\n").filter((o) => o);
			inp_html = `<select class="fg-new-input" data-fieldname="${fn}" data-old="${frappe.utils.escape_html(old_val)}" style="width:100%;padding:8px 10px;border:1px solid #ccc;border-radius:8px;font-size:13px;background:white;"><option value="">Select ${label}</option>${opts.map((o) => `<option value="${frappe.utils.escape_html(o)}"${saved_val === o ? " selected" : ""}>${frappe.utils.escape_html(o)}</option>`).join("")}</select>`;
		} else if (fieldtype === "Check") {
			inp_html = `<input type="checkbox" class="fg-new-input" data-fieldname="${fn}" data-old="${old_val}" ${saved_val == "1" ? "checked" : ""} />`;
		} else if (fieldtype === "Link") {
			const cur_html = old_val
				? `<a href="/app/file/${encodeURIComponent(old_val)}" target="_blank" style="color:#260fea;font-weight:500;">📎 View Current File</a>`
				: `<span style="color:var(--color-text-tertiary);font-style:italic;">empty</span>`;
			container.append(`<div class="fg-input-block" style="margin-bottom:18px;padding:12px;border:1px solid var(--color-border-tertiary);border-radius:10px;background:var(--color-background-secondary);">
				<div style="font-size:12px;font-weight:600;margin-bottom:10px;">${frappe.utils.escape_html(label)}</div>
				<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
					<div><div style="font-size:11px;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;">${__("Current")}</div><div style="padding:8px 10px;background:#f8f9fa;border:1px solid #ddd;border-radius:8px;font-size:13px;min-height:36px;">${cur_html}</div></div>
					<div><div style="font-size:11px;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;">${__("New")}</div>
						<input type="file" class="fg-file-input" data-fieldname="${fn}" style="font-size:12px;" />
						<div class="fg-file-name" data-fieldname="${fn}" style="font-size:11px;color:var(--color-text-secondary);">${saved_val ? `<span style="color:#260fea;">${frappe.utils.escape_html(saved_val)}</span>` : ""}</div>
						<input type="hidden" class="fg-new-input fg-file-url" data-fieldname="${fn}" data-old="${frappe.utils.escape_html(old_val)}" value="${frappe.utils.escape_html(saved_val)}" />
					</div>
				</div>
			</div>`);
			return;
		} else {
			inp_html = `<input class="fg-new-input" type="text" data-fieldname="${fn}" data-old="${frappe.utils.escape_html(old_val)}" value="${frappe.utils.escape_html(saved_val)}" placeholder="${__("Enter new value for")} ${frappe.utils.escape_html(label)}" style="width:100%;padding:8px 10px;border:1px solid #ccc;border-radius:8px;font-size:13px;background:white;" />`;
		}

		container.append(`<div class="fg-input-block" style="margin-bottom:18px;padding:12px;border:1px solid var(--color-border-tertiary);border-radius:10px;background:var(--color-background-secondary);">
			<div style="font-size:12px;font-weight:600;margin-bottom:10px;">${frappe.utils.escape_html(label)}</div>
			<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
				<div><div style="font-size:11px;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;">${__("Current")}</div>
					<div style="padding:8px 10px;background:#f8f9fa;border:1px solid #ddd;border-radius:8px;font-size:13px;min-height:36px;">${old_val ? frappe.utils.escape_html(old_val) : `<span style="color:var(--color-text-tertiary);font-style:italic;">empty</span>`}</div>
				</div>
				<div><div style="font-size:11px;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.4px;">${__("New")}</div>${inp_html}</div>
			</div>
		</div>`);
	});
}
