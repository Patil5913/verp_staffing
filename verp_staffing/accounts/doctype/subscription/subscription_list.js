frappe.listview_settings["Subscription"] = {
	get_indicator: function (doc) {

		switch (doc.status) {
			case "Trialing":
				return ["Trialing", "blue"];

			case "Active":
				return ["Active", "green"];

			case "Paused":
				return ["Paused", "orange"];

			case "Cancelled":
				return ["Cancelled", "red"];

			case "Completed":
				return ["Completed", "gray"];

			default:
				return ["Unknown", "darkgrey"];
		}
	},
};
