frappe.ui.form.on("Resume", {
	async refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);

		render_resume_document_table(frm, {
			fieldname: "resume_table",
			wrapper_field: "resume_html",
			show_fields: ["document", "date"],
			status_field: "status",
		});

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
			frm.set_df_property("assign_to", "read_only", 1);
			window.add_forward_button(frm, (service_name = "Resume"));
		}

		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: display_fields,
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Resume";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		window.setup_service_permission_button(frm);

		frm.set_query("assign_to", () => {
			return {
				query: "verp_staffing.crm.api.helpers.get_assign_to_by_service",
				filters: {
					service: "Resume",
					customer: frm.doc.customer,
				},
			};
		});
	},

	status(frm) {
		if (frm.doc.status == "Completed") {
			window.add_forward_button(frm, (service_name = "Resume"));
		}
	},

	validate(frm) {
		validate_resume_submission(frm);
	},
});

function get_new_resume_rows(frm) {
	return (frm.doc.resume_table || []).filter((row) => row.__islocal);
}

function validate_resume_submission(frm) {
	const new_rows = get_new_resume_rows(frm);

	if (new_rows.length > 1) {
		frappe.msgprint({
			title: __("Invalid Resume Submission"),
			message: __("Only one new resume can be uploaded at a time."),
			indicator: "red",
		});

		frappe.validated = false;

		return;
	}

	if (new_rows.length === 1 && !new_rows[0].document) {
		frappe.msgprint({
			title: __("Resume Required"),
			message: __("Please upload the resume attachment."),
			indicator: "red",
		});

		frappe.validated = false;

		return;
	}
}

function render_resume_document_table(frm, opts) {
	const { fieldname, wrapper_field, show_fields, status_field = "status" } = opts;

	if (!Array.isArray(show_fields) || !show_fields.length) {
		console.error(
			`render_resume_document_table: "show_fields" must be a non-empty array, got:`,
			show_fields,
		);
		return;
	}

	const child_doctype = frm.fields_dict[fieldname].df.options;
	const html_field = frm.get_field(wrapper_field);
	if (!html_field) {
		console.error(`render_resume_document_table: HTML field "${wrapper_field}" not found`);
		return;
	}
	if (frm.fields_dict[fieldname].$wrapper) {
		frm.fields_dict[fieldname].$wrapper.hide();
	}

	frappe.model.with_doctype(child_doctype, () => {
		const meta = frappe.get_meta(child_doctype);
		const columns = show_fields
			.map((fn) => meta.fields.find((f) => f.fieldname === fn))
			.filter((df) => df && !df.hidden);

		let active_controls = [];
		render();

		function get_rows() {
			return frm.doc[fieldname] || [];
		}
		function is_new_row(row) {
			return String(row.name).startsWith("new-");
		}
		function status_locked() {
			return frm.doc[status_field] === "Completed";
		}
		function has_pending_new_row() {
			return get_rows().some(is_new_row);
		}

		function render() {
			active_controls.forEach((c) => c.df && c.$wrapper && c.$wrapper.remove());
			active_controls = [];

			const rows = get_rows();
			const locked = status_locked();
			const show_add = !locked && !has_pending_new_row();

			const $wrap = $(`
				<div class="drresume-widget form-grid">
					<div class="grid-heading-row">
						<div class="grid-row grid-row-header" style="display:flex;font-weight:600;font-size:12px;color:var(--text-muted);text-transform:uppercase;border-bottom:1px solid var(--border-color);padding:6px 0;">
							<div class="col" style="width:36px;">${__("No.")}</div>
							${columns.map((df) => `<div class="col" style="flex:1;padding:0 8px;">${frappe.utils.escape_html(__(df.label))}</div>`).join("")}
							<div class="col" style="width:36px;"></div>
						</div>
					</div>
					<div class="grid-body"><div class="rows"></div></div>
					${
						show_add
							? `<div class="grid-footer" style="margin-top:6px;">
						<button class="btn btn-xs btn-secondary drresume-add-row">
							<i class="fa fa-plus" style="margin-right:4px;"></i>${__("Add Row")}
						</button>
					</div>`
							: ""
					}
				</div>
			`);

			html_field.$wrapper.empty().append($wrap);
			const $rows = $wrap.find(".rows");

			if (!rows.length) {
				$rows.append(
					`<div class="text-muted small" style="padding:8px 0;">${__("No resume uploaded yet")}</div>`,
				);
			}
			rows.forEach((row, i) => render_row(row, i + 1, $rows, locked));

			$wrap.find(".drresume-add-row").on("click", () => {
				const row = frappe.model.add_child(frm.doc, child_doctype, fieldname);
				frm.dirty();
				render();
			});
		}

		function render_row(row, idx, $rows, locked) {
			const editable = !locked && is_new_row(row);

			const $row = $(`
				<div class="grid-row" data-name="${row.name}" style="display:flex;align-items:center;border-bottom:1px solid var(--border-color);padding:4px 0;">
					<div class="col text-muted" style="width:36px;">${idx}</div>
				</div>
			`);

			columns.forEach((df) => {
				const $cell = $(`<div class="col" style="flex:1;padding:0 4px;"></div>`);
				if (editable && !df.read_only) {
					make_cell_control(df, row, $cell);
				} else {
					$cell.html(format_static(df, row)).css({ padding: "4px 8px" });
				}
				$row.append($cell);
			});

			const $action = $(`<div class="col text-right" style="width:36px;"></div>`);
			// Only the pending unsaved row can be discarded before the doc is saved.
			if (editable) {
				$action.html(
					`<a class="drresume-remove text-muted" title="${__("Remove")}"><i class="fa fa-trash" style="color: red;"></i></a>`,
				);
				$action.find(".drresume-remove").on("click", () => {
					frappe.confirm(__("Discard this upload?"), () => {
						const rows = get_rows();
						const idx_ = rows.findIndex((r) => r.name === row.name);
						if (idx_ !== -1) rows.splice(idx_, 1);
						rows.forEach((r, i) => (r.idx = i + 1));
						frappe.model.clear_doc(child_doctype, row.name);
						frm.dirty();
						render();
					});
				});
			}
			$row.append($action);
			$rows.append($row);
		}

		function make_cell_control(df, row, $cell) {
			const control = frappe.ui.form.make_control({
				df: { ...df, reqd: df.fieldname === "document" ? 1 : df.reqd },
				parent: $cell.get(0),
				render_input: true,
				only_input: true,
				value: row[df.fieldname],
			});
			control.refresh();
			control.set_value(row[df.fieldname]);
			control.df.onchange = () => {
				const value = control.get_value();
				frappe.model.set_value(child_doctype, row.name, df.fieldname, value);
				frm.dirty();
				if (
					df.fieldname === "document" &&
					value &&
					columns.some((c) => c.fieldname === "document_title") &&
					!row.document_title
				) {
					const file_name = decodeURIComponent(String(value).split("/").pop());
					const title_ctrl = active_controls.find(
						(c) => c.df.fieldname === "document_title",
					);
					const title = file_name.replace(/\.[^/.]+$/, "");
					frappe.model.set_value(child_doctype, row.name, "document_title", title);
					if (title_ctrl) title_ctrl.set_value(title);
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
			return frappe.utils.escape_html(frappe.format(value, df));
		}
	});
}
