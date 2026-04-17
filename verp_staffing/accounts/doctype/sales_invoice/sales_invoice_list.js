frappe.listview_settings["Sales Invoice"] = {
	get_indicator: function (doc) {
		if (doc.outstanding_amount < 0) {
			return ["Credit Note Issued", "gray"];
		} else if (doc.outstanding_amount > 0 && doc.status === "Overdue") {
			return ["Overdue", "red"];
		} else if (doc.outstanding_amount > 0) {
			return ["Unpaid", "orange"];
		} else {
			return ["Paid", "green"];
		}
	},
};
