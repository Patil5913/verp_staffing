// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt
// List view JS for your DocType
// frappe.listview_settings['Interview'] = {
//     onload: function(listview) {
//         // Hide filter button
//         listview.page.btn_filter && listview.page.btn_filter.hide();
        
//         // Or hide via DOM
//         $('.list-filter-button').hide();
//         $('[data-action="filter"]').hide();
//     }
// };

frappe.ui.form.on("Interview", {
	refresh(frm) {
		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Interview Form";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
		fetch_and_render_resume(frm);

		set_round_numbers(frm);

		if (!frm.is_new()) {
			frm.set_df_property("marketing_link", "read_only", 1);
			frm.set_df_property("role", "read_only", 1);
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
	frappe.db
		.get_list("Marketing", {
			filters: {
				name: frm.doc.marketing_link,
			},
			fields: ["name", "customer"],
			limit: 1,
		})
		.then((Marketing_res) => {
			if (!Marketing_res || !Marketing_res.length || !Marketing_res[0].customer) {
				return;
			}
			const customer = Marketing_res[0].customer;
			if (!customer) {
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
						customer: customer,
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
		});
}