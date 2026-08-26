// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

const CANCELLED_LIKE_STATUSES = ["Cancelled", "Rescheduled"];
const FINAL_ROUND_STATUSES = new Set(["Cancelled", "Rescheduled", "Completed"]);

frappe.ui.form.on("Interview", {
	onload(frm) {
		initialize_default_interview_status(frm);
	},

	onload_post_render(frm) {
		initialize_default_interview_status(frm);
	},

	refresh(frm) {
		frappe.breadcrumbs.clear();

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Interviews",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();

		frm.add_custom_button("Show Form Tour", () => {
			frm.tour.init({ tour_name: "Interview" }).then(() => frm.tour.start());
		});

		// For new Interview, make sure default status is applied.
		initialize_default_interview_status(frm);

		hide_interview_round_no_column(frm);
		apply_round_delete_restriction(frm);
		check_marketing_superiority(frm);
		capture_status_snapshots(frm);
		apply_round_row_lock(frm);
		block_round_reorder(frm);
		block_round_tab_new_row(frm);

		if (!frm.is_new()) {
			frm.set_df_property("marketing_link", "read_only", 1);
			frm.set_df_property("role", "read_only", 1);
			frm.set_df_property("company", "read_only", 1);
			frm.set_df_property("status", "read_only", 1);

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

		// Always use the same cached default-status request.
		if (!row.status) {
			get_default_interview_status(frm).then((default_status) => {
				if (!default_status || row.status) return;
				frappe.model.set_value(cdt, cdn, "status", default_status);
			});
		}

		apply_round_row_lock(frm);
		block_round_reorder(frm);
		block_round_tab_new_row(frm);
	},

	interview_rounds_table_remove(frm) {
		apply_round_row_lock(frm);
		block_round_reorder(frm);
		block_round_tab_new_row(frm);
	},

	form_render(frm, cdt, cdn) {
		apply_round_row_lock(frm);
		toggle_cancellation_fields(frm, cdt, cdn);
		block_round_tab_new_row(frm);
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

					get_default_interview_status(frm).then((default_status) => {
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

async function initialize_default_interview_status(frm) {
	if (!frm || !frm.doc || !frm.is_new()) {
		return;
	}

	// If already assigned, don't overwrite it.
	if (frm.doc.status) {
		return;
	}

	const default_status = await get_default_interview_status(frm);

	if (!default_status) {
		return;
	}

	// The document may have changed while the async request was running.
	if (!frm.is_new() || frm.doc.status) {
		return;
	}

	await frm.set_value("status", default_status);
}

function get_default_interview_status(frm) {
	if (!frm.__default_interview_status_promise) {
		frm.__default_interview_status_promise = frappe.db
			.get_single_value("ERP Configuration", "default_interview_status")
			.then((value) => {
				if (!value) {
					frappe.throw(
						__(
							"Default Interview Status is not set in 'ERP Configuration', please contact admin.",
						),
					);
				}

				frm.__default_interview_status = value;

				return value;
			})
			.catch((err) => {
				console.error("Failed to fetch default interview status", err);

				frm.__default_interview_status = "";

				return "";
			});
	}

	return frm.__default_interview_status_promise;
}

function hide_interview_round_no_column() {
	if ($("#interview-round-no-column-style").length) return;

	$("head").append(`
		<style id="interview-round-no-column-style">
			[data-fieldname="interview_rounds_table"] .row-index,
			[data-fieldname="interview_rounds_table"] .grid-row-index {
				display: none !important;
			}
		</style>
	`);
}

function inject_round_lock_style() {
	if ($("#interview-round-lock-style").length) return;

	// button classes come from grid_row_form.js's set_form_events bindings
	$("head").append(`
		<style id="interview-round-lock-style">
			[data-fieldname="interview_rounds_table"].round-reorder-locked .grid-insert-row,
			[data-fieldname="interview_rounds_table"].round-reorder-locked .grid-insert-row-below,
			[data-fieldname="interview_rounds_table"].round-reorder-locked .grid-duplicate-row,
			[data-fieldname="interview_rounds_table"].round-reorder-locked .grid-move-row,
			[data-fieldname="interview_rounds_table"].round-reorder-locked .grid-append-row {
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

function is_row_locked(frm, row) {
	if (!frm || !frm.doc) return true;
	if (frm.__is_superior) return false;
	const rows = frm.doc.interview_rounds_table || [];
	const last_idx = rows.length;
	return row.idx !== last_idx;
}

function is_drag_locked(frm) {
	return !frm?.__is_superior;
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
	if (!frm || !frm.doc || !frm.fields_dict?.interview_rounds_table) return;
	const rows = frm.doc.interview_rounds_table || [];
	if (!rows.length) return;

	const grid = frm.fields_dict.interview_rounds_table.grid;
	const drag_locked = is_drag_locked(frm);

	rows.forEach((row) => {
		const grid_row = grid.grid_rows_by_docname[row.name];
		if (!grid_row) return;

		const locked = is_row_locked(frm, row);
		row._sortable = !drag_locked;

		if (grid_row.docfields === grid.docfields) {
			grid_row.docfields = grid.docfields.map((df) => ({ ...df }));
		}
		grid_row.docfields.forEach((df) => {
			df.__base_read_only = df.__base_read_only ?? df.read_only ?? 0;
			df.read_only = locked ? 1 : df.__base_read_only;
		});
		grid_row.refresh();

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

function block_round_reorder(frm) {
	if (!frm || !frm.fields_dict?.interview_rounds_table) return;

	inject_round_lock_style();

	const grid = frm.fields_dict.interview_rounds_table.grid;
	const drag_locked = is_drag_locked(frm);

	frm.fields_dict.interview_rounds_table.$wrapper?.toggleClass(
		"round-reorder-locked",
		drag_locked,
	);

	const wrapper_el = grid.wrapper[0];
	if (wrapper_el) {
		if (wrapper_el.__round_lock_handle_guard) {
			wrapper_el.removeEventListener(
				"mousedown",
				wrapper_el.__round_lock_handle_guard,
				true,
			);
			wrapper_el.removeEventListener(
				"touchstart",
				wrapper_el.__round_lock_handle_guard,
				true,
			);
		}
		const guard = function (e) {
			if (is_drag_locked(frm) && e.target.closest(".sortable-handle")) {
				e.stopPropagation();
				e.preventDefault();
			}
		};
		wrapper_el.__round_lock_handle_guard = guard;
		wrapper_el.addEventListener("mousedown", guard, true);
		wrapper_el.addEventListener("touchstart", guard, true);
	}

	patch_grid_row_actions(frm);
}

function block_round_tab_new_row(frm) {
	if (!frm || !frm.fields_dict?.interview_rounds_table) return;

	const grid = frm.fields_dict.interview_rounds_table.grid;
	const wrapper_el = grid.wrapper[0];
	if (!wrapper_el) return;

	if (wrapper_el.__round_tab_new_row_guard) {
		wrapper_el.removeEventListener("keydown", wrapper_el.__round_tab_new_row_guard, true);
	}

	const guard = function (e) {
		if (e.key !== "Tab" || e.shiftKey) return;

		const row_el = e.target.closest(".grid-row");
		if (!row_el) return;

		const focusable = Array.from(
			row_el.querySelectorAll(
				'input:not([type="hidden"]):not(:disabled), select:not(:disabled), textarea:not(:disabled), [contenteditable="true"]',
			),
		).filter((el) => el.offsetParent !== null);

		if (!focusable.length) return;

		const current_index = focusable.indexOf(e.target);
		if (current_index === -1) return;

		// Only the row's last focusable field is where Frappe would
		// otherwise create a new row on Tab — swallow it entirely here
		// (no row creation, no focus shift anywhere). Any earlier field
		// falls through untouched, so Tab keeps moving to the next
		// field in the same row as normal.
		if (current_index === focusable.length - 1) {
			e.preventDefault();
			e.stopPropagation();
			e.stopImmediatePropagation();
		}
	};

	wrapper_el.__round_tab_new_row_guard = guard;
	wrapper_el.addEventListener("keydown", guard, true);
}

function patch_grid_row_actions(frm) {
	const sample_row = frm.fields_dict.interview_rounds_table.grid.grid_rows?.[0];
	if (!sample_row) return;

	const grid_row_proto = Object.getPrototypeOf(sample_row);
	if (grid_row_proto.__round_lock_patched) return;
	grid_row_proto.__round_lock_patched = true;

	const original_insert = grid_row_proto.insert;
	const original_move = grid_row_proto.move;

	grid_row_proto.insert = function (...args) {
		if (this.doc.doctype === "Interview Round" && is_drag_locked(this.frm)) return;
		return original_insert.apply(this, args);
	};

	grid_row_proto.move = function (...args) {
		if (this.doc.doctype === "Interview Round" && is_drag_locked(this.frm)) return;
		return original_move.apply(this, args);
	};
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
			args: { customer: customer },
			callback(r) {
				const resume = r.message;
				if (!resume?.document) {
					clear_resume();
					return;
				}
				set_html(`
				<div style="padding:8px">
					
						href="${resume.document}"
						target="_blank"
						style="color:#1a73e8;font-weight:600;text-decoration:none;"
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
