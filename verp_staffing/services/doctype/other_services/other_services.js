// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Other Services", {
	refresh(frm) {
		window.add_forward_button(frm);
		window.render_notes(frm);
		window.render_activity_section(frm);
	},
});

