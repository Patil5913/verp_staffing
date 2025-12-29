// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing", {
	refresh(frm) {
        frm.add_custom_button("Show Form Tour", () => {
            const tour_name = 'Marketing Form';

            frm.tour.init({ tour_name })
                .then(() => frm.tour.start());
        });
	},
});
