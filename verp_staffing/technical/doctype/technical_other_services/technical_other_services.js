// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Technical Other Services", {
	refresh(frm) {
		window.render_notes(frm);
		window.fetch_and_render_resume(frm);
		window.add_forward_button(frm);
		window.render_activity_section(frm);
		window.setup_service_permission_button(frm);
	},
});
