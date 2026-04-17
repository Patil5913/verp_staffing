// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("GL Entry", {
	refresh: function (frm) {
		frm.page.btn_secondary.hide();
		set_currency_labels(frm);
	},
});

async function set_currency_labels(frm) {
	const currency = frm.doc.transaction_currency || "";
	const company_currency =
		(await frappe.db.get_value("Company", frm.doc.company, "default_currency")) || "";

	if (currency && company_currency && currency !== company_currency.message.default_currency) {
		frm.set_df_property("conversion_rate", "hidden", false);
	} else {
		frm.set_df_property("conversion_rate", "hidden", true);
	}

	const fields = ["debit", "credit"];
	const company_currency_field = ["debit_in_company_currency", "credit_in_company_currency"];

	fields.forEach((field) => {
		frm.set_df_property(
			field,
			"label",
			`${frm.fields_dict[field].df.label.split(" (")[0]} (${currency})`,
		);
	});

	company_currency_field.forEach((field) => {
		frm.set_df_property(
			field,
			"label",
			`${frm.fields_dict[field].df.label.split(" (")[0]} (${company_currency.message.default_currency})`,
		);
	});
}
