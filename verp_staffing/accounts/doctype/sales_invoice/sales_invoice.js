// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		set_currency_labels(frm);
	},
	onload(frm) {
		set_account_queries(frm);
	},
	validate(frm) {
		console.log("Validating invoice and calculating totals");
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	company(frm) {
		handle_currency_ui(frm);
		handle_discount_account(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
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
		console.log("discount",frm.doc.discount_amount)
		verp_staffing.calculation_engine.calculate_invoice(frm);
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
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	rate(frm, cdt, cdn) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
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
