// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

const DEFAULT_ROUND_STATUS = "Scheduled";
const CANCELLED_LIKE_STATUSES = ["Cancelled", "Rescheduled"];
const FINAL_ROUND_STATUSES = new Set(["Cancelled", "Rescheduled", "Completed"]);

frappe.ui.form.on("Interview", {
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

		hide_interview_round_no_column(frm);
		apply_round_delete_restriction(frm); 
		check_marketing_superiority(frm); 
		capture_status_snapshots(frm);

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

		if (!row.status) {
			frappe.model.set_value(cdt, cdn, "status", DEFAULT_ROUND_STATUS);
		}

		apply_round_row_lock(frm);
	},

	interview_rounds_table_remove(frm) {
		apply_round_row_lock(frm);
	},

	// Fires whenever a row's expanded edit dialog opens — the dialog builds
	// its fields fresh each time, so read-only state must be re-applied here,
	// not just once on form refresh.
	form_render(frm, cdt, cdn) {
		apply_round_row_lock(frm);
		toggle_cancellation_fields(frm, cdt, cdn);
	},

	status(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row || row.__reverting_status) return;

		// Already finalized in a previous save — status can never change again,
		// no matter what row this is or whether it's still the "last" round.
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

		// About to set a terminal status for the first time — irreversible
		// once saved, so confirm before letting it stick.
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
					const fallback = row.__status_snapshot || DEFAULT_ROUND_STATUS;
					frappe.model.set_value(cdt, cdn, "status", fallback).then(() => {
						row.__reverting_status = false;
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

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------

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

function check_marketing_superiority(frm) {
	if (!frm.doc.marketing_link) {
		frm.__is_superior = false;
		apply_round_row_lock(frm);
		return;
	}

	frappe.db
		.get_value("Marketing", frm.doc.marketing_link, "assign_to")
		.then(({ message }) => {
			const assign_to = message?.assign_to;
			if (!assign_to) {
				frm.__is_superior = false;
				apply_round_row_lock(frm);
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
				},
				error(err) {
					console.error("Permission check failed", err);
					frm.__is_superior = false; // fail closed
					apply_round_row_lock(frm);
				},
			});
		})
		.catch((err) => {
			console.error("Failed to fetch Marketing's assign_to", err);
			frm.__is_superior = false; // fail closed
			apply_round_row_lock(frm);
		});
}

function apply_round_row_lock(frm) {
	const rows = frm.doc.interview_rounds_table || [];
	if (!rows.length) return;

	const grid = frm.fields_dict.interview_rounds_table.grid;
	const last_idx = rows.length;
	const is_superior = !!frm.__is_superior;

	rows.forEach((row) => {
		const is_editable = row.idx === last_idx || is_superior;
		const grid_row = grid.grid_rows_by_docname[row.name];
		if (!grid_row) return;

		// Inline (in-table) editable cells
		(grid_row.docfields || []).forEach((df) => {
			df.read_only = is_editable ? 0 : 1;
		});

		// Expanded row-edit dialog, if currently open for this row
		if (grid_row.grid_form && grid_row.grid_form.fields_dict) {
			Object.values(grid_row.grid_form.fields_dict).forEach((field) => {
				field.df.read_only = is_editable ? 0 : 1;
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

function toggle_cancellation_fields(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row) return;

	const is_cancel_like = CANCELLED_LIKE_STATUSES.includes(row.status);

	const grid_row = frm.fields_dict.interview_rounds_table.grid.grid_rows_by_docname[cdn];

	if (!grid_row || !grid_row.grid_form) return;

	["cancelled_by", "reason_of_cancel"].forEach((fieldname) => {
		const field = grid_row.grid_form.fields_dict[fieldname];
		if (!field) return;

		field.df.hidden = is_cancel_like ? 0 : 1;
		field.df.reqd = is_cancel_like ? 1 : 0;

		field.refresh();
	});

	grid_row.grid_form.refresh();
}

function fetch_and_render_resume(frm) {
	const set_html = (html) => frm.set_df_property("resume", "options", html);

	frappe.db
		.get_value("Marketing", frm.doc.marketing_link, "customer")
		.then(({ message }) => {
			const customer = message?.customer;
			if (!customer) {
				set_html('<div style="color:#888">No customer selected</div>');
				return null;
			}
			return frappe.db.get_value("Resume", { customer }, ["resume"]);
		})
		.then((r) => {
			const file_url = r?.message?.resume;
			if (!file_url) {
				set_html('<div style="color:#888">No resume uploaded</div>');
				return;
			}
			set_html(`
				<div style="padding:8px">
					<a href="${file_url}" target="_blank" style="color:#1a73e8;font-weight:600;text-decoration:none;">
						📄 View Resume
					</a>
				</div>
			`);
		})
		.catch(() => {
			set_html('<div style="color:#888">No resume uploaded</div>');
		});
}
