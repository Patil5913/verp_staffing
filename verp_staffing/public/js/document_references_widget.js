// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

// Fieldtypes that Frappe's native grid renders as a plain single-line
const GRID_COLLAPSE_TO_DATA = [
	"Small Text",
	"Text",
	"Long Text",
	"Text Editor",
	"Code",
	"Markdown Editor",
	"HTML Editor",
];

window.verp_staffing = window.verp_staffing || {};

function ensure_drdocref_styles() {
	if (document.getElementById("drdocref-widget-styles")) return;
	$("<style>", {
		id: "drdocref-widget-styles",
		text: `
			.drdocref-widget .drdocref-col { box-sizing: border-box; min-width: 0; overflow: hidden; }
			.drdocref-widget .drdocref-row-selected { background-color: var(--control-bg); }
		`,
	}).appendTo("head");
}

window.verp_staffing.render_document_references_table = function (frm, opts) {
	const {
		fieldname,
		wrapper_field,
		show_fields,
		locked_statuses = ["Completed"],
		status_field = "status",
	} = opts;

	if (!Array.isArray(show_fields) || !show_fields.length) {
		console.error(
			`render_document_references_table: "show_fields" must be a non-empty array, got:`,
			show_fields,
		);
		return;
	}

	const child_doctype = frm.fields_dict[fieldname].df.options;
	const html_field = frm.get_field(wrapper_field);
	if (!html_field) {
		console.error(`render_document_references_table: HTML field "${wrapper_field}" not found`);
		return;
	}
	if (frm.fields_dict[fieldname].$wrapper) {
		frm.fields_dict[fieldname].$wrapper.hide();
	}

	frappe.model.with_doctype(child_doctype, () => {
		ensure_drdocref_styles();
		const meta = frappe.get_meta(child_doctype);
		const editable_grid = !!meta.editable_grid;
		const columns = show_fields
			.map((fn) => meta.fields.find((f) => f.fieldname === fn))
			.filter((df) => df && !df.hidden);

		const selected = new Set();
		let active_controls = [];
		let $wrap; // set on every render(); read by render_row()'s checkbox handler

		render();


		function refresh_bulk_actions() {
			const count = selected.size;
			$wrap.find(".drdocref-bulk-delete").toggle(count > 0);
			$wrap
				.find(".drdocref-selected-count")
				.toggle(count > 0)
				.text(count ? __("{0} row(s) selected", [count]) : "");
		}

		function get_rows() {
			return frm.doc[fieldname] || [];
		}
		function is_locked() {
			return locked_statuses.includes(frm.doc[status_field]);
		}

		function render() {

			active_controls.forEach((c) => c.$wrapper && c.$wrapper.remove());
			active_controls = [];
			selected.clear();

			const rows = get_rows();
			const locked = is_locked();

			$wrap = $(`
				<div class="drdocref-widget">
					<div class="drdocref-heading-row">
						<div class="drdocref-row drdocref-header-row" style="display:flex;align-items:center;font-weight:600;font-size:12px;color:var(--text-muted);text-transform:uppercase;border-bottom:1px solid var(--border-color);padding:6px 0;">
							<div class="drdocref-col" style="width:32px;text-align:center;flex:none;">
								${locked ? "" : `<input type="checkbox" class="drdocref-check-all">`}
							</div>
							<div class="drdocref-col" style="width:36px;flex:none;">${__("No.")}</div>
							${columns
								.map(
									(df) =>
										`<div class="drdocref-col" style="flex:1;padding:0 8px;">${frappe.utils.escape_html(__(df.label))}${
											df.reqd ? ' <span class="text-danger">*</span>' : ""
										}</div>`,
								)
								.join("")}
							<div class="drdocref-col" style="width:36px;flex:none;"></div>
						</div>
					</div>
					<div class="drdocref-body"><div class="drdocref-rows"></div></div>
					${
						locked
							? ""
							: `<div class="drdocref-footer" style="margin-top:6px;display:flex;align-items:center;gap:8px;">
						<button class="btn btn-xs btn-danger drdocref-bulk-delete" style="display:none;">${__("Delete")}</button>
						<button class="btn btn-xs btn-secondary drdocref-add-row">
							<i class="fa fa-plus" style="margin-right:4px;"></i>${__("Add Row")}
						</button>
						<span class="text-muted small drdocref-selected-count" style="display:none;"></span>
					</div>`
					}
				</div>
			`);

			html_field.$wrapper.empty().append($wrap);
			const $rows = $wrap.find(".drdocref-rows");

			if (!rows.length) {
				$rows.append(
					`<div class="text-muted small" style="padding:8px 0;">${__("No documents added yet")}</div>`,
				);
			}
			rows.forEach((row, i) => render_row(row, i + 1, $rows, locked));

			$wrap.find(".drdocref-add-row").on("click", () => {
				const row = frappe.model.add_child(frm.doc, child_doctype, fieldname);
				frm.dirty();
				render();
			});

			$wrap.find(".drdocref-check-all").on("change", function () {
				const checked = this.checked;
				const rows_ = get_rows();
				selected.clear();
				if (checked) rows_.forEach((r) => selected.add(r.name));
				// Reflect state on the row checkboxes directly rather than
				// triggering their own change handlers, which would just
				// redundantly recompute the same `selected` set.
				$wrap.find(".drdocref-row-check").prop("checked", checked);
				$wrap
					.find(".drdocref-rows > .drdocref-row")
					.toggleClass("drdocref-row-selected", checked);
				refresh_bulk_actions();
			});

			refresh_bulk_actions();

			$wrap.find(".drdocref-bulk-delete").on("click", () => {
				frappe.confirm(__("Remove {0} selected document(s)?", [selected.size]), () => {
					const rows_ = get_rows();
					for (const name of Array.from(selected)) {
						const idx = rows_.findIndex((r) => r.name === name);
						if (idx !== -1) rows_.splice(idx, 1);
						frappe.model.clear_doc(child_doctype, name);
					}
					rows_.forEach((r, i) => (r.idx = i + 1));
					frm.dirty();
					// Persist immediately on confirm — the user already
					// confirmed the delete, they shouldn't also have to
					// remember to hit Save afterwards.
					frm.save().then(render).catch(render);
				});
			});
		}

		function render_row(row, idx, $rows, locked) {
			const $row = $(`
				<div class="drdocref-row" data-name="${row.name}" style="display:flex;align-items:center;border-bottom:1px solid var(--border-color);padding:4px 0;">
					<div class="drdocref-col" style="width:32px;text-align:center;flex:none;">
						${locked ? "" : `<input type="checkbox" class="drdocref-row-check">`}
					</div>
					<div class="drdocref-col text-muted" style="width:36px;flex:none;">${idx}</div>
				</div>
			`);

			if (!locked) {
				$row.find(".drdocref-row-check").on("change", function () {
					this.checked ? selected.add(row.name) : selected.delete(row.name);
					// Match native grid: highlight the whole row while it's selected.
					$row.toggleClass("drdocref-row-selected", this.checked);
					refresh_bulk_actions();
				});
			}

			columns.forEach((df) => {
				const $cell = $(
					`<div class="drdocref-col drdocref-static-col" data-fieldname="${df.fieldname}" style="flex:1;padding:0 4px;"></div>`,
				);
				$row.append($cell);
				if (editable_grid && !locked && !df.read_only) {
					make_cell_control(df, row, $cell);
				} else {
					$cell.html(format_static(df, row)).css({ padding: "4px 8px" });
				}
				// Missing-mandatory highlight, same intent as native grid.
				if (df.reqd && !row[df.fieldname]) {
					$cell.css(
						"background-color",
						"var(--table-yellow-bg, rgba(255, 210, 0, 0.08))",
					);
				}
			});

			const $expand = $(`<div class="drdocref-col text-center" style="width:36px;flex:none;">
				<a class="drdocref-expand text-muted" title="${__("Edit full row")}"><i class="fa fa-pencil"></i></a>
			</div>`);
			$expand.find(".drdocref-expand").on("click", () => open_row_dialog(row, locked));
			$row.append($expand);

			$rows.append($row);
		}

		function make_cell_control(df, row, $cell) {
			// Grid view collapses long-text-ish fieldtypes to a single-line
			// input, same as native Frappe. The dialog (pencil) still edits
			// the real fieldtype — this is purely a grid rendering choice.
			const grid_df = GRID_COLLAPSE_TO_DATA.includes(df.fieldtype)
				? { ...df, fieldtype: "Data" }
				: { ...df };

			const is_attach = df.fieldtype === "Attach" || df.fieldtype === "Attach Image";
			if (is_attach) {
				// The Attach control's post-upload state (filename + Clear,
				// sometimes more) is wider than a single grid column and
				// would otherwise get clipped by the column's overflow:hidden.
				// This only matters for the brief moment before the autosave
				// below re-renders the cell.
				$cell.css("overflow", "visible");
			}

			const control = frappe.ui.form.make_control({
				df: grid_df,
				parent: $cell.get(0),
				render_input: true,
				only_input: true,
				value: row[df.fieldname],
			});
			control.refresh();
			control.set_value(row[df.fieldname]);

			let last_synced_value = control.get_value();
			control.df.onchange = () => {
				const new_value = control.get_value();
				if (new_value === last_synced_value) return;
				last_synced_value = new_value;
				// Always write back using the REAL fieldname/value — collapsing
				// is purely visual, the stored value/type is unaffected.
				frappe.model.set_value(child_doctype, row.name, df.fieldname, new_value);
				frm.dirty();
				maybe_prefill_title(row);
				if (is_attach) {
					frm.save().then(render).catch(render);
				}
			};
			active_controls.push(control);
		}

		function format_static(df, row) {
			const value = row[df.fieldname];
			if (!value) return `<span class="text-muted">&mdash;</span>`;
			if (df.fieldtype === "Attach" || df.fieldtype === "Attach Image") {
				const file_name = decodeURIComponent(String(value).split("/").pop());
				return `<a href="${value}" target="_blank" rel="noopener"><i class="fa fa-link" style="margin-right:4px;"></i>${frappe.utils.escape_html(file_name)}</a>`;
			}
			if (df.fieldtype === "Date" || df.fieldtype === "Datetime")
				return frappe.datetime.str_to_user(value);
			if (df.fieldtype === "Check") return value ? __("Yes") : __("No");
			if (GRID_COLLAPSE_TO_DATA.includes(df.fieldtype)) {
				// Single-line, truncated like the native grid — no wrapping/newlines,
				// with a title tooltip so the full value is still discoverable.
				const escaped = frappe.utils.escape_html(String(value));
				return `<span title="${escaped}" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block;">${escaped}</span>`;
			}
			return frappe.utils.escape_html(frappe.format(value, df));
		}

		// Expand dialog shows ALL non-hidden fields on the child doctype,
		// not just the visible columns — matching native grid's row-expand.
		function open_row_dialog(row, locked) {
			const all_fields = meta.fields.filter((f) => !f.hidden);
			const dialog = new frappe.ui.Dialog({
				title: __("Document"),
				fields: all_fields.map((df) => ({
					...df,
					read_only: locked ? 1 : df.read_only,
					default: row[df.fieldname],
				})),
				primary_action_label: locked ? undefined : __("Save"),
				primary_action: locked
					? undefined
					: (values) => {
							Object.assign(row, values);
							maybe_prefill_title(row);
							frm.dirty();
							dialog.hide();
							frm.save().then(render).catch(render);
						},
			});

			if (!locked) {
				dialog.set_secondary_action_label(__("Delete"));
				dialog.set_secondary_action(() => {
					frappe.confirm(__("Delete this document?"), () => {
						const rows_ = get_rows();
						const idx = rows_.findIndex((r) => r.name === row.name);
						if (idx !== -1) rows_.splice(idx, 1);
						frappe.model.clear_doc(child_doctype, row.name);
						rows_.forEach((r, i) => (r.idx = i + 1));
						frm.dirty();
						dialog.hide();
						frm.save().then(render).catch(render);
					});
				});
			}

			dialog.show();
		}

		function maybe_prefill_title(row) {
			const has_title =
				columns.some((c) => c.fieldname === "document_title") ||
				meta.fields.some((f) => f.fieldname === "document_title");
			if (has_title && row.document && !row.document_title) {
				const file_name = decodeURIComponent(String(row.document).split("/").pop());
				row.document_title = file_name.replace(/\.[^/.]+$/, "");
			}
		}
	});
};
