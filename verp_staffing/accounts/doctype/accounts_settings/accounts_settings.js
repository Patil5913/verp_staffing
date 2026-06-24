// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accounts Settings", {
	refresh(frm) {
        		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Accounts Settings";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
	},
});
