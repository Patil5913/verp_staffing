frappe.provide("frappe.ui.form");

// 1. Define your dynamic configuration here
const quick_entry_config = {
	Lead: {
		fields: [
			{ label: __("Surname"), fieldname: "surname", fieldtype: "Data" },
			{ label: __("Email"), fieldname: "email", fieldtype: "Data", options: "Email" },
		],
	}
};

// 2. Factory function to generate and register classes
Object.keys(quick_entry_config).forEach((doctype) => {
	const config = quick_entry_config[doctype];
	const className = `${doctype}QuickEntryForm`;

	frappe.ui.form[className] = class extends frappe.ui.form.QuickEntryForm {
		get_variant_fields() {
			return config.fields;
		}

		render_dialog() {
			this.mandatory = this.mandatory.concat(this.get_variant_fields());
			super.render_dialog();
		}

		// ... inside your insert() method ...
		insert() {
			let me = this;
			let values = this.dialog.get_values();
			if (!values) return;

			return new Promise((resolve) => {
				// --- UPDATED EMAIL VALIDATION ---
				let invalid_email = false;
				config.fields.forEach((f) => {
					// Check if field is Email type AND has a non-empty value
					if (f.options === "Email" && values[f.fieldname]) {
						if (!frappe.utils.validate_type(values[f.fieldname], "email")) {
							frappe.msgprint(
								__("Please enter a valid email address for {0}", [f.label]),
							);
							invalid_email = true;
						}
					}
				});

				if (invalid_email) {
					// CRITICAL: Resolve the promise so the "Saving..." state ends
					resolve();
					return;
				}
				// ------------------------------

				this.update_doc();

				frappe.call({
					method: "frappe.desk.form.save.savedocs",
					args: { doc: JSON.stringify(this.doc), action: "Save" },
					callback: function (r) {
						if (!r.exc && r.docs && r.docs.length > 0) {
							let saved_doc = r.docs[0];
							let real_name = saved_doc.name;

							if (!saved_doc.from_lead) {
								frappe.call({
									method: "verp_staffing.crm.api.lead_details.create_lead_details",
									args: {
										doctype: me.doctype,
										docname: real_name,
										first_name: saved_doc.name1,
										custom_values: values,
									},
									callback: function (res) {
										frappe.model.clear_doc(me.doctype, real_name);
										frappe.model.with_doc(me.doctype, real_name, function () {
											me.dialog.hide();
											if (me.after_insert) {
												me.after_insert(saved_doc);
											} else {
												frappe.set_route("Form", me.doctype, real_name);
											}
											resolve(); // Resolve after full sync
										});
									},
								});
							} else {
								me.dialog.hide();
								frappe.set_route("Form", me.doctype, real_name);
								resolve();
							}
						} else {
							resolve(); // Resolve if server save fails to stop "Saving..."
						}
					},
				});
			});
		}
	};
});
