// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		set_currency_labels(frm);
		(frm.doc.taxes || []).forEach((row) =>
			toogle_rate_amount_fields(frm, row.doctype, row.name),
		);
	},
	onload(frm) {
		set_purchase_account_queries(frm);
	},
	validate(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	company(frm) {
		handle_currency_ui(frm);
		handle_discount_account(frm);
		if (!frm.doc.company) return;

		set_purchase_account_queries(frm);

		frappe.db.get_value("Company", frm.doc.company, "default_payable_account").then((r) => {
			if (r.message && r.message.default_payable_account) {
				frm.set_value("credit_to", r.message.default_payable_account);
			}
		});
		if (frm.doc.items && frm.doc.items.length) {
			frappe.db
				.get_value("Company", frm.doc.company, "default_expense_account")
				.then((r) => {
					if (!r.message.default_expense_account) {
						frappe.throw("Default Company Expense Account not set");
					}
					if (r.message && r.message.default_expense_account) {
						frm.doc.items.forEach((item) => {
							item.expense_account = r.message.default_expense_account;
						});
						frm.refresh_field("items");
					}
				});
		}
	},
	currency(frm) {
		handle_currency_ui(frm);
		set_currency_labels(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	conversion_rate(frm) {
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
		verp_staffing.calculation_engine.calculate_invoice(frm);
		handle_discount_account(frm);
	},
	supplier(frm) {
		if (!frm.doc.supplier) return;

		frappe.db.get_value("Supplier", frm.doc.supplier, "supplier_name").then((r) => {
			frm.set_value("supplier_name", r.message.supplier_name);
		});
	},
});

frappe.ui.form.on("Purchase Invoice Item", {
	item: async function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		const item = await frappe.db.get_doc("Item", row.item);

		if (item) {
			console.log("set values");
			frappe.model.set_value(cdt, cdn, "item_name", item.item_name);
			frappe.model.set_value(cdt, cdn, "uom", item.stock_uom);
			frappe.model.set_value(cdt, cdn, "qty", 1);
		}

		// AUTO EXPENSE ACCOUNT
		if (frm.doc.company) {
			frappe.db
				.get_value("Company", frm.doc.company, "default_expense_account")
				.then((r) => {
					if (r.message && r.message.default_expense_account) {
						frappe.model.set_value(
							cdt,
							cdn,
							"expense_account",
							r.message.default_expense_account,
						);
					}
				});
		}
	},
	items_add: function (frm) {
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

frappe.ui.form.on("Purchase Taxes and Charges", {
	refresh(frm) {
		(frm.doc.taxes || []).forEach((row) =>
			toogle_rate_amount_fields(frm, row.doctype, row.name),
		);
	},
	charge_type(frm, cdt, cdn) {
		toogle_rate_amount_fields(frm, cdt, cdn);
	},
	rate(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	tax_amount(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	taxes_add(frm, cdt, cdn) {
		toogle_rate_amount_fields(frm, cdt, cdn);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	taxes_remove(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	row_id(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
});

function toogle_rate_amount_fields(frm, cdt, cdn) {
	console.log("frm, cdt, cdn: ", frm, cdt, cdn);
	const row = locals[cdt][cdn];
	const grid_row = frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn];
	console.log("grid_row: ", grid_row);
	if (!grid_row) return;

	if (row.charge_type === "Actual") {
		frappe.model.set_value(cdt, cdn, "rate", 0);

		grid_row.toggle_editable("rate", false);
		grid_row.toggle_editable("tax_amount", true);
	} else {
		grid_row.toggle_editable("rate", true);
		grid_row.toggle_editable("tax_amount", false);
	}
}

async function set_currency_labels(frm) {
	const currency = frm.doc.currency || "";
	const company_currency =
		(await frappe.db.get_value("Company", frm.doc.company, "default_currency")) || "";

	const fields = [
		"total",
		"net_total",
		"grand_total",
		"rounded_total",
		"discount_amount",
		"rounding_adjustment",
		"total_taxes_and_charges",
	];
	fields.forEach((field) => {
		frm.set_df_property(
			field,
			"label",
			`${frm.fields_dict[field].df.label.split(" (")[0]} (${currency})`,
		);
	});
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
		if (
			currency &&
			company_currency &&
			currency !== company_currency.message.default_currency
		) {
			console.log(
				"Different currency, showing conversion rate and company currency fields",
				currency,
				company_currency.message.default_currency,
			);
			frm.set_df_property(field, "hidden", false);
		} else {
			frm.set_df_property(field, "hidden", true);
		}

		frm.set_df_property(
			field,
			"label",
			`${frm.fields_dict[field].df.label.split(" (")[0]} (${company_currency.message.default_currency})`,
		);
	});
}

function handle_currency_ui(frm) {
	if (!frm.doc.company || !frm.doc.currency) return;

	frappe.call({
		method: "verp_staffing.accounts.doctype.company.company.get_company_currency",
		args: { company: frm.doc.company },
		callback(r) {
			const company_currency = r.message;

			if (!company_currency) return;

			if (frm.doc.currency === company_currency) {
				// Same currency
				frm.set_value("conversion_rate", 1);

				frm.set_df_property("conversion_rate", "hidden", 1);
				frm.set_df_property("conversion_rate", "reqd", 0);

				toggle_base_fields(frm, false);
			} else {
				// Different currency
				frm.set_df_property("conversion_rate", "hidden", 0);
				frm.set_df_property("conversion_rate", "reqd", 1);

				toggle_base_fields(frm, true);
			}
		},
	});
}

function toggle_base_fields(frm, show) {
	const fields = [
		"base_total",
		"base_net_total",
		"base_grand_total",
		"base_rounded_total",
		"base_discount_amount",
	];

	fields.forEach((f) => {
		frm.set_df_property(f, "hidden", show ? 0 : 1);
		if (show) {
			frm.set_value(f, 0);
		}
	});
}

function set_purchase_account_queries(frm) {
	// CREDIT TO (Payable)
	frm.set_query("credit_to", () => {
		if (!frm.doc.company) {
			return { filters: { name: "__invalid__" } };
		}

		return {
			filters: {
				account_type: "Payable",
				is_group: 0,
				company: frm.doc.company,
			},
		};
	});

	// EXPENSE ACCOUNT (items)
	frm.set_query("expense_account", "items", () => {
		if (!frm.doc.company) {
			return { filters: { name: "__invalid__" } };
		}

		return {
			filters: {
				account_type: ["in", ["Expense Account", "Cost of Goods Sold"]],
				is_group: 0,
				company: frm.doc.company,
			},
		};
	});

	// TAX ACCOUNT
	frm.set_query("account_head", "taxes", () => {
		if (!frm.doc.company) {
			return { filters: { name: "__invalid__" } };
		}

		return {
			filters: {
				account_type: ["in", ["Tax", "Chargeable", "Expense"]],
				is_group: 0,
				company: frm.doc.company,
			},
		};
	});

	// DISCOUNT ACCOUNT
	frm.set_query("additional_discount_account", () => {
		if (!frm.doc.company) {
			return { filters: { name: "__invalid__" } };
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
