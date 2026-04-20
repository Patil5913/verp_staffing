// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

// verp_staffing.accounts.taxes.setup_tax_filters("Purchase Taxes and Charges");
// verp_staffing.accounts.taxes.setup_tax_validations("Purchase Order");

frappe.ui.form.on("Purchase Order", {
	company: function (frm) {
		update_company_currency_labels(frm);
		toggle_exchange_rate(frm);
		set_exchange_rate(frm);
	},
	currency: function (frm) {
		update_items_currency_labels(frm)
		handle_currency(frm)
	},
	transaction_date: function (frm) {
		set_exchange_rate(frm);
	},
	onload: function (frm) {
		update_items_currency_labels(frm)
		handle_currency(frm)
	},
	items_add: function (frm) {
		update_items_currency_labels(frm)
		calculate_totals(frm);
	},
	items_remove: function (frm) {
		update_items_currency_labels(frm)
		calculate_totals(frm);
	},
	validate: function (frm) {
		calculate_totals(frm);
	},
	conversion_rate: function (frm) {
		calculate_totals(frm);
	},

	additional_discount_percentage(frm) {
        verp_staffing.accounts.taxes.recalculate_taxes(frm);
    },

    discount_amount(frm) {
        verp_staffing.accounts.taxes.recalculate_taxes(frm);
    },

    apply_discount_on(frm) {
        verp_staffing.accounts.taxes.recalculate_taxes(frm);
    }
	
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

			update_row_amount(frm, cdt, cdn);
		});
	},

	qty: function (frm, cdt, cdn) {
		update_row_amount(frm, cdt, cdn);
	},

	rate: function (frm, cdt, cdn) {
		update_row_amount(frm, cdt, cdn);
	}
});

function update_row_amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    let amount = flt(row.qty) * flt(row.rate);

    frappe.model.set_value(cdt, cdn, "amount", amount);

    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total = 0;

    (frm.doc.items || []).forEach((row) => {
        total += flt(row.amount);
    });

    frm.set_value("total", total);
    frm.set_value("net_total", total);
    frm.set_value("grand_total", total);

    let conversion_rate = flt(frm.doc.conversion_rate) || 1;

    frm.set_value("base_total", total * conversion_rate);
    frm.set_value("base_net_total", total * conversion_rate);
    frm.set_value("base_grand_total", total * conversion_rate);
}

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