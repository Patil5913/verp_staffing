frappe.listview_settings['Lead'] = {
	get_indicator: function (doc) {

		const status_colors = {
			"Won": "green",
			"Lost": "red",
			"Opportunity": "orange"
		};

		return [
			__(doc.status),
			status_colors[doc.status] || "black",
			"status,=," + doc.status
		];
	}
};