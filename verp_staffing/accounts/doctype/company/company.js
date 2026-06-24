// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company", {
	onload: function (frm) {
		if (frm.doc.__islocal && frm.doc.parent_company) {
			frappe.db.get_value("Company", frm.doc.parent_company, "is_group", (r) => {
				if (!r.is_group) {
					frm.set_value("parent_company", "");
				}
			});
		}
	},
	setup: function (frm) {
		frm.__rename_queue = "long";

		frm.set_query("parent_company", function () {
			return {
				filters: { is_group: 1 },
			};
		});
	},
	country: function (frm) {
		set_chart_of_accounts_options(frm.doc);
	},
	company_name: function (frm) {
		if (frm.doc.__islocal) {
			// add missing " " arg in split method
			let parts = frm.doc.company_name.split(" ");
			let abbr = $.map(parts, function (p) {
				return p ? p.substr(0, 1) : null;
			}).join("");
			frm.set_value("abbr", abbr);
		}
	},
	parent_company: function (frm) {
		var bool = frm.doc.parent_company ? true : false;
		frm.set_value("create_chart_of_accounts_based_on", bool ? "Existing Company" : "");
		frm.set_value("existing_company", bool ? frm.doc.parent_company : "");
		disbale_coa_fields(frm, bool);
	},
	date_of_commencement: function (frm) {
		if (frm.doc.date_of_commencement < frm.doc.date_of_incorporation) {
			frappe.throw(__("Date of Commencement should be greater than Date of Incorporation"));
		}
		if (!frm.doc.date_of_commencement) {
			frm.doc.date_of_incorporation = "";
		}
	},
	refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Accounting",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();
		frm.toggle_display("address_html", !frm.is_new());
		setup_queries(frm);

		if (!frm.is_new()) {
			frm.doc.abbr && frm.set_df_property("abbr", "read_only", 1);
			disbale_coa_fields(frm);
			frappe.contacts.render_address_and_contact(frm);
			if (frappe.perm.has_perm("Account", 0, "read")) {
				frm.add_custom_button(
					__("Chart of Accounts"),
					function () {
						// Step 1: manually set route options
						frappe.route_options = {
							company: frm.doc.name,
						};
						// Step 2: navigate
						frappe.set_route("Tree", "Account");
					},
					__("View"),
				);
			}
		}
		set_chart_of_accounts_options(frm.doc);

				frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Company";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
	},
});

let disbale_coa_fields = function (frm, bool = true) {
	frm.set_df_property("create_chart_of_accounts_based_on", "read_only", bool);
	frm.set_df_property("chart_of_accounts", "read_only", bool);
	frm.set_df_property("existing_company", "read_only", bool);
};

const set_chart_of_accounts_options = function (doc) {
	var selected_value = doc.chart_of_accounts;
	if (doc.country) {
		return frappe.call({
			method: "verp_staffing.accounts.doctype.account.charts_of_accounts.charts_of_accounts.get_charts_for_country",
			args: {
				country: doc.country,
				with_standard: true,
			},
			callback: function (r) {
				if (!r.exc) {
					set_field_options("chart_of_accounts", [""].concat(r.message).join("\n"));
					if (in_list(r.message, selected_value))
						cur_frm.set_value("chart_of_accounts", selected_value);
				}
			},
		});
	}
};

const setup_queries = function (frm) {
	$.each(
		[
			["default_bank_account", { account_type: "Bank" }],
			["default_cash_account", { account_type: "Cash" }],
			["default_receivable_account", { root_type: "Asset", account_type: "Receivable" }],
			["default_payable_account", { root_type: "Liability", account_type: "Payable" }],
			["default_expense_account", { root_type: "Expense", account_type: "Expense Account" }],
			["default_income_account", { root_type: "Income", account_type: "Income Account" }],
			["round_off_account", { root_type: "Expense" }],
			["write_off_account", { root_type: "Expense" }],
			["default_discount_account", {}],
		],
		function (i, v) {
			set_custom_query(frm, v);
		},
	);

	if (frm.doc.enable_perpetual_inventory) {
		$.each(
			[
				[
					"stock_adjustment_account",
					{ root_type: "Expense", account_type: "Stock Adjustment" },
				],
				[
					"expenses_included_in_valuation",
					{ root_type: "Expense", account_type: "Expenses Included in Valuation" },
				],
				[
					"stock_received_but_not_billed",
					{ root_type: "Liability", account_type: "Stock Received But Not Billed" },
				],
				[
					"service_received_but_not_billed",
					{ root_type: "Liability", account_type: "Service Received But Not Billed" },
				],
			],
			function (i, v) {
				set_custom_query(frm, v);
			},
		);
	}
};

const set_custom_query = function (frm, v) {
	var filters = {
		company: frm.doc.name,
		is_group: 0,
	};

	for (var key in v[1]) {
		filters[key] = v[1][key];
	}

	frm.set_query(v[0], function () {
		return {
			filters: filters,
		};
	});
};
