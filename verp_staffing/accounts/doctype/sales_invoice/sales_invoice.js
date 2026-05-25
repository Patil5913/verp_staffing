// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Receivables",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();

		set_currency_labels(frm);
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Send Invoice"),
				function () {
					frappe.confirm("Send Sales Invoice email to customer?", function () {
						frappe.call({
							method: "verp_staffing.accounts.doctype.sales_invoice.sales_invoice.send_sales_invoice_email",
							args: { doc: frm.doc.name },
							callback(r) {
								if (!r.exc) {
									frappe.msgprint("Invoice sent successfully.");
								}
							},
						});
					});
				},
				__("Email"),
			);
		}
		(frm.doc.items || []).forEach((row) => {
			if (!row.type) {
				const type = frm.doctype === "Sales Invoice" ? "Sales" : "Purchase";
				frappe.model.set_value(row.doctype, row.name, "type", type);
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
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Send Invoice"),
				function () {
					frappe.confirm("Send Sales Invoice email to customer?", function () {
						frappe.call({
							method: "verp_staffing.accounts.doctype.sales_invoice.sales_invoice.send_sales_invoice_email",
							args: { doc: frm.doc.name },
							callback(r) {
								if (!r.exc) {
									frappe.msgprint("Invoice sent successfully.");
								}
							},
						});
					});
				},
				__("Email"),
			);
		}
	},
	onload(frm) {
		set_currency_labels(frm);
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
	after_save(frm) {
		frm.set_value("in_words", frm.doc.in_words);
		frm.set_value("base_in_words", frm.doc.base_in_words);
	},
	validate(frm) {
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

		if (frm.doc.items && frm.doc.items.length) {
			frappe.db.get_value("Company", frm.doc.company, "default_income_account").then((r) => {
				if (r.message && r.message.default_income_account) {
					frm.doc.items.forEach((item) => {
						item.income_account = r.message.default_income_account;
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
	disable_rounded_total(frm) {
		verp_staffing.calculation_engine.calculate_rounding(frm);
	},
});

frappe.ui.form.on("Items Table", {
	item: async function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.item) return;

		row.type = "Sales";

		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Item",
				filter: { name: row.item },
				fieldname: ["stock_uom"],
			},
			callback: function (r) {
				if (r.message) {
					frappe.model.set_value(
						cdt,
						cdn,
						"uom",
						r.message.stock_uom ?? r.message.stock_uom,
					);
				}
			},
		});
		row.qty = 1;

		frm.refresh_field("items");

		if (frm.doc.company) {
			frappe.db.get_value("Company", frm.doc.company, "default_income_account").then((r) => {
				if (r.message?.default_income_account) {
					row.income_account = r.message.default_income_account;

					frm.refresh_field("items");
				}
			});
		}
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	items_add: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		row.type = "Sales";
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

	const company_currency = frm.doc.company_currency;

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

function set_account_queries(frm) {
	// store previous company
	let previous_company = frm.doc.company;

	frm.set_query("debit_to", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__", // returns nothing
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

	// handle company change
	frm.fields_dict.company.df.onchange = function () {
		const current_company = frm.doc.company;

		// do nothing if same company
		if (current_company === previous_company) return;

		previous_company = current_company;

		// get company defaults from cache (or fallback null-safe)
		const company_doc = frappe.get_cached_doc("Company", current_company);

		const default_income_account = company_doc?.default_income_account || null;

		const default_discount_account = company_doc?.default_discount_account || null;

		// update items table
		(frm.doc.items || []).forEach((row) => {
			frappe.model.set_value(
				row.doctype,
				row.name,
				"income_account",
				default_income_account,
			);
		});

		// update taxes table
		(frm.doc.taxes || []).forEach((row) => {
			frappe.model.set_value(row.doctype, row.name, "account_head", null);
		});

		// update main field
		frm.set_value("additional_discount_account", default_discount_account);
		frm.set_value("debit_to", null);
	};
}

function set_currency_labels(frm) {
	const currency = frm.doc.currency || "";
	const company_currency = frm.doc.company_currency;

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
		if (currency && company_currency && currency !== company_currency) {
			frm.set_df_property(field, "hidden", false);
		} else {
			frm.set_df_property(field, "hidden", true);
		}

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
		frappe.db.get_value("Company", frm.doc.company, "default_discount_account").then((r) => {
			if (r.message && r.message.default_discount_account) {
				frm.set_value("additional_discount_account", r.message.default_discount_account);
			}
		});
	}
}
