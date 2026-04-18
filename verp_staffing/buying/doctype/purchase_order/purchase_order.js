// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

// verp_staffing.accounts.taxes.setup_tax_filters("Purchase Taxes and Charges");
// verp_staffing.accounts.taxes.setup_tax_validations("Purchase Order");

frappe.ui.form.on("Purchase Order", {
	company: function (frm) {
		update_company_currency_labels(frm);
		set_account_queries(frm);
		toggle_exchange_rate(frm);
		set_exchange_rate(frm);
	},
	onload: function (frm) {
		set_account_queries(frm);
	},
	currency: function (frm) {
		update_items_currency_labels(frm);
		handle_currency(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	transaction_date: function (frm) {
		set_exchange_rate(frm);
	},
	onload: function (frm) {
		update_items_currency_labels(frm);
		handle_currency(frm);
	},
	items_add: function (frm) {
		update_items_currency_labels(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	items_remove: function (frm) {
		update_items_currency_labels(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	validate(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	conversion_rate: function (frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},

	additional_discount_percentage(frm) {
		let discount_amount = 0;
		discount_amount =
			(flt(frm.doc.total) * flt(frm.doc.additional_discount_percentage || 0)) / 100;

		frm.set_value("discount_amount", discount_amount);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},

	discount_amount(frm) {
		console.log("discount", frm.doc.discount_amount);
		verp_staffing.calculation_engine.calculate_invoice(frm);
		handle_discount_account(frm);
	},
});

function handle_currency(frm) {
	update_currency_labels(frm);
	toggle_exchange_rate(frm);
	set_exchange_rate(frm);
}

function toggle_exchange_rate(frm) {
	const company_currency = frm.doc.company_currency;
	const currency = frm.doc.currency;

	if (!company_currency || !currency) return;

	if (currency === company_currency) {
		frm.set_value("conversion_rate", 1);
		frm.set_df_property("conversion_rate", "hidden", 1);
		frm.set_df_property("conversion_rate", "reqd", 0);
	} else {
		frm.set_df_property("conversion_rate", "hidden", 0);
		frm.set_df_property("conversion_rate", "reqd", 1);
	}
}

async function set_exchange_rate(frm) {
	if (!frm.doc.currency || !frm.doc.company_currency) return;

	if (frm.doc.currency === frm.doc.company_currency) return;

	if (frm.doc.conversion_rate) return; // avoid override

	// error in this auto fetching exchange rate, solve in future
	// let res = await frappe.call({
	//     method: "verp_staffing.utils.accounts.get_exchange_rate",
	//     args: {
	//         from_currency: frm.doc.currency,
	//         to_currency: frm.doc.company_currency,
	//         transaction_date: frm.doc.transaction_date
	//     }
	// });

	// if (res.message) {
	//     frm.set_value("conversion_rate", res.message);
	// }
}

frappe.ui.form.on("Purchase Order Item", {
	item_code: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (!row.item_code) return;

		frappe.db.get_value("Item", row.item_code, ["item_name", "stock_uom"]).then((r) => {
			if (!r.message) return;

			frappe.model.set_value(cdt, cdn, "item_name", r.message.item_name);
			frappe.model.set_value(cdt, cdn, "uom", r.message.stock_uom);

			frappe.model.set_value(cdt, cdn, "qty", 1);
			frappe.model.set_value(cdt, cdn, "rate", 0);
		});
	},

	qty: function (frm, cdt, cdn) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},

	rate: function (frm, cdt, cdn) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
});

frappe.ui.form.on("Purchase Taxes and Charges", {
	charge_type: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (row.charge_type === "Actual") {
			frappe.model.set_value(cdt, cdn, "rate", 0);

			frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn].toggle_editable("rate", false);
			frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn].toggle_editable(
				"tax_amount",
				true,
			);
		} else {
			frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn].toggle_editable("rate", true);
			frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn].toggle_editable(
				"tax_amount",
				false,
			);
		}
	},
	rate(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	tax_amount(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	taxes_add(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	taxes_remove(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	row_id(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
});

function update_currency_labels(frm) {
	let currency = frm.doc.currency || "";

	frm.set_df_property("total", "label", `Total (${currency})`);
	frm.set_df_property("net_total", "label", `Net Total (${currency})`);
	frm.set_df_property("grand_total", "label", `Grand Total (${currency})`);

	frm.refresh_fields();
}

function update_items_currency_labels(frm) {
	let currency = frm.doc.currency || "";
	if (!frm.fields_dict.items) return;
	let grid = frm.fields_dict.items.grid;

	grid.update_docfield_property("rate", "label", `Rate (${currency})`);
	grid.update_docfield_property("amount", "label", `Amount (${currency})`);

	grid.refresh();
}

function update_company_currency_labels(frm) {
	let company_currency = frm.doc.company_currency || "";

	frm.set_df_property("base_total", "label", `Total (${company_currency})`);
	frm.set_df_property("base_net_total", "label", `Net Total (${company_currency})`);
	frm.set_df_property("base_grand_total", "label", `Grand Total (${company_currency})`);

	frm.refresh_fields();
}

function handle_discount_account(frm) {
	if (!frm.doc.company) return;

	if (flt(frm.doc.discount_amount) > 0 && !frm.doc.additional_discount_account) {
		frappe.db.get_value("Company", frm.doc.company, "default_discount_account").then((r) => {
			if (r.message && r.message.default_discount_account) {
				frm.set_value("additional_discount_account", r.message.default_discount_account);
			}
		});
	}
}

function set_account_queries(frm) {

	frm.set_query("expense_account", "items", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__",
				},
			};
		}

		return {
			filters: {
				report_type: "Profit and Loss",
				is_group: 0,
				company: frm.doc.company,
			},
		};
	});

	frm.set_query("account_head", "taxes", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__",
				},
			};
		}

		return {
			filters: {
				account_type: ["in", ["Tax", "Chargeable", "Expense", "Income Account"]],
				is_group: 0,
				company: frm.doc.company,
			},
		};
	});

	frm.set_query("additional_discount_account", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__",
				},
			};
		}

		return {
			filters: {
				company: frm.doc.company,
				is_group: 0,
				report_type: "Profit and Loss",
			},
		};
	});
}
