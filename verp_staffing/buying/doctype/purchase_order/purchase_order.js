// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		frm.set_query("item", "items", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];

			const selected_items = (doc.items || [])
				.filter((d) => d.item && d.name !== row.name)
				.map((d) => d.item);

			return {
				filters: [["Item", "name", "not in", selected_items]],
			};
		});
	},
	refresh: function (frm) {
		verp_staffing.purchase.exchange.update_description(frm);
		handle_currency(frm);
		(frm.doc.taxes || []).forEach((row) =>
			verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, row.doctype, row.name),
		);
		verp_staffing.calculation_engine.handle_rounded_total(frm);

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Purchase Order";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
	},

	onload: function (frm) {
		set_account_queries(frm);
		if (!frm.doc.company) {
			frappe.call({
				method: "verp_staffing.accounts.doctype.company.company.fetch_default_company",
				callback(r) {
					if (r.message) {
						frm.set_value("company", r.message);
					}
				},
			});
		}
	},

	validate(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},

	company: function (frm) {
		update_company_currency_labels(frm);
		verp_staffing.purchase.exchange.update_description(frm);
		set_exchange_rate(frm);

		handle_discount_account(frm);
		if (!frm.doc.company) return;
		set_account_queries(frm);

		if (frm.doc.items && frm.doc.items.length) {
			frappe
				.call("verp_staffing.accounts.api.get_defaults.get_default_company_account", {
					company: frm.doc.company,
					fieldname: "default_expense_account",
				})
				.then((r) => {
					if (r.message && r.message) {
						frm.doc.items.forEach((item) => {
							item.expense_account = r.message;
						});
						frm.refresh_field("items");
					}
				});
		}
	},

	currency: function (frm) {
		update_company_currency_labels(frm);
		verp_staffing.purchase.items.update_items_currency_labels(frm);
		verp_staffing.purchase.exchange.update_description(frm);
		handle_currency(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
	},

	conversion_rate: function (frm) {
		verp_staffing.purchase.exchange.update_description(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
	},

	additional_discount_percentage(frm) {
		let discount_amount = 0;
		discount_amount =
			(flt(frm.doc.total) * flt(frm.doc.additional_discount_percentage || 0)) / 100;

		frm.set_value("discount_amount", discount_amount);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},

	discount_amount(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
		handle_discount_account(frm);
	},
});

function handle_currency(frm) {
	update_currency_labels(frm);
	set_exchange_rate(frm);
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

frappe.ui.form.on("Items Table", {
	item: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		row.type = "Purchase";
		frm.refresh_field("items");
		verp_staffing.purchase.item_handler(frm, cdt, cdn);
	},
	items_add: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		row.type = "Purchase";
		frm.refresh_field("items");
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	items_remove: function (frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	qty(frm, cdt, cdn) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	rate(frm, cdt, cdn) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
});

frappe.ui.form.on("Taxes and Charges", {
	refresh(frm) {
		(frm.doc.taxes || []).forEach((row) =>
			verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, row.doctype, row.name),
		);
	},
	charge_type(frm, cdt, cdn) {
		verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, cdt, cdn);
	},
	rate(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	tax_amount(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	taxes_add(frm, cdt, cdn) {
		verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, cdt, cdn);
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
	const currency = frm.doc.currency || "";

	frm.set_df_property("total", "label", `Total (${currency})`);
	frm.set_df_property("net_total", "label", `Net Total (${currency})`);
	frm.set_df_property("grand_total", "label", `Grand Total (${currency})`);
	frm.set_df_property("rounding_adjustment", "label", `Rounding Adjustment (${currency})`);
	frm.set_df_property("rounded_total", "label", `Rounded Total (${currency})`);
	frm.set_df_property("discount_amount", "label", `Additional Discount Ammount (${currency})`);

	frm.refresh_fields();
}

function update_company_currency_labels(frm) {
	const company_currency = frm.doc.company_currency || "";

	const company_currency_field = [
		"base_total",
		"base_net_total",
		"base_grand_total",
		"base_rounded_total",
		"base_rounding_adjustment",
		"base_total_taxes_and_charges",
		"base_in_words",
		"base_discount_amount",
	];
	company_currency_field.forEach((field) => {
		frm.set_df_property(
			field,
			"label",
			`${frm.fields_dict[field].df.label.split(" (")[0]} (${company_currency})`,
		);
	});
}

function handle_discount_account(frm) {
	if (!frm.doc.company) return;

	if (flt(frm.doc.discount_amount) > 0 && !frm.doc.additional_discount_account) {
		frappe
			.call("verp_staffing.accounts.api.get_defaults.get_default_company_account", {
				company: frm.doc.company,
				fieldname: "default_discount_account",
			})
			.then((r) => {
				if (r.message) {
					frm.set_value("additional_discount_account", r.message);
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
