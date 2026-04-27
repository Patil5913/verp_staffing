// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Trial Balance"] = {

	// ─────────────────────────────────────────────────────────────
	// INTERNAL: restrict fiscal_year dropdown to company's years
	// ─────────────────────────────────────────────────────────────
	_set_fiscal_year_query: function (fy_names) {
		let filter = frappe.query_report.get_filter("fiscal_year");
		if (!filter) return;
		filter.df.get_query = function () {
			return { filters: [["Fiscal Year", "name", "in", fy_names]] };
		};
		if (filter.df && filter.df.$input) {
			let ctrl = filter.df.$input.data("fieldobj");
			if (ctrl) ctrl.get_query = filter.df.get_query;
		}
	},

	// ─────────────────────────────────────────────────────────────
	// INTERNAL: cascade company → currency, finance_book, fiscal year,
	//           from_date / to_date from selected fiscal year
	// ─────────────────────────────────────────────────────────────
	_apply_company_defaults: function (company, force_fy) {
		let me = frappe.query_reports["Trial Balance"];

		// 1. Company → default_currency + default_finance_book
		frappe.db.get_value(
			"Company", company,
			["default_currency"],
			function (r) {
				if (!r) return;
				if (r.default_currency) {
					frappe.query_report.set_filter_value("currency", r.default_currency);
				}
				// if (r.default_finance_book) {
				// 	frappe.query_report.set_filter_value("finance_book", r.default_finance_book);
				// }
			}
		);

		// 2. Fiscal years whose included_companies contains this company
		frappe.db.get_list("Fiscal Year", {
			fields:   ["name", "year_start_date", "year_end_date"],
			filters:  [["Fiscal Year Company", "company", "=", company]],
			order_by: "year_start_date asc",
			limit:    500
		}).then(function (rows) {
			if (!rows || !rows.length) return;

			let fy_names = rows.map(function (r) { return r.name; });
			let last_row = rows[rows.length - 1];

			// Restrict dropdown options to company's fiscal years
			me._set_fiscal_year_query(fy_names);

			let cur_fy = frappe.query_report.get_filter_value("fiscal_year");

			if (force_fy || !cur_fy || !fy_names.includes(cur_fy)) {
				// Auto-set to latest fiscal year and fill dates from it
				frappe.query_report.set_filter_value("fiscal_year", last_row.name);
				me._fill_dates_from_fiscal_year(last_row);
			}
		});
	},

	// ─────────────────────────────────────────────────────────────
	// INTERNAL: fill from_date / to_date from a fiscal year row
	// ─────────────────────────────────────────────────────────────
	_fill_dates_from_fiscal_year: function (fy_row) {
		if (fy_row.year_start_date) {
			frappe.query_report.set_filter_value("from_date", fy_row.year_start_date);
		}
		if (fy_row.year_end_date) {
			frappe.query_report.set_filter_value("to_date", fy_row.year_end_date);
		}
	},

	// ─────────────────────────────────────────────────────────────
	// ONLOAD – auto-populate from Accounts Settings → Company
	// ─────────────────────────────────────────────────────────────
	onload: function (report) {
		let me = frappe.query_reports["Trial Balance"];

		frappe.db.get_value(
			"Accounts Settings",
			"Accounts Settings",
			"default_company",
			function (r) {
				let company = (r && r.default_company)
					? r.default_company
					: frappe.defaults.get_user_default("Company");

				if (!company) return;

				frappe.query_report.set_filter_value("company", company);
				// force_fy = true: always pre-fill on first load
				me._apply_company_defaults(company, true);
			}
		);
	},

	// ─────────────────────────────────────────────────────────────
	// FILTERS
	// ─────────────────────────────────────────────────────────────
	filters: [

		// ── Row 1 ──────────────────────────────────────────────────
		{
			fieldname: "company",
			label:     __("Company"),
			fieldtype: "Link",
			options:   "Company",
			reqd:      1,
			on_change: function () {
				let company = frappe.query_report.get_filter_value("company");
				if (company) {
					frappe.query_reports["Trial Balance"]._apply_company_defaults(company, true);
				}
			}
		},
		{
			fieldname: "fiscal_year",
			label:     __("Fiscal Year"),
			fieldtype: "Link",
			options:   "Fiscal Year",
			reqd:      1,
			// get_query injected dynamically by _set_fiscal_year_query
			on_change: function () {
				let fy = frappe.query_report.get_filter_value("fiscal_year");
				if (!fy) return;
				// When user manually picks a different fiscal year, auto-fill dates from it
				frappe.db.get_value("Fiscal Year", fy, ["year_start_date", "year_end_date"], function (r) {
					if (r) {
						frappe.query_reports["Trial Balance"]._fill_dates_from_fiscal_year(r);
					}
				});
			}
		},

		// ── Row 2 ──────────────────────────────────────────────────
		{
			fieldname: "from_date",
			label:     __("From Date"),
			fieldtype: "Date",
			reqd:      1
			// auto-filled from fiscal year's year_start_date
		},
		{
			fieldname: "to_date",
			label:     __("To Date"),
			fieldtype: "Date",
			reqd:      1
			// auto-filled from fiscal year's year_end_date
		},
		{
			fieldname: "finance_book",
			label:     __("Finance Book"),
			fieldtype: "Link",
			options:   "Finance Book"
			// auto-set from Company.default_finance_book
		},
		{
			fieldname: "currency",
			label:     __("Currency"),
			fieldtype: "Link",
			options:   "Currency"
			// auto-set from Company.default_currency
		},

		// ── Checkboxes ─────────────────────────────────────────────
		{
			// Include previous FY closing entries as opening balance
			fieldname:   "with_period_closing_entry",
			label:       __("With Period Closing Entry For Opening Balances"),
			fieldtype:   "Check",
			default:     1,
			description: __("Include previous fiscal year's closing entries as opening balances.")
		},
		{
			// Include period closing entries in the current period
			fieldname:   "period_closing_entry",
			label:       __("Period Closing Entry For Current Period"),
			fieldtype:   "Check",
			default:     0,
			description: __("Include period closing journal entries (P&L transfers) in current period figures.")
		},
		{
			// Show all accounts including zero-balance ones
			fieldname: "show_zero_values",
			label:     __("Show Zero Values"),
			fieldtype: "Check",
			default:   0
		},
		{
			// Include unclosed P&L balances from previous unclosed fiscal years
			fieldname:   "show_unclosed_fy_pl_balances",
			label:       __("Show Unclosed Fiscal Year's P&L Balances"),
			fieldtype:   "Check",
			default:     0,
			description: __("Include unclosed profit/loss from previous fiscal years in opening balance calculation.")
		},
		{
			// Include GL entries with no finance book alongside selected book
			fieldname: "include_default_fb_entries",
			label:     __("Include Default FB Entries"),
			fieldtype: "Check",
			default:   1
		},
		{
			// Show net (Dr-Cr) instead of separate Dr/Cr for opening and closing
			fieldname:   "show_net_values",
			label:       __("Show Net Values in Opening and Closing Columns"),
			fieldtype:   "Check",
			default:     0,
			description: __("When checked, opening and closing columns show net balance (Debit − Credit) instead of separate Debit and Credit columns.")
		}
	],

	// ─────────────────────────────────────────────────────────────
	// FORMATTER
	// ─────────────────────────────────────────────────────────────
	formatter: function (value, row, column, data, default_formatter) {
		if (!data) return value;

		value = default_formatter(value, row, column, data);

		// Grand total row — bold everything
		if (data.is_total_row) {
			value = `<strong>${value}</strong>`;
		}

		// Group accounts (parent rows) — bold the account name
		if (data.is_group && column.fieldname === "account") {
			value = `<strong>${value}</strong>`;
		}

		// Negative values in red (imbalance or contra)
		if (typeof value === "number" && value < 0) {
			value = `<span style="color:var(--red-500)">${value}</span>`;
		}

		return value;
	},

	// ─────────────────────────────────────────────────────────────
	// TREE OPTIONS
	// ─────────────────────────────────────────────────────────────
	tree:          true,
	name_field:    "account",
	parent_field:  "parent_account",
	initial_depth: 3,

	get_datatable_options: function (options) {
		return Object.assign(options, {
			layout:     "fixed",
			cellHeight: 36
		});
	}
};