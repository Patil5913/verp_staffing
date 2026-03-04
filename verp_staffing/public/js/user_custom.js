frappe.provide("frappe.ui.form");

frappe.ui.form.UserQuickEntryForm = class UserQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	constructor(doctype, after_insert, init_callback, doc, force) {
		super(doctype, after_insert, init_callback, doc, force);
		this.skip_redirect_on_error = true;  // Like ERPNext Customer
	}

	render_dialog() {		
		super.render_dialog();

		// Hide role fields after dialog renders (ERPNext Customer style)
		["role_permission_name", "role_profile_name"].forEach(fieldname => {
			let field = this.dialog.get_field(fieldname);
			if (field) {
				field.df.hidden = 1;
				field.refresh();
			}
		});
	}
};
