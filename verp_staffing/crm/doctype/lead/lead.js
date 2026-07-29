// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

let isSaving = false;

frappe.ui.form.on("Lead", {
	onload(frm) {
		if (frappe.session.user !== "Administrator") {
			frm.set_df_property("lead_owner", "read_only", 1);
		}
		frm.set_df_property("status", "read_only", 1);
	},

	refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Lead",
			doctype: frm.doctype,
			type: "Form",
		};
		frappe.breadcrumbs.update();
		window.render_notes(frm);
		window.render_activity_section(frm);

		window._ftbl_state = {};
		window._temp_files = {};
		window._ftbl_active_dialog = null;
		frm.set_df_property("lead_detail", "options", "");

		if (frm.is_new()) return;

		frappe.call({
			method: "verp_staffing.crm.doctype.lead.lead.lead_has_opportunity", // match your actual module path
			args: { lead_name: frm.doc.name },
			callback: function (r) {
				if (r.message) {
					window._lead_form_locked = true;
					frm.disable_form();
					watchAndLockLeadDetail();
				} else {
					frm.add_custom_button("Create Opportunity", () => {
						open_create_opportunity_dialog(frm);
					});
				}
			},
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Lead";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		setupLeadDetailForm(frm);

		const roles = frappe.user_roles;

		if (roles.includes("Extra Menu Item Not Show")) {
			const hideElements = ({ selectors = [], keywordSelectors = [], keywords = [] }) => {
				selectors.forEach((sel) => {
					const el = document.querySelector(sel);
					if (el) el.style.display = "none";
				});
				keywordSelectors.forEach((sel) => {
					document.querySelectorAll(sel).forEach((el) => {
						const text = el.innerText?.trim();
						if (text && keywords.some((k) => text.includes(k))) {
							el.style.display = "none";
							const li = el.closest("li");
							if (li) li.style.display = "none";
						}
					});
				});
			};
			const MENU_HIDE = ["Links", "Duplicate", "Copy to Clipboard"];
			const cleanMenu = () => {
				MENU_HIDE.forEach((label) => {
					try {
						frm.page.remove_menu_item(label);
					} catch {}
				});
				hideElements({
					keywordSelectors: [".dropdown-menu .dropdown-item"],
					keywords: MENU_HIDE,
				});
			};
			$(frm.page.wrapper).on("shown.bs.dropdown", cleanMenu);
			const cleanSidebar = () =>
				hideElements({
					selectors: [
						".form-sidebar .assigned-to",
						".form-sidebar .btn-share",
						".form-sidebar .shared-with",
					],
					keywordSelectors: [".form-sidebar *"],
					keywords: ["Assigned", "Share"],
				});
			const runCleanup = () => {
				cleanMenu();
				cleanSidebar();
			};
			runCleanup();
			let attempts = 0;
			const timer = setInterval(() => {
				runCleanup();
				if (attempts++ > 12) clearInterval(timer);
			}, 200);
		}
	},
});

function setupLeadDetailForm(frm) {
	let _lead_detail_dirty = false;
	let _lead_form_locked = !!window._lead_form_locked;

	// ─── Field name sets ──────────────────────────────────────────────────────────
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

	// ─── Date helpers ─────────────────────────────────────────────────────────────
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

	// ─── Error helpers ────────────────────────────────────────────────────────────
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

	// ─── Column helpers ───────────────────────────────────────────────────────────
	function getTableColumns(child_meta) {
		return child_meta.fields.filter(
			(f) =>
				f.fieldname &&
				!f.hidden &&
				!f.read_only &&
				!["Section Break", "Column Break", "HTML", "Button", "Fold", "Heading"].includes(
					f.fieldtype,
				),
		);
	}
	function getDepartmentFields(doctype_name) {
		return frappe.db
			.get_single_value("ERP Configuration", "department_access_form_fields")
			.then((data) => {
				if (!data) return [];
				try {
					return JSON.parse(data)[doctype_name] || [];
				} catch (e) {
					return [];
				}
			});
	}

	// ─── Cell display (read-only text in grid) ────────────────────────────────────
	function formatCellDisplay(col, value) {
		if (value === null || value === undefined || value === "")
			return `<span style="color:var(--color-text-tertiary,#bbb);">—</span>`;
		if (col.fieldtype === "Check") return value ? "✓" : "";
		if (isMonthYearField(col.fieldname)) return toMonthYear(String(value));
		const str = String(value);
		return frappe.utils?.escape_html ? frappe.utils.escape_html(str) : str;
	}

	// ─── Build one dialog field (full form) ───────────────────────────────────────
	function buildDialogInput(col, currentVal, uid) {
		const id = `dlg-${uid}-${col.fieldname}`;
		const val = currentVal ?? "";
		const label = col.label || frappe.model.unscrub(col.fieldname);

		let noteHtml = col.description
			? `<div style="font-size:11px;color:var(--color-text-secondary,#888);margin-top:3px;">NOTE: ${col.description}</div>`
			: "";

		const baseStyle = `width:100%;height:32px;padding:0 10px;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.25));border-radius:6px;font-size:13px;font-family:inherit;background:var(--color-background-secondary,#F3F3F3);color:var(--color-text-primary);outline:none;`;

		let inputHtml;

		if (col.fieldtype === "Check") {
			return `<div class="ftbl-dialog-field" data-fieldname="${col.fieldname}" style="width:100%;padding:0 8px;margin-bottom:10px;">
        <label style="display:inline-flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">
            <input id="${id}" type="checkbox" ${val ? "checked" : ""} style="width:14px;height:14px;accent-color:#378add;cursor:pointer;" />
            ${label}
        </label>${noteHtml}
    </div>`;
		}

		if (isEmailField(col.fieldname)) {
			inputHtml = `<input id="${id}" type="email" value="${val}" data-override="email" style="${baseStyle}" placeholder="${label}" />`;
		} else if (isPhoneField(col.fieldname)) {
			inputHtml = `<input id="${id}" type="tel" value="${val}" data-override="phone" style="${baseStyle}" placeholder="${label} (e.g. Exp: +1xxxxxxxxxx Or +91xxxxxxxxxx)" />`;
		} else if (isMonthYearField(col.fieldname)) {
			inputHtml = `<input id="${id}" type="text" value="${toMonthYear(val)}" data-override="month-year" maxlength="7" style="${baseStyle}" placeholder="MM-YYYY (e.g. 01-2025)" />`;
			noteHtml = `<div style="font-size:11px;color:var(--color-text-secondary,#888);margin-top:3px;">NOTE: Use date format: MM-YYYY</div>`;
		} else if (col.fieldtype === "Select") {
			const opts = (col.options || "").split("\n").filter(Boolean);
			inputHtml = `<select id="${id}" style="${baseStyle}">
        <option value="">Select ${label}…</option>
        ${opts.map((o) => `<option value="${o}"${o === val ? " selected" : ""}>${o}</option>`).join("")}
    </select>`;
		} else if (["Text", "Small Text", "Long Text"].includes(col.fieldtype)) {
			const minH = col.fieldname === "description" ? "150px" : "70px";
			inputHtml = `<textarea id="${id}" style="width:100%;min-height:${minH};padding:8px 10px;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.25));border-radius:6px;font-size:13px;font-family:inherit;background:var(--color-background-secondary,#F3F3F3);color:var(--color-text-primary);outline:none;resize:vertical;line-height:1.5;" placeholder="${label}">${val}</textarea>`;
			if (col.fieldname === "description")
				noteHtml = `<div style="font-size:11px;color:var(--color-text-secondary,#888);margin-top:3px;">NOTE: Minimum length: 800 characters (excluding spaces).</div>`;
		} else if (["Int", "Float", "Currency"].includes(col.fieldtype)) {
			inputHtml = `<input id="${id}" type="text" value="${val == 0 ? "" : val}" style="${baseStyle}" placeholder="${label}" />`;
		} else if (col.fieldtype === "Date") {
			inputHtml = `<input id="${id}" type="date" value="${(val || "").split(" ")[0] || ""}" style="${baseStyle}" placeholder="${label}" />`;
		} else {
			inputHtml = `<input id="${id}" type="text" value="${val}" style="${baseStyle}" placeholder="${label}" />`;
		}

		const isWide = ["Text", "Small Text", "Long Text"].includes(col.fieldtype);
		const labelHtml = `<div style="font-size:12px;font-weight:500;color:var(--color-text-secondary,#6b6b6b);margin-bottom:5px;">
    ${label}${col.reqd ? '<span style="color:#e24b4a;margin-left:2px;">*</span>' : ""}
</div>`;

		return `<div class="ftbl-dialog-field" data-fieldname="${col.fieldname}"
    style="width:${isWide ? "100%" : "calc(50% - 8px)"};min-width:${isWide ? "100%" : "200px"};padding:0 8px;margin-bottom:10px;">
    ${labelHtml}${inputHtml}${noteHtml}
</div>`;
	}

	// ─── Open row edit dialog ─────────────────────────────────────────────────────
	function openRowDialog(field, rowIdx) {
		const state = window._ftbl_state[field];
		if (!state) return;
		const row = state.rows[rowIdx];
		const columns = state.columns;
		const total = state.rows.length;
		const uid = `${field}-${rowIdx}-${Date.now()}`;

		const fieldsHtml = columns
			.map((col) => buildDialogInput(col, row[col.fieldname], uid))
			.join("");

		const btnStyle = `height:30px;padding:0 12px;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.25));background:var(--color-background-primary,#fff);color:var(--color-text-primary);border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;font-family:inherit;transition:background 0.1s;`;

		const bodyHtml = `
<div>
	<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:8px;">
		<div style="font-size:15px;font-weight:600;color:var(--color-text-primary);">Editing Row #${rowIdx + 1}</div>
		<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">

			<button onclick="window._ftbl_dlg_delete('${field}',${rowIdx},'${uid}')"
				style="width:32px;height:32px;border:none;background:#f04438;color:#fff;border-radius:8px;cursor:pointer;font-size:14px;display:inline-flex;align-items:center;justify-content:center;transition:all 0.15s;"
				title="Delete"
				onmouseenter="this.style.background='#d92d20'"
				onmouseleave="this.style.background='#f04438'">
				🗑
			</button>

			<div style="width:1px;height:20px;background:rgba(0,0,0,0.1);margin:0 2px;"></div>

			<button onclick="window._ftbl_dlg_insert('${field}',${rowIdx},'above','${uid}')"
				style="height:32px;padding:0 12px;border:1px solid rgba(0,0,0,0.15);background:#fff;color:#344054;border-radius:8px;font-size:12px;font-weight:500;cursor:pointer;display:flex;align-items:center;gap:4px;transition:all 0.15s;"
				onmouseenter="this.style.background='#f9fafb'"
				onmouseleave="this.style.background='#fff'">
				↑ Above
			</button>

			<button onclick="window._ftbl_dlg_insert('${field}',${rowIdx},'below','${uid}')"
				style="height:32px;padding:0 12px;border:1px solid rgba(0,0,0,0.15);background:#fff;color:#344054;border-radius:8px;font-size:12px;font-weight:500;cursor:pointer;display:flex;align-items:center;gap:4px;transition:all 0.15s;"
				onmouseenter="this.style.background='#f9fafb'"
				onmouseleave="this.style.background='#fff'">
				↓ Below
			</button>

			<button onclick="window._ftbl_dlg_duplicate('${field}',${rowIdx},'${uid}')"
				style="height:32px;padding:0 12px;border:1px solid rgba(0,0,0,0.15);background:#fff;color:#344054;border-radius:8px;font-size:12px;font-weight:500;cursor:pointer;display:flex;align-items:center;gap:4px;transition:all 0.15s;"
				onmouseenter="this.style.background='#f9fafb'"
				onmouseleave="this.style.background='#fff'">
				⧉ Duplicate
			</button>

			<div style="flex:1;"></div>

			<button onclick="window._ftbl_close_dialog()"
				style="width:32px;height:32px;border:none;background:transparent;color:#667085;border-radius:8px;cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;transition:all 0.15s;"
				title="Close"
				onmouseenter="this.style.background='#f2f4f7';this.style.color='#101828'"
				onmouseleave="this.style.background='transparent';this.style.color='#667085'">
				×
			</button>

		</div>
	</div>

	<div style="display:flex;flex-wrap:wrap;gap:4px;margin:0 -8px;">
		${fieldsHtml}
	</div>

	<div style="display:flex;align-items:center;justify-content:space-between;margin-top:16px;padding-top:14px;border-top:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.1));">
		<div style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--color-text-secondary,#888);">
			<span style="margin-right:4px;">⌨ Shortcuts:</span>
			<kbd style="padding:2px 6px;border:0.5px solid var(--color-border-secondary);border-radius:4px;font-size:10px;background:var(--color-background-secondary);font-family:inherit;">Ctrl + Up</kbd>
			<span style="margin:0 3px;">.</span>
			<kbd style="padding:2px 6px;border:0.5px solid var(--color-border-secondary);border-radius:4px;font-size:10px;background:var(--color-background-secondary);font-family:inherit;">Ctrl + Down</kbd>
			<span style="margin:0 3px;">.</span>
			<kbd style="padding:2px 6px;border:0.5px solid var(--color-border-secondary);border-radius:4px;font-size:10px;background:var(--color-background-secondary);font-family:inherit;">ESC</kbd>
		</div>
		<button onclick="window._ftbl_dlg_insert('${field}',${rowIdx},'below','${uid}')" style="${btnStyle}">Insert Below</button>
	</div>
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

		dialog.$wrapper.on("keydown", (e) => {
			if (e.ctrlKey && e.key === "ArrowUp" && rowIdx > 0) {
				_collectAndClose(dialog, field, rowIdx, columns, uid);
				openRowDialog(field, rowIdx - 1);
			}
			if (e.ctrlKey && e.key === "ArrowDown" && rowIdx < total - 1) {
				_collectAndClose(dialog, field, rowIdx, columns, uid);
				openRowDialog(field, rowIdx + 1);
			}
		});

		dialog.$wrapper.on("hide.bs.modal", () => {
			_collectValues(dialog, field, rowIdx, columns, uid);
			rebuildFtblBody(field);
			window._ftbl_active_dialog = null;
		});

		window._ftbl_active_dialog = { dialog, field, rowIdx, columns, uid };
		dialog.show();
		dialog.$wrapper.find(".modal-dialog").css({
			display: "flex",
			alignItems: "center",
			minHeight: "100vh",
			margin: "0 auto",
		});
	}

	// ─── Helpers used by dialog action buttons ────────────────────────────────────
	function _collectValues(dialog, field, rowIdx, columns, uid) {
		const state = window._ftbl_state[field];
		if (!state || !state.rows[rowIdx]) return;
		columns.forEach((col) => {
			const el = dialog.$wrapper[0].querySelector(`#dlg-${uid}-${col.fieldname}`);
			if (!el) return;
			let val = el.type === "checkbox" ? (el.checked ? 1 : 0) : el.value;
			if (isMonthYearField(col.fieldname) && val) val = fromMonthYear(val) || val;
			state.rows[rowIdx][col.fieldname] = val;
		});
	}

	function _collectAndClose(dialog, field, rowIdx, columns, uid) {
		_collectValues(dialog, field, rowIdx, columns, uid);
		dialog.$wrapper.off("hide.bs.modal");
		dialog.hide();
	}

	// ─── Dialog action button handlers (global, called from onclick) ──────────────
	window._ftbl_dlg_delete = function (field, rowIdx, uid) {
		const ad = window._ftbl_active_dialog;
		if (ad) {
			ad.dialog.$wrapper.off("hide.bs.modal");
			ad.dialog.hide();
		}
		const state = window._ftbl_state[field];
		if (!state) return;
		state.rows.splice(rowIdx, 1);
		rebuildFtblBody(field);
	};

	window._ftbl_close_dialog = function () {
		const ad = window._ftbl_active_dialog;
		if (!ad) return;

		_collectValues(ad.dialog, ad.field, ad.rowIdx, ad.columns, ad.uid);

		ad.dialog.$wrapper.off("hide.bs.modal");
		ad.dialog.hide();
	};

	window._ftbl_dlg_insert = function (field, rowIdx, where, uid) {
		const ad = window._ftbl_active_dialog;
		if (ad) {
			_collectValues(ad.dialog, field, rowIdx, ad.columns, ad.uid);
			ad.dialog.$wrapper.off("hide.bs.modal");
			ad.dialog.hide();
		}
		const state = window._ftbl_state[field];
		if (!state) return;
		const newRow = {
			doctype: state.childDoctype,
			parent: frm.doc.name,
			parentfield: field,
			parenttype: frm.doctype,
		};
		const insertAt = where === "above" ? rowIdx : rowIdx + 1;
		state.rows.splice(insertAt, 0, newRow);
		rebuildFtblBody(field);
		openRowDialog(field, insertAt);
	};

	window._ftbl_dlg_duplicate = function (field, rowIdx, uid) {
		const ad = window._ftbl_active_dialog;
		if (ad) {
			_collectValues(ad.dialog, field, rowIdx, ad.columns, ad.uid);
			ad.dialog.$wrapper.off("hide.bs.modal");
			ad.dialog.hide();
		}
		const state = window._ftbl_state[field];
		if (!state) return;
		const copy = { ...state.rows[rowIdx] };
		delete copy.name;
		state.rows.splice(rowIdx + 1, 0, copy);
		rebuildFtblBody(field);
		openRowDialog(field, rowIdx + 1);
	};

	// ─── Rebuild tbody from state ─────────────────────────────────────────────────
	function rebuildFtblBody(field) {
		const state = window._ftbl_state[field];
		if (!state) return;
		const tbody = document.getElementById(`tbody-${field}`);
		if (!tbody) return;
		tbody.innerHTML = state.rows.length
			? state.rows.map((row, i) => buildFtblRow(field, state.previewCols, row, i)).join("")
			: `<div class="ftbl-empty" style="padding:20px 16px;text-align:center;color:var(--color-text-tertiary,#aaa);font-size:13px;">No rows. Click "Add Row" to begin.</div>`;
		_ftbl_updateCount(field);
		_ftbl_rowCheckChange(field);
	}

	// ─── Build one preview row (checkbox + No. + 4 cols + edit icon) ─────────────
	function buildFtblRow(field, previewCols, row, idx) {
		const rowId = row.name || `new-${field}-${idx}`;
		const colCells = previewCols
			.map(
				(col) => `
<div class="ftbl-cell" onclick="window._ftbl_openRowDialog('${field}',${idx})"
	style="padding:6px 10px;display:flex;align-items:center;min-height:34px;border-right:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.07));font-size:13px;color:var(--color-text-primary);cursor:pointer;overflow:hidden;">
	<span style="overflow:hidden;white-space:nowrap;text-overflow:ellipsis;max-width:100%;">${formatCellDisplay(col, row[col.fieldname])}</span>
</div>`,
			)
			.join("");

		return `
<div class="ftbl-row" data-rowid="${rowId}" data-field="${field}" data-idx="${idx}"
	style="display:grid;grid-template-columns:32px 44px ${previewCols.map(() => "1fr").join(" ")} 38px;border-bottom:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.08));transition:background 0.1s;"
	onmouseenter="this.style.background='var(--color-background-secondary,#F3F3F3)'"
	onmouseleave="this.style.background=''">
	<div style="padding:6px 8px;display:flex;align-items:center;justify-content:center;">
		<input type="checkbox" class="ftbl-chk" data-field="${field}" data-rowid="${rowId}"
			onchange="window._ftbl_rowCheckChange('${field}')"
			onclick="event.stopPropagation()"
			style="width:13px;height:13px;accent-color:#378add;cursor:pointer;" />
	</div>
	<div onclick="window._ftbl_openRowDialog('${field}',${idx})"
		style="padding:6px 8px;display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--color-text-secondary,#888);font-weight:500;cursor:pointer;">
		${idx + 1}
	</div>
	${colCells}
	<div style="padding:6px 6px;display:flex;align-items:center;justify-content:center;">
		<button onclick="event.stopPropagation();window._ftbl_openRowDialog('${field}',${idx})"
			style="width:24px;height:24px;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.2));background:transparent;color:var(--color-text-secondary,#666);cursor:pointer;border-radius:5px;font-size:12px;display:inline-flex;align-items:center;justify-content:center;"
			title="Edit row">✏</button>
	</div>
</div>`;
	}

	// ─── Build the full table widget HTML ─────────────────────────────────────────
	function buildFtblHTML(field, rows, previewCols) {
		const colHeaders = previewCols
			.map(
				(col) => `
<div style="padding:7px 10px;font-size:11px;font-weight:500;color:var(--color-text-secondary,#6b6b6b);text-transform:uppercase;letter-spacing:0.04em;border-right:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.1));">
	${col.label || frappe.model.unscrub(col.fieldname)}${col.reqd ? '<span style="color:#e24b4a;margin-left:2px;">*</span>' : ""}
</div>`,
			)
			.join("");

		const bodyHtml = rows.length
			? rows.map((row, i) => buildFtblRow(field, previewCols, row, i)).join("")
			: `<div class="ftbl-empty" style="padding:20px 16px;text-align:center;color:var(--color-text-tertiary,#aaa);font-size:13px;">No rows. Click "Add Row" to begin.</div>`;

		return `
<div class="frappe-child-table" data-field="${field}"
	style="border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.2));border-radius:var(--border-radius-md,8px);overflow:hidden;margin-top:4px;">

	<div style="display:grid;grid-template-columns:32px 44px ${previewCols.map(() => "1fr").join(" ")} 38px;background:var(--color-background-secondary,#F3F3F3);border-bottom:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.12));">
		<div style="padding:7px 8px;display:flex;align-items:center;justify-content:center;">
			<input type="checkbox" id="chk-all-${field}" onchange="window._ftbl_toggleAll('${field}',this)"
				style="width:13px;height:13px;accent-color:#378add;cursor:pointer;" />
		</div>
		<div style="padding:7px 10px;font-size:11px;font-weight:500;color:var(--color-text-secondary,#6b6b6b);text-transform:uppercase;letter-spacing:0.04em;">No.</div>
		${colHeaders}
		<div style="padding:7px 8px;"></div>
	</div>

	<div id="tbody-${field}" class="ftbl-body" data-field="${field}">${bodyHtml}</div>

	<div style="padding:6px 10px;border-top:0.5px solid var(--color-border-tertiary,rgba(0,0,0,0.1));background:var(--color-background-secondary,#F3F3F3);display:flex;align-items:center;gap:6px;">
		<button id="ftbl-del-sel-${field}" onclick="window._ftbl_deleteSelected('${field}')"
			style="display:none;align-items:center;gap:5px;height:28px;padding:0 14px;background:#e24b4a;color:#fff;border:none;border-radius:5px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;">
			Delete
		</button>
		<button onclick="window._ftbl_addRow('${field}')"
			style="height:28px;padding:0 14px;background:none;border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.25));color:var(--color-text-primary);border-radius:5px;font-size:12px;font-weight:500;cursor:pointer;font-family:inherit;">
			Add Row
		</button>
		<span id="row-count-${field}" style="margin-left:auto;font-size:12px;color:var(--color-text-secondary,#6b6b6b);">
			${rows.length ? rows.length + " row" + (rows.length !== 1 ? "s" : "") : ""}
		</span>
	</div>
</div>`;
	}

	// ─── Global controller ────────────────────────────────────────────────────────
	window._ftbl_state = {};
	window._ftbl_active_dialog = null;

	window._ftbl_openRowDialog = function (field, rowIdx) {
		openRowDialog(field, rowIdx);
	};

	window._ftbl_addRow = function (field) {
		const state = window._ftbl_state[field];
		if (!state) return;
		const newRow = {
			doctype: state.childDoctype,
			parent: frm.doc.name,
			parentfield: field,
			parenttype: frm.doctype,
		};
		state.rows.push(newRow);
		rebuildFtblBody(field);
		_lead_detail_dirty = true;
		frm.dirty();
		openRowDialog(field, state.rows.length - 1);
	};

	window._ftbl_toggleAll = function (field, el) {
		document
			.querySelectorAll(`.ftbl-chk[data-field="${field}"]`)
			.forEach((chk) => (chk.checked = el.checked));
		_ftbl_rowCheckChange(field);
	};

	window._ftbl_rowCheckChange = function (field) {
		_ftbl_rowCheckChange(field);
	};

	function _ftbl_rowCheckChange(field) {
		const all = document.querySelectorAll(`.ftbl-chk[data-field="${field}"]`);
		const checked = document.querySelectorAll(`.ftbl-chk[data-field="${field}"]:checked`);
		const allChk = document.getElementById(`chk-all-${field}`);
		const delBtn = document.getElementById(`ftbl-del-sel-${field}`);
		if (allChk) {
			allChk.checked = checked.length > 0 && checked.length === all.length;
			allChk.indeterminate = checked.length > 0 && checked.length < all.length;
		}
		if (delBtn) delBtn.style.display = checked.length > 0 ? "inline-flex" : "none";
	}

	window._ftbl_deleteSelected = function (field) {
		const toDelete = [
			...document.querySelectorAll(`.ftbl-chk[data-field="${field}"]:checked`),
		].map((el) => el.dataset.rowid);
		const state = window._ftbl_state[field];
		if (!state) return;
		state.rows = state.rows.filter(
			(r, i) => !toDelete.includes(r.name || `new-${field}-${i}`),
		);
		rebuildFtblBody(field);
	};

	function _ftbl_updateCount(field) {
		const state = window._ftbl_state[field];
		const el = document.getElementById(`row-count-${field}`);
		if (el && state)
			el.textContent = state.rows.length
				? `${state.rows.length} row${state.rows.length !== 1 ? "s" : ""}`
				: "";
	}

	// ─── Regular (non-table) input HTML ──────────────────────────────────────────
	function getInputHTML(fieldtype, value, field, meta_field) {
		value = value ?? "";
		const label = meta_field.label || frappe.model.unscrub(field);
		const cls = "form-control input-with-feedback dynamic-input";

		if (_lead_form_locked) {
			if (value === "" || value === null || value === undefined) return "__HIDE__";

			const roBox = `
        padding: 6px 10px;
        min-height: 32px;
        background: var(--color-background-secondary, #f3f3f3);
        border: 0.5px solid var(--color-border-secondary, rgba(0,0,0,0.2));
        border-radius: var(--border-radius-md, 6px);
        font-size: 13px;
        color: var(--color-text-primary);
        line-height: 1.5;
        display: flex;
        align-items: center;
        word-break: break-word;
    `;

			const escape = (v) =>
				frappe.utils?.escape_html ? frappe.utils.escape_html(String(v)) : String(v);

			if (fieldtype === "Link") {
				return `
<div style="${roBox}">
    <a href="/app/file/${value}" target="_blank"
        style="color: var(--color-text-info, #1a73e8); text-decoration: none; font-size: 13px;">
        📎 View File
    </a>
</div>`;
			}

			if (fieldtype === "Check") {
				return `
<div style="${roBox}">
    <span style="color: var(--color-text-secondary); font-size: 13px;">
        ${value ? "Yes" : "No"}
    </span>
</div>`;
			}

			if (isMonthYearField(field)) {
				return `<div style="${roBox}">${escape(toMonthYear(String(value)))}</div>`;
			}

			if (fieldtype === "Date") {
				return `<div style="${roBox}">${escape(value.split(" ")[0] || "")}</div>`;
			}

			if (["Text", "Small Text", "Long Text"].includes(fieldtype)) {
				return `
<div style="
    padding: 8px 10px;
    background: var(--color-background-secondary, #f3f3f3);
    border: 0.5px solid var(--color-border-secondary, rgba(0,0,0,0.2));
    border-radius: var(--border-radius-md, 6px);
    font-size: 13px;
    color: var(--color-text-primary);
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    min-height: 60px;
">${escape(value)}</div>`;
			}

			if (fieldtype === "Table") {
				const child_doctype = meta_field.options;
				if (!child_doctype) return "__HIDE__";
				const child_meta = frappe.get_meta(child_doctype);
				if (!child_meta?.fields) return "__HIDE__";
				const allColumns = getTableColumns(child_meta);
				const previewCols = allColumns.slice(0, 4);
				const rows = Array.isArray(value) ? value : [];
				if (!rows.length) return "__HIDE__";

				const safeField = field.replace(/[^a-zA-Z0-9_]/g, "_");
				window._ro_table_state = window._ro_table_state || {};
				window._ro_table_state[safeField] = { rows, allColumns };

				const colHeaders = previewCols
					.map(
						(col) => `
<div style="
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 500;
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-right: 0.5px solid var(--color-border-tertiary, rgba(0,0,0,0.1));
">${col.label || frappe.model.unscrub(col.fieldname)}</div>`,
					)
					.join("");

				const bodyRows = rows
					.map((row, i) => {
						const cells = previewCols
							.map(
								(col) => `
<div style="
    padding: 6px 10px;
    font-size: 13px;
    color: var(--color-text-primary);
    border-right: 0.5px solid var(--color-border-tertiary, rgba(0,0,0,0.07));
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
">${formatCellDisplay(col, row[col.fieldname])}</div>`,
							)
							.join("");

						return `
<div onclick="window._ftbl_ro_view_row('${safeField}', ${i})"
    style="
        display: grid;
        grid-template-columns: 36px ${previewCols.map(() => "1fr").join(" ")} 38px;
        border-bottom: 0.5px solid var(--color-border-tertiary, rgba(0,0,0,0.08));
        background: var(--color-background-primary);
        cursor: pointer;
        pointer-events: all !important;
    "
    onmouseenter="this.style.background='var(--color-background-secondary,#f3f3f3)'"
    onmouseleave="this.style.background='var(--color-background-primary)'">
    <div style="
        padding: 6px 8px;
        font-size: 12px;
        color: var(--color-text-secondary);
        display: flex;
        align-items: center;
        justify-content: center;
        border-right: 0.5px solid var(--color-border-tertiary, rgba(0,0,0,0.07));
    ">${i + 1}</div>
    ${cells}
    <div style="padding:6px;display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--color-text-secondary);">👁</div>
</div>`;
					})
					.join("");

				return `
<div style="
    border: 0.5px solid var(--color-border-secondary, rgba(0,0,0,0.2));
    border-radius: var(--border-radius-md, 6px);
    overflow: hidden;
    margin-top: 4px;
">
    <div style="
        display: grid;
        grid-template-columns: 36px ${previewCols.map(() => "1fr").join(" ")} 38px;
        background: var(--color-background-secondary, #f3f3f3);
        border-bottom: 0.5px solid var(--color-border-tertiary, rgba(0,0,0,0.12));
    ">
        <div style="
            padding: 7px 8px;
            font-size: 11px;
            font-weight: 500;
            color: var(--color-text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            border-right: 0.5px solid var(--color-border-tertiary, rgba(0,0,0,0.1));
        ">No.</div>
        ${colHeaders}
        <div style="padding: 7px 8px;"></div>
    </div>
    ${bodyRows}
</div>`;
			}

			return `<div style="${roBox}">${escape(String(value))}</div>`;
		}

		// ── EDITABLE MODE ─────────────────────────────────────────────────────────
		if (field.toLowerCase() === "availability_for_interview")
			return `<input type="text" value="${value}" data-field="${field}" data-override="availability" class="${cls}" placeholder="Exp: Mon - Fri, 9:30 AM - 10:00 PM" />`;
		if (isEmailField(field))
			return `<input type="email" value="${value}" data-field="${field}" data-override="email" class="${cls}" placeholder=" ${label}" />`;
		if (field.toLowerCase().includes("ssn")) {
			return `<input type="text"
        value="${value}"
        data-field="${field}"
        data-override="ssn"
        maxlength="4"
        class="${cls}"
        placeholder="Enter last 4 digits" />`;
		}
		if (isMonthYearField(field))
			return `<input type="text" value="${toMonthYear(value)}" data-field="${field}" data-override="month-year" class="${cls}" placeholder="MM-YYYY" maxlength="7" />`;
		if (isPhoneField(field)) {
			value = meta_field.default;
			return `<input type="tel" value="${value}" data-field="${field}" data-override="phone" class="${cls}" placeholder="Exp: +1xxxxxxxxxx Or +91xxxxxxxxxx" />`;
		}
		if (fieldtype === "Link") {
			const can_remove_file = frm.doc.status === "Lead" || "Open";

			let current_display_html = value
				? `
		<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
			<a href="/app/file/${value}" target="_blank"
				style="color:#260fea;font-weight:500;text-decoration:none;">
				📎 View Current File
			</a>

			${
				can_remove_file
					? `<button
							type="button"
							class="fg-remove-file"
							data-field="${field}"
							title="Remove File"
							style="
								border:none;
								background:transparent;
								color:#dc2626;
								cursor:pointer;
								font-size:16px;
								padding:0;
								line-height:1;
							">
							✕
					   </button>`
					: ""
			}
		</div>`
				: `<span style="color:var(--color-text-tertiary);font-style:italic;">No file</span>`;

			return `
		<div style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap;">
			<div style="flex:1;min-width:180px;">
				<div style="font-size:11px;color:#6b6b6b;margin-bottom:4px;">Current</div>
				<div style="padding:6px 8px;border:1px solid #ddd;border-radius:6px;background:#f9fafb;min-height:32px;display:flex;align-items:center;">
					${current_display_html}
				</div>
			</div>

			<div style="flex:1;min-width:180px;">
				<div style="font-size:11px;color:#6b6b6b;margin-bottom:4px;">Upload New</div>
				<div style="display:flex;flex-direction:column;gap:6px;">
					<input type="file" class="dynamic-input fg-file-input" data-field="${field}" style="font-size:12px;" />
					<div class="fg-file-name" data-field="${field}" style="font-size:11px;color:#667085;"></div>
					<input type="hidden" class="dynamic-input fg-file-url" data-field="${field}" value="${frappe.utils.escape_html(value || "")}" />
				</div>
			</div>
		</div>`;
		}
		switch (fieldtype) {
			case "Date":
				return `<input type="date" value="${value.split(" ")[0] || ""}" data-field="${field}" class="${cls}" />`;
			case "Int":
			case "Float":
			case "Currency":
				return `<input type="text" value="${value}" data-field="${field}" class="${cls}" placeholder="${label}" />`;
			case "Check":
				return `<div class="checkbox" style="margin-top:6px;"><input type="checkbox" data-field="${field}" class="dynamic-input" ${value ? "checked" : ""} /></div>`;
			case "Email":
				return `<input type="email" value="${value}" data-field="${field}" data-override="email" class="${cls}" placeholder="${label}" />`;
			case "Select": {
				const opts = (meta_field.options || "").split("\n").filter(Boolean);
				return `<select data-field="${field}" class="form-control dynamic-input">
                <option value="">Select ${label}</option>
                ${opts.map((o) => `<option value="${o}" ${o === value ? "selected" : ""}>${o}</option>`).join("")}
            </select>`;
			}
			case "Table": {
				const child_doctype = meta_field.options;
				if (!child_doctype)
					return `<div style="color:red;">No Child Doctype configured</div>`;
				const child_meta = frappe.get_meta(child_doctype);
				if (!child_meta?.fields)
					return `<div style="color:orange;">Child meta not loaded for: ${child_doctype}</div>`;
				const allColumns = getTableColumns(child_meta);
				const previewCols = allColumns.slice(0, 4);
				const rows = Array.isArray(value) ? value : [];
				window._ftbl_state[field] = {
					rows: [...rows],
					columns: allColumns,
					previewCols,
					childDoctype: child_doctype,
				};
				return buildFtblHTML(field, rows, previewCols);
			}
			default:
				return `<input type="text" value="${value}" data-field="${field}" class="${cls}" placeholder=" ${label}" />`;
		}
	}

	// ─── Validation ───────────────────────────────────────────────────────────────
	function isValidAvailability(value) {
		if (!value) return false;
		const pattern =
			/^\s*[A-Za-z]{2,9}(\s*[–\-]\s*[A-Za-z]{2,9})?\s*,\s*\d{1,2}:\d{2}\s*(AM|PM)\s*[–\-]\s*\d{1,2}:\d{2}\s*(AM|PM)\s*$/i;
		return pattern.test(value.trim());
	}

	function validateSingleInput(input, field_map) {
		const field = input.dataset.field;
		const meta = field_map[field];
		if (!meta || meta.fieldtype === "Table" || input.type === "checkbox") return;
		clearError(input);
		const value = input.value.trim();
		const label = meta.label || frappe.model.unscrub(field);
		const override = input.dataset.override;
		if (meta.reqd && !value) return markInvalid(input, `${label} is required`);
		if (override === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))
			return markInvalid(input, `${label} must be a valid email address`);
		if (override === "month-year" && value && !isValidMonthYear(value))
			return markInvalid(input, `${label} must be in MM-YYYY format`);
		if (override === "phone" && value) {
			// Sanitize: Replace ( ) - and spaces with an empty string
			const sanitized_phone = value.replace(/[()-\s]/g, "");

			// Your original strict regex (+countrycode followed by 9 to 14 digits)
			const phone_regex = /^\+[1-9]\d{9,14}$/;

			// Validate against the sanitized version
			if (!phone_regex.test(sanitized_phone)) {
				return markInvalid(input, `${label} must include country code`);
			}
		}
		if (["Int", "Float", "Currency"].includes(meta.fieldtype) && value && isNaN(value))
			return markInvalid(input, `${label} must be a number`);
		if (meta.fieldtype === "Date" && value && isNaN(Date.parse(value)))
			return markInvalid(input, `${label} must be a valid date`);
		if (override === "ssn") {
			if (value && !/^\d{4}$/.test(value)) {
				return markInvalid(input, `${label} must be exactly 4 digits`);
			}
		}
		if (override === "availability" && value && !isValidAvailability(value))
			return markInvalid(input, `Must be in format: Mon - Fri, 9:30 AM - 10:00 PM`);
	}

	function validateWithMeta(field_map) {
		let isValid = true,
			firstInvalid = null;
		const fail = (input, msg) => {
			markInvalid(input, msg);
			isValid = false;
			if (!firstInvalid) firstInvalid = input;
		};

		document.querySelectorAll(".dynamic-input").forEach((input) => {
			const field = input.dataset.field;
			const meta = field_map[field];
			if (!meta || meta.fieldtype === "Table") return;
			clearError(input);
			const value = input.type === "checkbox" ? (input.checked ? 1 : 0) : input.value;
			const label = meta.label || frappe.model.unscrub(field);
			const override = input.dataset.override;
			if (meta.reqd && !value && input.type !== "checkbox")
				return fail(input, `${label} is required`);
			if (override === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))
				return fail(input, `${label} must be a valid email address`);
			if (override === "month-year" && value && !isValidMonthYear(value))
				return fail(input, `${label} must be in MM-YYYY format`);
			if (override === "phone" && value) {
				// Sanitize: Replace ( ) - and spaces with an empty string
				const sanitized_phone = value.replace(/[()-\s]/g, "");

				// Your original strict regex (+countrycode followed by 9 to 14 digits)
				const phone_regex = /^\+[1-9]\d{9,14}$/;

				// Validate against the sanitized version
				if (!phone_regex.test(sanitized_phone)) {
					return fail(input, `${label} must include country code`);
				}
			}
			if (
				meta.fieldtype === "Select" &&
				value &&
				!(meta.options || "").split("\n").includes(value)
			)
				return fail(input, `${label} must be a valid option`);
			if (["Int", "Float", "Currency"].includes(meta.fieldtype) && value && isNaN(value))
				return fail(input, `${label} must be a number`);
			if (meta.fieldtype === "Date" && value && isNaN(Date.parse(value)))
				return fail(input, `${label} must be a valid date`);
			if (override === "ssn" && value && !/^\d{4}$/.test(value)) {
				return fail(input, `${label} must be exactly 4 digits`);
			}
			if (override === "availability" && value && !isValidAvailability(value))
				return fail(input, `Must be in format: Mon - Fri, 9:30 AM - 10:00 PM`);
		});

		Object.entries(window._ftbl_state).forEach(([field, state]) => {
			state.rows.forEach((row, rowIdx) => {
				state.columns.forEach((col) => {
					if (!col.reqd || col.fieldtype === "Check") return;
					const strVal = (row[col.fieldname] ?? "").toString().trim();
					if (!strVal) {
						isValid = false;
						const rowId = row.name || `new-${field}-${rowIdx}`;
						const cellEl = document.querySelector(
							`.ftbl-cell[data-field="${field}"][data-rowid="${rowId}"][data-child="${col.fieldname}"]`,
						);
						if (cellEl) cellEl.style.outline = "1.5px solid #e24b4a";
					}
				});
			});
		});

		if (firstInvalid) {
			firstInvalid.focus();
			firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
		}
		return isValid;
	}

	// ─── Data collection ─────────────────────────────────────────────────────────
	function collectFormData(field_map) {
		const data = {};

		document.querySelectorAll(".dynamic-input").forEach((input) => {
			const meta = field_map[input.dataset.field];
			if (!meta || meta.fieldtype === "Table") return;
			let val = input.type === "checkbox" ? (input.checked ? 1 : 0) : input.value;

			const override = input.dataset.override;

			if (override === "ssn" && val) {
				val = parseInt(val, 10);
			}
			if (input.dataset.override === "month-year" && val) val = fromMonthYear(val);
			data[input.dataset.field] = val;
		});

		Object.entries(window._ftbl_state).forEach(([field, state]) => {
			data[field] = state.rows
				.filter((r) =>
					Object.keys(r).some(
						(k) =>
							!["doctype", "parent", "parentfield", "parenttype", "name"].includes(
								k,
							) &&
							r[k] !== "" &&
							r[k] !== null &&
							r[k] !== undefined,
					),
				)
				.map((r) => ({ ...r }));
		});

		return data;
	}

	function attachLiveValidation(field_map) {
		document.querySelectorAll(".dynamic-input").forEach((input) => {
			input.addEventListener("input", () => clearError(input));
			input.addEventListener("blur", () => validateSingleInput(input, field_map));
		});
	}

	// ─── Main entry point ─────────────────────────────────────────────────────────
	getDepartmentFields("Lead").then(async (fields) => {
		frm.set_df_property("lead_detail", "options", "");

		const res = await frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Lead Detail Form",
				fields: ["name"],
				filters: [
					["Doctype Reference", "reference_doctype", "=", "Lead"],
					["Doctype Reference", "reference_person", "=", frm.doc.name],
				],
				limit_page_length: 1,
			},
		});

		if (!res.message.length) {
			return;
		}

		const docname = res.message[0].name;

		await frappe.model.with_doctype("Lead Detail Form");

		const [doc] = await Promise.all([frappe.db.get_doc("Lead Detail Form", docname)]);

		const meta = frappe.get_meta("Lead Detail Form");

		await Promise.all(
			meta.fields
				.filter((f) => f.fieldtype === "Table" && f.options)
				.map((f) => frappe.model.with_doctype(f.options)),
		);

		const field_map = Object.fromEntries(meta.fields.map((f) => [f.fieldname, f]));

		window._ftbl_state = {};

		const formFields = fields
			.map((field) => {
				const meta_field = field_map[field];
				if (!meta_field) return "";
				const label = meta_field.label || frappe.model.unscrub(field);
				const isFullWidth = ["Table", "Text Editor", "Long Text", "HTML"].includes(
					meta_field.fieldtype,
				);
				const default_value = meta_field.default_value;
				const inputHtml = getInputHTML(
					meta_field.fieldtype,
					doc[field],
					field,
					meta_field,
				);

				if (inputHtml === "__HIDE__") return "";

				return `
<div style="width:${isFullWidth ? "100%" : "calc(50% - 8px)"};min-width:${isFullWidth ? "100%" : "250px"};">
    <div class="frappe-control">
        <div class="control-label" style="margin-bottom:6px;">
            ${label}${meta_field.reqd && !_lead_form_locked ? '<span style="color:red;">*</span>' : ""}
        </div>
        <div class="control-input">
            ${inputHtml}
        </div>
    </div>
</div>`;
			})
			.join("");

		const html = `
<div class="form-layout">
	<div class="form-section">
		<div class="section-head">Lead Detail Form</div>
		<div class="section-body">
			<div style="display:flex;flex-wrap:wrap;gap:16px;">${formFields}</div>
			
		</div>
	</div>
</div>`;

		frm.set_df_property("lead_detail", "options", html);

		async function saveLeadDetailForm() {
			if (!_lead_detail_dirty) return { saved: false, valid: true };

			if (!validateWithMeta(field_map)) {
				frappe.msgprint("Enter Valid Values in Form");
				return { saved: false, valid: false };
			}
			let data = collectFormData(field_map);

			for (const field in window._temp_files || {}) {
				const file = window._temp_files[field];
				const formData = new FormData();
				formData.append("file", file);
				formData.append("is_private", 0);
				try {
					const res = await $.ajax({
						url: "/api/method/upload_file",
						type: "POST",
						data: formData,
						processData: false,
						contentType: false,
						headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
					});
					if (res.message) {
						const file_id = res.message.name;
						data[field] = file_id;
						$(`.fg-file-url[data-field="${field}"]`).val(file_id);
					}
				} catch (err) {
					frappe.msgprint(`File upload failed for ${field}`);
					return { saved: false, valid: false };
				}
			}
			window._temp_files = {};

			try {
				const res = await frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "Lead Detail Form",
						filters: [
							["Doctype Reference", "reference_doctype", "=", "Lead"],
							["Doctype Reference", "reference_person", "=", frm.doc.name],
						],
						fields: ["name"],
						limit_page_length: 1,
					},
				});

				if (!res.message || !res.message.length) {
					frappe.msgprint("Lead Detail Form not found");
					return { saved: false, valid: false };
				}

				const latest_doc = await frappe.db.get_doc(
					"Lead Detail Form",
					res.message[0].name,
				);
				Object.keys(data).forEach((key) => (latest_doc[key] = data[key]));

				await frappe.call({
					method: "frappe.client.save",
					args: { doc: latest_doc },
				});

				_lead_detail_dirty = false;
				return { saved: true, valid: true };
			} catch (err) {
				frappe.msgprint("An error occurred while saving. Please try again.");
				return { saved: false, valid: false };
			}
		}

		frm._lead_detail_hook = false;
		if (!frm._lead_detail_hook) {
			frm._lead_detail_hook = true;
			frappe.ui.form.on(frm.doctype, {
				before_save: async (f) => {
					if (f.doc.name !== frm.doc.name) return;

					isSaving = true;

					try {
						const result = await saveLeadDetailForm();

						if (!result.valid) {
							frappe.validated = false;
							return;
						}

						if (f.doc.status === "Opportunity") {
							const exists = await frappe.db.exists("Opportunity", {
								opportunity_from_lead: f.doc.name,
							});
							if (!exists) {
								frappe.throw("First create an Opportunity for this Lead");
							}
						}
					} catch (err) {
						frappe.validated = false;
					} finally {
						isSaving = false;
					}
				},
			});
		}

		window._temp_files = window._temp_files || {};

		$(document).off("change", ".fg-file-input");
		$(document).off("input change", ".dynamic-input, .ftbl-chk");

		$(document).on("input change", ".dynamic-input, .ftbl-chk", function () {
			_lead_detail_dirty = true;
			frm.dirty();
		});

		$(document).on("change", ".fg-file-input", function () {
			const file = this.files[0];
			const field = $(this).data("field");
			if (!file) return;
			window._temp_files[field] = file;
			_lead_detail_dirty = true;
			frm.dirty();
			$(`.fg-file-name[data-field="${field}"]`).html(
				`<span style="color:#260fea;">${file.name}</span>`,
			);
		});

		$(document).on("click", ".fg-remove-file", function () {
			const field = $(this).data("field");
			const $button = $(this);
			frappe.confirm(__("Are you sure you want to remove this file?"), () => {
				frappe.call({
					method: "verp_staffing.crm.doctype.lead.lead.remove_attachment",
					args: {
						// doctype: frm.doctype,
						docname: frm.doc.lead_details,
						fieldname: field,
					},
					callback: (r) => {
						if (r.message?.status !== "success") return;

						$(document).find(`.fg-file-url[data-field="${field}"]`).val("");

						const currentBox = $button.closest(
							'[style*="justify-content:space-between"]',
						);

						currentBox.html(
							'<span style="color:var(--color-text-tertiary);font-style:italic;">No file</span>',
						);

						frappe.show_alert({
							message: __("File removed"),
							indicator: "green",
						});
					},
				});
			});
		});
		attachLiveValidation(field_map);
	});
}

function lockLeadDetailForm() {
	const wrapper = document.querySelector('[data-fieldname="lead_detail"]');

	if (!wrapper) return;

	wrapper.querySelectorAll("*").forEach((el) => {
		if (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA") {
			el.disabled = true;
			el.readOnly = true;
		}

		if (el.tagName === "BUTTON") {
			el.disabled = true;
		}

		if (el.tagName !== "A" && !el.hasAttribute("onclick")) {
			el.style.pointerEvents = "none";
		} else {
			el.style.pointerEvents = "all";
		}
	});

	wrapper.style.opacity = "0.8";
}

// ─── Read-only row viewer dialog ──────────────────────────────────────────────
window._ftbl_ro_view_row = function (safeField, rowIdx) {
	const state = window._ro_table_state && window._ro_table_state[safeField];
	if (!state) return;
	const row = state.rows[rowIdx];
	const allColumns = state.allColumns;

	const fieldsHtml = allColumns
		.map((col) => {
			const val = row[col.fieldname];
			const label = col.label || frappe.model.unscrub(col.fieldname);
			const isWide = ["Text", "Small Text", "Long Text"].includes(col.fieldtype);

			let displayVal;
			if (val === null || val === undefined || val === "") {
				displayVal = `<span style="color:var(--color-text-tertiary,#bbb);font-style:italic;">—</span>`;
			} else if (col.fieldtype === "Check") {
				displayVal = val ? "Yes" : "No";
			} else if (["start_date", "end_date", "entry_date"].includes(col.fieldname)) {
				const parts = String(val).split("-");
				displayVal = parts.length >= 2 ? `${parts[1]}-${parts[0]}` : String(val);
			} else {
				const escaped = frappe.utils?.escape_html
					? frappe.utils.escape_html(String(val))
					: String(val);
				displayVal = escaped;
			}

			const valueHtml = ["Text", "Small Text", "Long Text"].includes(col.fieldtype)
				? `<div style="padding:8px 10px;background:var(--color-background-secondary,#f3f3f3);border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.2));border-radius:6px;font-size:13px;color:var(--color-text-primary);line-height:1.6;white-space:pre-wrap;word-break:break-word;min-height:48px;">${displayVal}</div>`
				: `<div style="padding:6px 10px;min-height:32px;background:var(--color-background-secondary,#f3f3f3);border:0.5px solid var(--color-border-secondary,rgba(0,0,0,0.2));border-radius:6px;font-size:13px;color:var(--color-text-primary);display:flex;align-items:center;">${displayVal}</div>`;

			return `
<div style="width:${isWide ? "100%" : "calc(50% - 8px)"};min-width:${isWide ? "100%" : "200px"};padding:0 8px;margin-bottom:12px;">
    <div style="font-size:12px;font-weight:500;color:var(--color-text-secondary,#6b6b6b);margin-bottom:5px;">${label}</div>
    ${valueHtml}
</div>`;
		})
		.join("");

	const bodyHtml = `
<div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <div style="font-size:15px;font-weight:600;color:var(--color-text-primary);">Row #${rowIdx + 1} — Details</div>
        <button onclick="window._ftbl_ro_close_dialog()"
            style="width:32px;height:32px;border:none;background:transparent;color:#667085;border-radius:8px;cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;"
            onmouseenter="this.style.background='#f2f4f7'" onmouseleave="this.style.background='transparent'">×</button>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:4px;margin:0 -8px;">
        ${fieldsHtml}
    </div>
</div>`;

	const dialog = new frappe.ui.Dialog({
		title: " ",
		fields: [{ fieldtype: "HTML", fieldname: "ro_row_view", options: bodyHtml }],
		size: "large",
	});
	dialog.$wrapper.find(".modal-header").hide();
	dialog.$wrapper.find(".modal-body").css({ "padding-top": "20px", "padding-bottom": "10px" });
	dialog.$wrapper.find(".modal-footer").hide();
	dialog.$wrapper
		.find(".modal-dialog")
		.css({ display: "flex", alignItems: "center", minHeight: "100vh", margin: "0 auto" });

	window._ftbl_ro_active_dialog = dialog;
	dialog.show();
};

window._ftbl_ro_close_dialog = function () {
	if (window._ftbl_ro_active_dialog) {
		window._ftbl_ro_active_dialog.hide();
		window._ftbl_ro_active_dialog = null;
	}
};

function watchAndLockLeadDetail() {
	const target = document.querySelector('[data-fieldname="lead_detail"]');

	if (!target) return;

	const observer = new MutationObserver(() => {
		lockLeadDetailForm();
	});

	observer.observe(target, {
		childList: true,
		subtree: true,
	});

	lockLeadDetailForm();
}

function open_create_opportunity_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Create Opportunity from Lead"),
		fields: [
			{
				fieldname: "manual_assign",
				fieldtype: "Check",
				label: "Want to assign Opportunity Owner Manually?",
			},
			{
				fieldname: "opportunity_owner",
				label: "Opportunity Owner",
				fieldtype: "Link",
				options: "Employee",
				depends_on: "eval:doc.manual_assign == 1",
				mandatory_depends_on: "eval:doc.manual_assign == 1",
				get_query() {
					return { filters: { department: "Sales" } };
				},
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			dialog.hide();
			if (values.manual_assign) {
				create_opportunity(frm, values.opportunity_owner);
			} else {
				frappe.call({
					method: "verp_staffing.crm.api.auto_assign.get_auto_assign_employee",
					args: {
						department: "Sales",
						target_doctype: "Opportunity",
						owner_field: "opportunity_owner",
					},
					callback(r) {
						if (r.message) {
							create_opportunity(frm, r.message);
						}
					},
				});
			}
		},
	});
	dialog.show();
}

function create_opportunity(frm, owner) {
	frappe.call({
		method: "verp_staffing.crm.doctype.lead.lead.create_opportunity_from_lead",
		args: {
			lead: frm.doc.name,
			owner: owner,
		},
		callback(response) {
			if (response.message) {
				frappe.msgprint({
					title: __("Success"),
					message: __("Opportunity Created: {0}", [response.message]),
					indicator: "green",
				});

				frm.reload_doc();
			}
		},
	});
}
