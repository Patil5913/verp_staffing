// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		set_currency_labels(frm);
		(frm.doc.items || []).forEach((row) => {
			if (!row.type) {
				const type = frm.doctype === "Sales Invoice" ? "Sales" : "Purchase";
				(frm.doc.items || []).forEach((row) => {
					if (!row.type) {
						row.type = frm.doctype === "Sales Invoice" ? "Sales" : "Purchase";
					}
				});
				frm.refresh_field("items");
			}
		});
		if (frm.doc.docstatus === 1 && flt(frm.doc.outstanding_amount) > 0) {
			frm.add_custom_button(
				__("Payment Entry"),
				function () {
					frappe.model.open_mapped_doc({
						method: "verp_staffing.accounts.doctype.payment_entry.payment_entry.make_payment_entry",
						frm: frm,
					});
				},
				__("Create"),
			);
		}
		verp_staffing.purchase.exchange.update_description(frm);
		(frm.doc.taxes || []).forEach((row) =>
			verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, row.doctype, row.name),
		);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
	},

	onload(frm) {
		set_purchase_account_queries(frm);

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

	company(frm) {
		set_currency_labels(frm);
		verp_staffing.purchase.exchange.update_description(frm);
		handle_discount_account(frm);
		if (!frm.doc.company) return;

		set_purchase_account_queries(frm);

		frappe
			.call("verp_staffing.accounts.api.get_defaults.get_default_company_account", {
				company: frm.doc.company,
				fieldname: "default_payable_account",
			})
			.then((r) => {
				if (r.message) {
					frm.set_value("credit_to", r.message);
				}
			});
		if (frm.doc.items && frm.doc.items.length) {
			frappe
				.call("verp_staffing.accounts.api.get_defaults.get_default_company_account", {
					company: frm.doc.company,
					fieldname: "default_expense_account",
				})
				.then((r) => {
					if (r.message) {
						frm.doc.items.forEach((item) => {
							item.expense_account = r.message;
						});
						frm.refresh_field("items");
					}
				});
		}
	},

	currency(frm) {
		set_currency_labels(frm);
		verp_staffing.purchase.exchange.update_description(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
	},

	conversion_rate(frm) {
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

	purchase_order: async function (frm) {
		if (!frm.doc.purchase_order) return;

		const po = await frappe.db.get_doc("Purchase Order", frm.doc.purchase_order);

		// ---------- Parent fields ----------
		frm.set_value("supplier", po.supplier);
		frm.set_value("company", po.company);
		frm.set_value("currency", po.currency);
		frm.set_value("conversion_rate", po.conversion_rate);

		// ---------- Clear tables ----------
		frm.clear_table("items");
		// frm.clear_table("taxes");

		// ---------- Items ----------
		(po.items || []).forEach((row) => {
			let child = frm.add_child("items");

			child.type = "Purchase";
			child.item = row.item;
			child.qty = row.qty;
			child.uom = row.uom;
			child.rate = row.rate;
			child.expense_account = row.expense_account;
		});

		// ---------- Taxes ----------
		(po.taxes || []).forEach((row) => {
			let tax = frm.add_child("taxes");

			Object.assign(tax, row);
		});

		frm.set_value("additional_discount_account", po.additional_discount_account);
		frm.set_value("additional_discount_percentage", po.additional_discount_percentage);
		frm.set_value("discount_amount", po.discount_amount);

		frm.refresh_fields();

		// CRITICAL: wait a tick so model updates settle
		await frappe.after_ajax();

		// ---------- Now calculate ----------
		set_currency_labels(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
});

frappe.ui.form.on("Items Table", {
	item: function (frm, cdt, cdn) {
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

async function set_currency_labels(frm) {
	const currency = frm.doc.currency || "";
	const company_currency = frm.doc.company_currency || "";

	const fields = [
		"total",
		"net_total",
		"grand_total",
		"rounded_total",
		"discount_amount",
		"rounding_adjustment",
		"total_taxes_and_charges",
		"outstanding_amount",
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
		frm.set_df_property(
			field,
			"label",
			`${frm.fields_dict[field].df.label.split(" (")[0]} (${company_currency})`,
		);
	});
}

function set_purchase_account_queries(frm) {
	// store previous company
	let previous_company = frm.doc.company;

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

	// CASH/BANK ACCOUNT
	frm.set_query("cashbank_account", () => {
		if (!frm.doc.company) {
			return { filters: { name: "__invalid__" } };
		}

		return {
			filters: {
				account_type: ["in", ["Cash", "Bank"]],
				is_group: 0,
				company: frm.doc.company,
				report_type: "Balance Sheet",
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

	// handle company change
	frm.fields_dict.company.df.onchange = function () {
		const current_company = frm.doc.company;

		// do nothing if same company
		if (current_company === previous_company) return;

		previous_company = current_company;

		// get company defaults from cache (or fallback null-safe)
		const company_doc = frappe.get_cached_doc("Company", current_company);

		const default_expense_account = company_doc?.default_expense_account || null;

		const default_discount_account = company_doc?.default_discount_account || null;

		// update items table
		(frm.doc.items || []).forEach((row) => {
			frappe.model.set_value(
				row.doctype,
				row.name,
				"expense_account",
				default_expense_account,
			);
		});

		// update taxes table
		(frm.doc.taxes || []).forEach((row) => {
			frappe.model.set_value(row.doctype, row.name, "account_head", null);
		});

		// update main field
		frm.set_value("additional_discount_account", default_discount_account);
	};
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
