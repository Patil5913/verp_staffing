// namespace safety
window.verp_staffing = window.verp_staffing || {};
verp_staffing.purchase = {};

// ---------------- ITEM HANDLER ----------------
verp_staffing.purchase.item_handler = async function (frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.item) return;

	const item = await frappe.db.get_doc("Item", row.item);

	if (item) {
		frappe.model.set_value(cdt, cdn, "item_name", item.item_name);
		frappe.model.set_value(cdt, cdn, "uom", item.stock_uom);
		frappe.model.set_value(cdt, cdn, "qty", 1);
	}

	// expense account
	if (frm.doc.company) {
		const r = await frappe.db.get_value("Company", frm.doc.company, "default_expense_account");

		if (r.message?.default_expense_account) {
			frappe.model.set_value(cdt, cdn, "expense_account", r.message.default_expense_account);
		}
	}
};

verp_staffing.purchase.tax = {};

verp_staffing.purchase.tax.toggle_rate_amount_fields = function (frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const grid_row = frm.fields_dict["taxes"]?.grid?.grid_rows_by_docname?.[cdn];

	if (!grid_row) return;

	if (row.charge_type === "Actual") {
		frappe.model.set_value(cdt, cdn, "rate", 0);

		grid_row.toggle_editable("rate", false);
		grid_row.toggle_editable("tax_amount", true);
	} else {
		grid_row.toggle_editable("rate", true);
		grid_row.toggle_editable("tax_amount", false);
	}
};

verp_staffing.purchase.items = {};

verp_staffing.purchase.items.update_items_currency_labels = function (frm) {
	const currency = frm.doc.currency || "";
	if (!frm.fields_dict.items) return;

	const grid = frm.fields_dict.items.grid;

	grid.update_docfield_property("rate", "label", `Rate (${currency})`);
	grid.update_docfield_property("amount", "label", `Amount (${currency})`);

	grid.refresh();
};

verp_staffing.purchase.exchange = {};

verp_staffing.purchase.exchange.update_description = function (frm) {
	const currency = frm.doc.currency;
	const company_currency = frm.doc.company_currency;
	const rate = frm.doc.conversion_rate;

	if (!currency || !company_currency) {
		frm.set_df_property("conversion_rate", "description", "");
		return;
	}

	if (currency === company_currency) {
		frm.set_df_property("conversion_rate", "description", "Same currency, rate = 1");
		return;
	}

	let text = `1 ${currency} = ${rate || "?"} ${company_currency}`;

	if (rate) {
		let inverse = (1 / rate).toFixed(6);
		text += ` | 1 ${company_currency} = ${inverse} ${currency}`;
	}

	frm.set_df_property("conversion_rate", "description", text);
};