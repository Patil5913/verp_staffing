// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Supplier", {
	setup: function (frm) {

		frm.set_query("default_bank_account", function () {
			return {
				filters: {
					is_company_account: 1,
				},
			};
		});

		frm.make_methods = {
			"Bank Account": () => verp_staffing.purchase.make_bank_account(frm.doc.doctype, frm.doc.name),
		};
	},

	refresh: function (frm) {

		if (!frm.doc.__islocal) {
            // don't remove it's for future
            
			// custom buttons 
			// frm.add_custom_button(
			// 	__("Accounting Ledger"),
			// 	function () {
			// 		frappe.set_route("query-report", "General Ledger", {
			// 			party_type: "Supplier",
			// 			party: frm.doc.name,
			// 			party_name: frm.doc.supplier_name,
			// 		});
			// 	},
			// 	__("View")
			// );

			// frm.add_custom_button(
			// 	__("Accounts Payable"),
			// 	function () {
			// 		frappe.set_route("query-report", "Accounts Payable", {
			// 			party_type: "Supplier",
			// 			party: frm.doc.name,
			// 		});
			// 	},
			// 	__("View")
			// );

			frm.add_custom_button(__("Bank Account"), () => frm.make_methods["Bank Account"](), __("Create"));

			// // indicators
			// erpnext.utils.set_party_dashboard_indicators(frm);
		}

		frm.set_query("supplier_group", () => {
			return {
				filters: {
					is_group: 0,
				},
			};
		});
	},
});

