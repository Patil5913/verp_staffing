// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

const CANCELLED_LIKE_STATUSES = ["Cancelled", "Rescheduled"];
const FINAL_ROUND_STATUSES = new Set(["Cancelled", "Rescheduled", "Completed"]);

// Text-match strip for the row "..." dropdown. Frappe builds this menu fresh
// each time it's opened rather than once at load, so we hook show.bs.dropdown
// and remove matching items right before the menu becomes visible.
// Verify these labels against your Frappe version's actual dropdown (open one
// in devtools) if reorder items still show up on a locked row after this.
const REORDER_MENU_TEXT_MATCHES = ["insert above", "insert below", "duplicate", "move"];

frappe.ui.form.on("Interview", {
	onload(frm) {
		get_default_round_status(frm);
	},

	refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Interviews",
			doctype: frm.doctype,
			type: "Form",
		};
		frappe.breadcrumbs.update();

		frm.add_custom_button("Show Form Tour", () => {
			frm.tour.init({ tour_name: "Interview" }).then(() => frm.tour.start());
		});

		get_default_round_status(frm);

		hide_interview_round_no_column(frm);
		apply_round_delete_restriction(frm);
		check_marketing_superiority(frm); // resolves frm.__is_superior, then re-applies lock + reorder block
		capture_status_snapshots(frm);

		// Apply immediately with whatever we know so far (defaults to locked
		// until check_marketing_superiority's async callback resolves).
		apply_round_row_lock(frm);
		block_round_reorder(frm);

		if (!frm.is_new()) {
			frm.set_df_property("marketing_link", "read_only", 1);
			frm.set_df_property("role", "read_only", 1);
			frm.set_df_property("company", "read_only", 1);
			fetch_and_render_resume(frm);
		}
	},

	validate(frm) {
		const invalid_row = (frm.doc.interview_rounds_table || []).find(
			(row) =>
				CANCELLED_LIKE_STATUSES.includes(row.status) &&
				(!row.cancelled_by || !row.reason_of_cancel),
		);

		if (invalid_row) {
			frappe.msgprint({
				title: __("Missing Information"),
				indicator: "red",
				message: __(
					"Round #{0}: 'Cancelled By' and 'Reason of Cancel' are required when status is '{1}'.",
					[invalid_row.round || invalid_row.idx, invalid_row.status],
				),
			});
			frappe.validated = false;
		}
	},
});

frappe.ui.form.on("Interview Round", {
	interview_rounds_table_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		row.__prev_follow_up = row.follow_up || 0;

		if (!row.round) {
			frappe.model.set_value(cdt, cdn, "round", String(row.idx));
		}

		if (!row.status) {
			get_default_round_status(frm).then((default_status) => {
				if (default_status && !row.status) {
					frappe.model.set_value(cdt, cdn, "status", default_status);
				}
			});
		}

		apply_round_row_lock(frm);
		block_round_reorder(frm);
	},

	interview_rounds_table_remove(frm) {
		apply_round_row_lock(frm);
		block_round_reorder(frm);
	},

	form_render(frm, cdt, cdn) {
		apply_round_row_lock(frm);
		toggle_cancellation_fields(frm, cdt, cdn);
	},

	status(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row || row.__reverting_status) return;

		if (is_round_finalized(row)) {
			row.__reverting_status = true;
			frappe.msgprint({
				title: __("Status Locked"),
				indicator: "red",
				message: __(
					"This round was already marked '{0}' and its status can no longer be changed.",
					[row.__status_snapshot],
				),
			});
			frappe.model.set_value(cdt, cdn, "status", row.__status_snapshot).then(() => {
				row.__reverting_status = false;
			});
			return;
		}

		if (FINAL_ROUND_STATUSES.has(row.status)) {
			frappe.confirm(
				__(
					"Once this round's status is set to '{0}', it cannot be changed again. Continue?",
					[row.status],
				),
				() => {
					toggle_cancellation_fields(frm, cdt, cdn);
				},
				() => {
					row.__reverting_status = true;
					get_default_round_status(frm).then((default_status) => {
						const fallback = row.__status_snapshot || default_status || "";
						frappe.model.set_value(cdt, cdn, "status", fallback).then(() => {
							row.__reverting_status = false;
						});
					});
				},
			);
			return;
		}

		toggle_cancellation_fields(frm, cdt, cdn);
	},

	follow_up(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (row.__reverting_follow_up) return;

		const prev = row.__prev_follow_up ?? 0;
		const curr = row.follow_up;

		if (curr === prev) return;

		if (curr !== prev + 1) {
			frappe.show_alert(
				{
					message: __("Invalid Follow Up value. Only allowed value is {0}", [prev + 1]),
					indicator: "red",
				},
				5,
			);

			row.__reverting_follow_up = true;
			frappe.model.set_value(cdt, cdn, "follow_up", prev).then(() => {
				row.__reverting_follow_up = false;
			});
			return;
		}

		row.__prev_follow_up = curr;
	},
});

function get_default_round_status(frm) {
	if (!frm.__default_round_status_promise) {
		frm.__default_round_status_promise = frappe.db
			.get_single_value("ERP Configuration", "default_interview_status")
			.then((value) => {
				frm.__default_round_status = value || "";
				
				if (!value) {
					frappe.throw("Default Interview Status is not set in 'ERP Configuration', please contact admin.");
				}
				return frm.__default_round_status;
			})
			.catch((err) => {
				console.error("Failed to fetch default interview status", err);
				frm.__default_round_status = "";
				return "";
			});
	}
	return frm.__default_round_status_promise;
}

function hide_interview_round_no_column() {
	if ($("#interview-round-no-column-style").length) {
		return;
	}

	$("head").append(`
		<style id="interview-round-no-column-style">
			[data-fieldname="interview_rounds_table"] .row-index,
			[data-fieldname="interview_rounds_table"] .grid-row-index {
				display: none !important;
			}
		</style>
	`);
}

function capture_status_snapshots(frm) {
	(frm.doc.interview_rounds_table || []).forEach((row) => {
		row.__status_snapshot = row.status;
	});
}

function is_round_finalized(row) {
	return !!row && FINAL_ROUND_STATUSES.has(row.__status_snapshot);
}

// Single source of truth for "can this row be edited/reordered right now".
// Position (idx) is only trustworthy because block_round_reorder prevents
// non-superior users from ever changing it — the two functions are coupled
// by design, don't lock one without the other.
function is_row_locked(frm, row) {
	if (frm.__is_superior) return false;
	const rows = frm.doc.interview_rounds_table || [];
	const last_idx = rows.length;
	return row.idx !== last_idx;
}

function check_marketing_superiority(frm) {
	if (!frm.doc.marketing_link) {
		frm.__is_superior = false;
		apply_round_row_lock(frm);
		block_round_reorder(frm);
		return;
	}

	frappe.db
		.get_value("Marketing", frm.doc.marketing_link, "assign_to")
		.then(({ message }) => {
			const assign_to = message?.assign_to;
			if (!assign_to) {
				frm.__is_superior = false;
				apply_round_row_lock(frm);
				block_round_reorder(frm);
				return;
			}

			frappe.call({
				method: "verp_staffing.crm.api.helpers._is_superior_in_department",
				args: {
					assign_to,
					current_user: frappe.session.user,
					department: "Marketing",
				},
				callback(r) {
					frm.__is_superior = !!(r.message && r.message.is_superior);
					apply_round_row_lock(frm);
					block_round_reorder(frm);
				},
				error(err) {
					console.error("Permission check failed", err);
					frm.__is_superior = false; // fail closed
					apply_round_row_lock(frm);
					block_round_reorder(frm);
				},
			});
		})
		.catch((err) => {
			console.error("Failed to fetch Marketing's assign_to", err);
			frm.__is_superior = false; // fail closed
			apply_round_row_lock(frm);
			block_round_reorder(frm);
		});
}

function apply_round_row_lock(frm) {
	const rows = frm.doc.interview_rounds_table || [];
	if (!rows.length) return;

	const grid = frm.fields_dict.interview_rounds_table.grid;

	rows.forEach((row) => {
		const grid_row = grid.grid_rows_by_docname[row.name];
		if (!grid_row) return;

		const locked = is_row_locked(frm, row);

		// grid_row.docfields is the SAME array reference as grid.docfields,
		// shared across every row in the grid. Mutating it in place makes
		// every row's inline read-only state collapse to whichever row was
		// processed last. Clone once per row before mutating.
		if (grid_row.docfields === grid.docfields) {
			grid_row.docfields = grid.docfields.map((df) => ({ ...df }));
		}
		grid_row.docfields.forEach((df) => {
			df.__base_read_only = df.__base_read_only ?? df.read_only ?? 0;
			df.read_only = locked ? 1 : df.__base_read_only;
		});
		grid_row.refresh();

		// Expanded row-edit dialog, if currently open for this row.
		if (grid_row.grid_form && grid_row.grid_form.fields_dict) {
			Object.values(grid_row.grid_form.fields_dict).forEach((field) => {
				field.df.__base_read_only = field.df.__base_read_only ?? field.df.read_only ?? 0;
				field.df.read_only = locked ? 1 : field.df.__base_read_only;
				field.refresh();
			});
		}
	});

	grid.refresh();
}

function apply_round_delete_restriction(frm) {
	const restrict = frappe.session.user !== "Administrator";
	frm.set_df_property("interview_rounds_table", "cannot_delete_rows", restrict);
	frm.fields_dict.interview_rounds_table.grid.refresh();
}

// Blocks drag-sort, and strips "Insert Above / Insert Below / Duplicate /
// Move" from a locked row's dropdown. This is UX-layer only — there is
// deliberately no backend enforcement, per requirement, so an admin/superior
// user is always exempt and non-privileged users are blocked purely here.
function block_round_reorder(frm) {
	const grid = frm.fields_dict.interview_rounds_table.grid;
	const allow_all = !!frm.__is_superior;
	// Sortable.js is the drag-drop mechanism in recent Frappe versions.
	// Property name has moved across versions — guard both.
	const sortable = grid.sortable_list || grid.sortable;
	if (sortable && sortable.option) {
		sortable.option("disabled", !allow_all);
	}
	grid.wrapper.find(".grid-row").attr("draggable", allow_all ? "true" : "false");

	// Row "..." menu: Frappe rebuilds this dropdown's contents each time it
	// opens, so hook the Bootstrap show event rather than trying to strip
	// items once at render time (they won't exist yet then).
	grid.wrapper
		.off("show.bs.dropdown.round-lock")
		.on("show.bs.dropdown.round-lock", ".grid-row", function () {
			const cdn = $(this).attr("data-name");
			const row = locals["Interview Round"][cdn];
			if (!row || !is_row_locked(frm, row)) return;

			const $menu = $(this).find(".dropdown-menu");
			$menu.find(".dropdown-item, a").each(function () {
				const text = $(this).text().trim().toLowerCase();
				if (REORDER_MENU_TEXT_MATCHES.some((t) => text.includes(t))) {
					$(this).remove();
				}
			});
		});
}

function toggle_cancellation_fields(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row) return;

	const grid_row = frm.fields_dict.interview_rounds_table.grid.grid_rows_by_docname[cdn];
	if (!grid_row || !grid_row.grid_form || !grid_row.grid_form.fields_dict) return;

	const is_cancel_like = CANCELLED_LIKE_STATUSES.includes(row.status);
	const by_field = grid_row.grid_form.fields_dict.cancelled_by;
	const reason_field = grid_row.grid_form.fields_dict.reason_of_cancel;
	if (!by_field || !reason_field) return;

	const labels = {
		Cancelled: ["Cancelled By", "Reason For Cancellation"],
		Rescheduled: ["Rescheduled By", "Reason For Reschedule"],
	}[row.status] || ["Cancelled By", "Reason of cancel"];

	[by_field, reason_field].forEach((field) => {
		field.df.hidden = is_cancel_like ? 0 : 1;
		field.df.reqd = is_cancel_like ? 1 : 0;
	});
	by_field.df.label = labels[0];
	reason_field.df.label = labels[1];

	by_field.refresh();
	reason_field.refresh();

	// One refresh at the end, not one per field-mutation step, to avoid the
	// dialog tearing down/rebuilding mid-sequence.
	grid_row.grid_form.refresh();
}

function fetch_and_render_resume(frm) {
	const set_html = (html) => frm.set_df_property("resume", "options", html);

	const clear_resume = () => set_html("");

	frappe.db.get_value("Marketing", frm.doc.marketing_link, "customer").then(({ message }) => {
		const customer = message?.customer;
		if (!customer) {
			clear_resume();
			return;
		}
		frappe.call({
			method: "verp_staffing.technical.doctype.resume.resume.get_latest_resume_document",
			args: {
				customer: customer,
			},
			callback(r) {
				const resume = r.message;

				if (!resume?.document) {
					clear_resume();
					return;
				}

				set_html(`
				<div style="padding:8px">
					<a
						href="${resume.document}"
						target="_blank"
						style="
							color:#1a73e8;
							font-weight:600;
							text-decoration:none;
						"
					>
						📄 View Resume
					</a>
				</div>
			`);
			},
			error() {
				clear_resume();
			},
		});
	});
}