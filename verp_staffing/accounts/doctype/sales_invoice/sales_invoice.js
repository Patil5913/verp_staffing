// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// handle_currency_ui(frm);
		// calculate_invoice(frm);
		set_currency_labels(frm);
	},
	onload(frm) {
		set_account_queries(frm);
	},
	validate(frm) {
		calculate_invoice(frm);
	},
	company(frm) {
		handle_currency_ui(frm);
		handle_discount_account(frm);
		calculate_invoice(frm);
		set_account_queries(frm);
		if (!frm.doc.company) return;

		frappe.call({
			method: "verp_staffing.accounts.doctype.company.company.get_company_receivable_account",
			args: {
				company: frm.doc.company,
			},
			callback(r) {
				if (r.message) {
					frm.set_value("debit_to", r.message);
				}
			},
		});
	},
	currency(frm) {
		handle_currency_ui(frm);
		set_currency_labels(frm);
	},
	conversion_rate(frm) {
		calculate_invoice(frm);
	},
	additional_discount_percentage(frm) {
		console.log(
			"Calculating discount amount based on percentage...",
			frm.doc.additional_discount_percentage,
		);
		let discount_on = frm.doc.apply_discount_on;
		let discount_amount = 0;
		if (discount_on === "Net Total") {
			discount_amount =
				(flt(frm.doc.net_total) * flt(frm.doc.additional_discount_percentage || 0)) / 100;
		} else if (discount_on === "Grand Total") {
			discount_amount =
				(flt(frm.doc.grand_total) * flt(frm.doc.additional_discount_percentage || 0)) /
				100;
		}
		frm.set_value("discount_amount", discount_amount);
	},
	discount_amount(frm) {
		calculate_invoice(frm);
		handle_discount_account(frm);
	},
});

frappe.ui.form.on("Sales Invoice Item", {
	item: async function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		// Fetch item_name directly
		const item = await frappe.db.get_doc("Item", row.item);

		if (item) {
			frappe.model.set_value(cdt, cdn, "item_name", item.item_name);
			frappe.model.set_value(cdt, cdn, "uom", item.stock_uom);
			frappe.model.set_value(cdt, cdn, "qty", 1);
		}

		if (frm.doc.company) {
			frappe.call({
				method: "verp_staffing.accounts.api.get_defaults.get_default_income_account",
				args: {
					company: frm.doc.company,
				},
				callback(r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, "income_account", r.message);
					}
				},
			});
		}
	},
	qty(frm, cdt, cdn) {
		calculate_amount(frm, cdt, cdn);
		calculate_invoice(frm);
	},
	rate(frm, cdt, cdn) {
		calculate_invoice(frm);
		calculate_amount(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Sales Taxes and Charges", {
	charge_type(frm, cdt, cdn) {
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
		calculate_invoice(frm);
	},
	tax_amount(frm) {
		calculate_invoice(frm);
	},
	taxes_add(frm) {
		calculate_invoice(frm);
	},
	taxes_remove(frm) {
		calculate_invoice(frm);
	},
});

function calculate_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	if (row.qty != null && row.rate != null) {
		const amount = flt(row.qty) * flt(row.rate);
		frappe.model.set_value(cdt, cdn, "amount", amount);
	}
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
	const fields = ["base_total", "base_net_total", "base_grand_total", "base_rounded_total"];

	fields.forEach((f) => {
		frm.set_df_property(f, "hidden", show ? 0 : 1);
		if (show) {
			frm.set_value(f, 0);
		}
	});
}

function calculate_invoice(frm) {
	if (!frm.doc.items || frm.doc.items.length === 0) return;

	// STEP 1: Items + Net Total
	let net_total = 0;
	let total_qty = 0;
	frm.doc.items.forEach((row) => {
		const amount = flt(row.qty) * flt(row.rate);
		row.amount = amount;
		net_total += amount;
		total_qty += flt(row.qty);
	});

	frm.set_value("total", net_total);
	frm.set_value("net_total", net_total);
	frm.set_value("total_qty", total_qty);

	// STEP 2: Taxes
	calculate_taxes(frm);

	// STEP 3: Discount handling
	apply_discount(frm);

	// STEP 4: Base currency
	calculate_base_totals(frm);

	// STEP 5: Rounding
	calculate_rounding(frm);

	frm.refresh_field("items");
	frm.refresh_field("taxes");
}

function calculate_taxes(frm) {
	let net_total = flt(frm.doc.net_total);
	let cumulative_total = net_total;

	(frm.doc.taxes || []).forEach((tax, i) => {
		let tax_amount = 0;

		// CASE 1: Actual
		if (tax.charge_type === "Actual") {
			tax_amount = flt(tax.tax_amount || 0);
		}

		// CASE 2: On Net Total
		else if (tax.charge_type === "On Net Total") {
			tax_amount = (net_total * flt(tax.rate)) / 100;
		}

		// CASE 3: On Previous Row Amount
		else if (tax.charge_type === "On Previous Row Amount") {
			let prev = frm.doc.taxes[i - 1];
			if (!prev) {
				frappe.throw("Previous row not found for tax calculation");
			}
			tax_amount = (flt(prev.tax_amount) * flt(tax.rate)) / 100;
		}

		// CASE 4: On Previous Row Total
		else if (tax.charge_type === "On Previous Row Total") {
			let prev = frm.doc.taxes[i - 1];
			if (!prev) {
				frappe.throw("Previous row not found for tax calculation");
			}
			tax_amount = (flt(prev.total) * flt(tax.rate)) / 100;
		}

		// CASE 5: On Item Quantity
		else if (tax.charge_type === "On Item Quantity") {
			let total_qty = 0;
			frm.doc.items.forEach((item) => {
				total_qty += flt(item.qty);
			});
			tax_amount = total_qty * flt(tax.rate);
		}
		tax.tax_amount = tax_amount;

		// 🔥 CRITICAL: cumulative total
		cumulative_total += tax_amount;
		tax.total = cumulative_total;
	});

	frm.set_value("total_taxes_and_charges", cumulative_total - net_total);
	frm.set_value("grand_total", cumulative_total);
}

function apply_discount(frm) {
	let discount = flt(frm.doc.discount_amount || 0);

	if (!discount) return;

	let grand_total = flt(frm.doc.grand_total);

	if (frm.doc.apply_discount_on === "Grand Total") {
		let ratio = (grand_total - discount) / grand_total;

		// Adjust net total
		let new_net_total = flt(frm.doc.net_total) * ratio;
		frm.set_value("net_total", new_net_total);

		// Adjust taxes
		(frm.doc.taxes || []).forEach((tax) => {
			tax.tax_amount = flt(tax.tax_amount) * ratio;
		});

		// Recalculate taxes again (important)
		calculate_taxes(frm);
	} else if (frm.doc.apply_discount_on === "Net Total") {
		let new_net_total = flt(frm.doc.net_total) - discount;
		frm.set_value("net_total", new_net_total);

		calculate_taxes(frm);
	}
}

function calculate_base_totals(frm) {
	let rate = flt(frm.doc.conversion_rate || 1);

	frm.set_value("base_total", flt(frm.doc.total) * rate);
	frm.set_value("base_net_total", flt(frm.doc.net_total) * rate);
	frm.set_value("base_grand_total", flt(frm.doc.grand_total) * rate);
	frm.set_value(
		"base_total_taxes_and_charges",
		flt(frm.doc.total_taxes_and_charges) * flt(frm.doc.conversion_rate || 1),
	);
}

function set_account_queries(frm) {
	frm.set_query("debit_to", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__", // 🔥 returns nothing
				},
			};
		}

		return {
			filters: {
				account_type: "Receivable",
				is_group: 0,
				company: frm.doc.company,
			},
		};
	});

	frm.set_query("income_account", "items", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__",
				},
			};
		}

		return {
			filters: {
				account_type: ["in", ["Income", "Income Account"]],
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
				account_type: ["in", ["Tax", "Chargeable", "Expense"]],
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

function calculate_rounding(frm) {
	if (frm.doc.disable_rounded_total) {
		frm.set_value("rounded_total", frm.doc.grand_total);
		frm.set_value("rounding_adjustment", 0);
		frm.set_value("base_rounded_total", frm.doc.base_grand_total);
		return;
	}

	let grand_total = flt(frm.doc.grand_total);

	let rounded = Math.round(grand_total);

	let adjustment = rounded - grand_total;

	frm.set_value("rounded_total", rounded);
	frm.set_value("rounding_adjustment", adjustment);

	let rate = flt(frm.doc.conversion_rate || 1);

	frm.set_value("base_rounded_total", rounded * rate);

	frm.set_value("outstanding_amount", rounded);
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
