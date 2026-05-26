frappe.listview_settings["Payment Entry"] = {
	add_fields: ["verification_status", "payment_term_row"],
	get_indicator(doc) {
		// Show verification status if payment_term_row exists
		if (doc.payment_term_row) {
			const colors = {
				"Pending Verification": "orange",
				Verified: "green",
				Rejected: "red",
			};

			return [
				__(doc.verification_status),
				colors[doc.verification_status] || "gray",
				`verification_status,=,${doc.verification_status}`,
			];
		} else {
			// Default Frappe docstatus indicators
			if (doc.docstatus === 0) {
				return [__("Draft"), "red", "docstatus,=,0"];
			}

			if (doc.docstatus === 1) {
				return [__("Submitted"), "green", "docstatus,=,1"];
			}

			if (doc.docstatus === 2) {
				return [__("Cancelled"), "gray", "docstatus,=,2"];
			}
		}
	},
};
