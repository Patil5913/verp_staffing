// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["General Ledger"] = {
	filters: [
		// mandatory
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},

		// account──
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "Link",
			options: "Account",
			get_query: function () {
				return {
					filters: {
						company: frappe.query_report.get_filter_value("company"),
					},
				};
			},
		},
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},

		// party────
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Link",
			options: "DocType",
			// only show doctypes that make sense as parties
			get_query: function () {
				return {
					filters: {
						name: ["in", ["Customer", "Supplier", "Employee", "Shareholder"]],
					},
				};
			},
			on_change: function () {
				// reset party when party_type changes
				frappe.query_report.set_filter_value("party", "");
			},
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Dynamic Link",
			options: "party_type",
			get_query: function () {
				const party_type = frappe.query_report.get_filter_value("party_type");
				if (!party_type) frappe.throw(__("Please select Party Type first"));
				return { doctype: party_type };
			},
		},

		// voucher──
		{
			fieldname: "voucher_type",
			label: __("Voucher Type"),
			fieldtype: "Link",
			options: "DocType",
			on_change: function () {
				frappe.query_report.set_filter_value("voucher_no", "");
			},
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher No"),
			fieldtype: "Dynamic Link",
			options: "voucher_type",
			get_query: function () {
				const voucher_type = frappe.query_report.get_filter_value("voucher_type");
				if (!voucher_type) frappe.throw(__("Please select Voucher Type first"));
				return { doctype: voucher_type };
			},
		},

		// against voucher
		{
			fieldname: "against_voucher_type",
			label: __("Against Voucher Type"),
			fieldtype: "Link",
			options: "DocType",
			on_change: function () {
				frappe.query_report.set_filter_value("against_voucher", "");
			},
		},
		{
			fieldname: "against_voucher",
			label: __("Against Voucher"),
			fieldtype: "Dynamic Link",
			options: "against_voucher_type",
			get_query: function () {
				const avt = frappe.query_report.get_filter_value("against_voucher_type");
				if (!avt) frappe.throw(__("Please select Against Voucher Type first"));
				return { doctype: avt };
			},
		},

		// amounts──
		{
			fieldname: "min_amount",
			label: __("Min Amount"),
			fieldtype: "Float",
		},
		{
			fieldname: "max_amount",
			label: __("Max Amount"),
			fieldtype: "Float",
		},

		// flags────
		{
			fieldname: "is_opening",
			label: __("Is Opening"),
			fieldtype: "Select",
			options: "\nYes\nNo",
		},
		{
			fieldname: "is_advance",
			label: __("Is Advance"),
			fieldtype: "Select",
			options: "\nYes\nNo",
		},
		{
			fieldname: "include_cancelled",
			label: __("Include Cancelled Entries"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_in_account_currency",
			label: __("Show in Account Currency"),
			fieldtype: "Check",
			default: 0,
		},

		// ── grouping / display ─────────────────────────────────────
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: [
				"",
				{ label: __("Group by Voucher"), value: "Group by Voucher" },
				{ label: __("Group by Account"), value: "Group by Account" },
				{ label: __("Group by Party"), value: "Group by Party" },
			],
			default: "Group by Voucher",
		},
		{
			fieldname: "show_remarks",
			label: __("Show Remarks"),
			fieldtype: "Check",
			default: 0,
		},
	],

	// ── formatter: colour Dr/Cr and bold opening/closing rows ───────
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (data && data.is_opening_row) {
			value = `<b>${value}</b>`;
		}

		if (column.fieldname === "debit" && data && flt(data.debit) > 0) {
			value = `<span style="color: var(--blue-500)">${value}</span>`;
		}
		if (column.fieldname === "credit" && data && flt(data.credit) > 0) {
			value = `<span style="color: var(--red-500)">${value}</span>`;
		}
		if (data && data.is_total_row) {
			value = `<b>${value}</b>`;
		}

		return value;
	},
};
