// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Interview", {
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
			const tour_name = "Interview Form";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
		
		set_round_numbers(frm);
		
		if (!frm.is_new()) {
			frm.set_df_property("marketing_link", "read_only", 1);
			frm.set_df_property("role", "read_only", 1);
			frm.set_df_property("compnay", "read_only", 1);
			fetch_and_render_resume(frm);
		}
	},
});

frappe.ui.form.on("Interview Round", {
	interview_rounds_table_add(frm, cdt, cdn) {
		set_round_numbers(frm);

		const row = locals[cdt][cdn];

		// adding previos follow up value in state
		row.__prev_follow_up = row.follow_up || 0;
	},

	interview_rounds_table_remove(frm) {
		set_round_numbers(frm);
	},

	follow_up(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		const prev = row.__prev_follow_up ?? 0;
		const curr = row.follow_up;

		if (curr !== prev + 1) {
			frappe.msgprint(`Invalid Follow Up value. Only allowed value is ${prev + 1}`);

			row.follow_up = prev;
			frm.refresh_field("interview_rounds_table");
			return;
		}

		row.__prev_follow_up = curr;
	},
});

function set_round_numbers(frm) {
	(frm.doc.interview_rounds_table || []).forEach((row) => {
		row.round = row.idx;
	});
	frm.refresh_field("interview_rounds_table");
}

function fetch_and_render_resume(frm) {
	const set_html = (html) =>
		frm.set_df_property("resume", "options", html);

	frappe.db
		.get_value(
			"Marketing",
			frm.doc.marketing_link,
			"customer",
		)
		.then(({ message }) => {
			const customer = message?.customer;

			if (!customer) {
				set_html('<div style="color:#888">No customer selected</div>');
				return null;
			}

			return frappe.db.get_value(
				"Resume",
				{
					customer,
				},
				["resume"],
			);
		})
		.then((r) => {
			const file_url = r?.message?.resume;

			if (!file_url) {
				set_html('<div style="color:#888">No resume uploaded</div>');
				return;
			}

			set_html(`
				<div style="padding:8px">
					<a href="${file_url}"
						target="_blank"
						style="
							color:#1a73e8;
							font-weight:600;
							text-decoration:none;
						">
						📄 View Resume
					</a>
				</div>
			`);
		})
		.catch(() => {
			set_html('<div style="color:#888">No resume uploaded</div>');
		});
}