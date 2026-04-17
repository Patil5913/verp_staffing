frappe.listview_settings["Supplier"] = {
	add_fields: ["supplier_name", "supplier_group", "disabled"],
	get_indicator: function (doc) {
		if (cint(doc.disabled)) {
			return [__("Disabled"), "red"];
		}
	},
};
