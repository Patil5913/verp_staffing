frappe.listview_settings["Sales Invoice"] = {
	get_indicator: function (doc) {

		let today = frappe.datetime.get_today();

		if (doc.outstanding_amount < 0) {
			return ["Credit Note Issued", "gray"];

		} else if (doc.outstanding_amount == 0) {
			return ["Paid", "green"];

		} else if (doc.outstanding_amount > 0 && doc.due_date && doc.due_date < today) {
			return ["Overdue", "red"];

		} else if (doc.outstanding_amount > 0 && doc.outstanding_amount < doc.grand_total) {
			return ["Partially Paid", "blue"];

		} else {
			return ["Unpaid", "orange"];
		}
	},
};
