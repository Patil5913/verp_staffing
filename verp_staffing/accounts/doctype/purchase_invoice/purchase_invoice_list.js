frappe.listview_settings["Purchase Invoice"] = {
	get_indicator: function (doc) {

		let today = frappe.datetime.get_today();

		if (doc.outstanding_amount < 0) {
			return ["Debit Note Issued", "gray"];

		} else if (doc.outstanding_amount == 0) {
			return ["Paid", "green"];

		} else if (doc.outstanding_amount > 0 && doc.due_date && doc.due_date < today) {
			return ["Overdue", "red"];

		} else if (doc.outstanding_amount > 0 && doc.outstanding_amount < doc.rounded_total) {
			return ["Partly Paid", "blue"];

		} else {
			return ["Unpaid", "orange"];
		}
	},
};
