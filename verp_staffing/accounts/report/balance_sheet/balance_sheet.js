// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Balance Sheet"] = {
	// ─────────────────────────────────────────────────────────────
	// INTERNAL STATE
	// ─────────────────────────────────────────────────────────────
	_company_default_currency: null, // cached after company is resolved

	// ─────────────────────────────────────────────────────────────
	// INTERNAL: show / hide exchange_rate filter based on whether
	// selected currency differs from company default currency
	// ─────────────────────────────────────────────────────────────
	_toggle_exchange_rate: function () {
		let me = frappe.query_reports["Balance Sheet"];
		let currency = frappe.query_report.get_filter_value("currency");
		let show =
			currency && me._company_default_currency && currency !== me._company_default_currency;

		frappe.query_report.toggle_filter_display("exchange_rate", !show);

		if (!show) {
			// Reset to 1 when hidden so it never silently distorts numbers
			frappe.query_report.set_filter_value("exchange_rate", 1);
		}
	},

	// ─────────────────────────────────────────────────────────────
	// INTERNAL: cascade company → currency + fiscal years
	// force_fy = true  → always overwrite fiscal year values
	// force_fy = false → only overwrite if current value is invalid
	// ─────────────────────────────────────────────────────────────
	_apply_company_defaults: function (company, force_fy) {
		let me = frappe.query_reports["Balance Sheet"];

		// 1. Fetch company default currency
		frappe.db.get_value("Company", company, ["default_currency"], function (r) {
			if (!r) return;

			if (r.default_currency) {
				me._company_default_currency = r.default_currency;
				frappe.query_report.set_filter_value("currency", r.default_currency);
				// Currency just reset to default → exchange rate should hide
				me._toggle_exchange_rate();
			}
		});

		// 2. Fetch all fiscal years that include this company.
		//    Include disabled fiscal years so old years are still selectable
		//    for historical balance sheet reports.
		frappe.db
			.get_list("Fiscal Year", {
				fields: ["name", "year"],
				filters: [["Fiscal Year Company", "company", "=", company]],
				order_by: "year_start_date asc",
				limit: 500,
			})
			.then(function (rows) {
				if (!rows || !rows.length) return;

				let fy_names = rows.map(function (r) {
					return r.year;
				});
				let last_fy = fy_names[fy_names.length - 1];

				if (force_fy) {
					frappe.query_report.set_filter_value("from_fiscal_year", last_fy);
					frappe.query_report.set_filter_value("to_fiscal_year", last_fy);
				} else {
					let cur_from = frappe.query_report.get_filter_value("from_fiscal_year");
					let cur_to = frappe.query_report.get_filter_value("to_fiscal_year");
					if (!cur_from || !fy_names.includes(cur_from)) {
						frappe.query_report.set_filter_value("from_fiscal_year", last_fy);
					}
					if (!cur_to || !fy_names.includes(cur_to)) {
						frappe.query_report.set_filter_value("to_fiscal_year", last_fy);
					}
				}
			});
	},

	// ─────────────────────────────────────────────────────────────
	// ONLOAD
	// ─────────────────────────────────────────────────────────────
	onload: function (report) {
		let me = frappe.query_reports["Balance Sheet"];

		// Hide exchange_rate on load — it only appears when needed
		frappe.query_report.toggle_filter_display("exchange_rate", true);

		frappe.db.get_value(
			"Accounts Settings",
			"Accounts Settings",
			"default_company",
			function (r) {
				let company =
					r && r.default_company
						? r.default_company
						: frappe.defaults.get_user_default("Company");
				if (!company) return;

				frappe.query_report.set_filter_value("company", company);
				frappe.query_report.set_filter_value("filter_based_on", "Fiscal Year");
				me._apply_company_defaults(company, true);
			},
		);
	},

	// ─────────────────────────────────────────────────────────────
	// FILTERS
	// ─────────────────────────────────────────────────────────────
	filters: [
		// ── Row 1 ──────────────────────────────────────────────────
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			on_change: function () {
				let company = frappe.query_report.get_filter_value("company");
				if (company) {
					frappe.query_reports["Balance Sheet"]._apply_company_defaults(company, true);
				}
			},
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},

		// ── Row 2 ──────────────────────────────────────────────────
		{
			fieldname: "filter_based_on",
			label: __("Filter Based On"),
			fieldtype: "Select",
			options: "Fiscal Year\nDate Range",
			default: "Fiscal Year",
			reqd: 1,
			on_change: function () {
				let val = frappe.query_report.get_filter_value("filter_based_on");
				frappe.query_report.toggle_filter_display(
					"from_fiscal_year",
					val !== "Fiscal Year",
				);
				frappe.query_report.toggle_filter_display("to_fiscal_year", val !== "Fiscal Year");
				frappe.query_report.toggle_filter_display("from_date", val !== "Date Range");
				frappe.query_report.toggle_filter_display("to_date", val !== "Date Range");
			},
		},
		{
			fieldname: "from_fiscal_year",
			label: __("Start Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			depends_on: "eval:doc.filter_based_on=='Fiscal Year'",
			reqd: 0,
			get_query: function () {
				return {
					query: "verp_staffing.accounts.utils.fiscal_year_opening_balance.get_fiscal_years_for_company",
					filters: {
						company: frappe.query_report.get_filter_value("company"),
					},
				};
			},
		},
		{
			fieldname: "to_fiscal_year",
			label: __("End Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			depends_on: "eval:doc.filter_based_on=='Fiscal Year'",
			reqd: 0,
			get_query: function () {
				let company = frappe.query_report.get_filter_value("company");
				return {
					query: "verp_staffing.accounts.utils.fiscal_year_opening_balance.get_fiscal_years_for_company",
					filters: {
						company: company,
					},
				};
			},
		},
		{
			fieldname: "from_date",
			label: __("Start Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.filter_based_on=='Date Range'",
			reqd: 0,
		},
		{
			fieldname: "to_date",
			label: __("End Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.filter_based_on=='Date Range'",
			reqd: 0,
		},

		// ── Row 3 ──────────────────────────────────────────────────
		{
			fieldname: "periodicity",
			label: __("Periodicity"),
			fieldtype: "Select",
			options: "Yearly\nHalf-Yearly\nQuarterly\nMonthly",
			default: "Yearly",
			reqd: 1,
		},
		{
			fieldname: "currency",
			label: __("Presentation Currency"),
			fieldtype: "Link",
			options: "Currency",
			on_change: function () {
				frappe.query_reports["Balance Sheet"]._toggle_exchange_rate();
				format_currency(frappe.query_report.get_filter_value("exchange_rate"));
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "view",
			label: __("Select View"),
			fieldtype: "Select",
			options: "Report View\nGrowth View",
			default: "Report View",
		},

		// ── Exchange Rate — hidden unless presentation currency ≠ company currency ──
		{
			fieldname: "exchange_rate",
			label: __("Exchange Rate"),
			fieldtype: "Float",
			default: 1,
			// Shown only when a different presentation currency is selected.
			// All amounts in the report will be multiplied by this rate.
			// Example: if company currency is INR and you select USD,
			// enter today's INR → USD rate (e.g. 0.012).
			// The report will display every amount converted to USD.
			description: __(
				"Enter the conversion rate from company currency to the selected presentation currency. " +
					"All report amounts will be multiplied by this rate. " +
					"Example: company currency is INR, presentation currency is USD → enter INR-to-USD rate (e.g. 0.012).",
			),
			hidden: 1, // starts hidden; _toggle_exchange_rate() controls visibility
			on_change: function () {
				let rate = frappe.query_report.get_filter_value("exchange_rate");
				if (rate < 1) {
					frappe.msgprint({
						title: __("Invalid Exchange Rate"),
						message: __("Exchange rate must be greater than 1."),
						indicator: "red",
					});
					frappe.query_report.set_filter_value("exchange_rate", 1);
				}
				frappe.query_report.refresh();
			},
		},

		// ── Checkboxes ─────────────────────────────────────────────
		{
			fieldname: "show_period_movement",
			label: __("Show Period Movement (Advanced)"),
			fieldtype: "Check",
			default: 0,
			description: __(
				"Shows changes during each period instead of total balances. For analysis use only.",
			),
		},
		{
			fieldname: "include_default_fb_entries",
			label: __("Include Default FB Entries"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_zero_values",
			label: __("Show Zero Values"),
			fieldtype: "Check",
			default: 0,
		},
	],

	// ─────────────────────────────────────────────────────────────
	// FORMATTER
	// ─────────────────────────────────────────────────────────────
	formatter: function (value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);

		// ── Section headers (ASSETS / LIABILITIES / EQUITY) ──────
		if (data.is_header && column.fieldname === "account") {
			return `<span style="
				font-size: 11px;
				font-weight: 700;
				letter-spacing: 0.1em;
				text-transform: uppercase;
				color: var(--text-muted);
			">${frappe.utils.escape_html(data.account || "")}</span>`;
		}

		// ── Account name column ───────────────────────────────────
		if (column.fieldname === "account") {
			let label = frappe.utils.escape_html(data.account || "");
			if (data.bold) {
				return `<strong style="color: var(--text-color)">${label}</strong>`;
			}
			return default_formatter(value, row, column, data);
		}

		// ── Growth % columns — directional color only ─────────────
		if (column.fieldname && column.fieldname.endsWith("_growth")) {
			let formatted = default_formatter(value, row, column, data);
			let num = flt(value);
			if (num > 0) return `<span style="color: var(--green-500)">${formatted}</span>`;
			if (num < 0) return `<span style="color: var(--red-500)">${formatted}</span>`;
			return formatted;
		}

		// ── Amount columns ────────────────────────────────────────
		// Apply exchange rate if a presentation currency is selected
		let exchange_rate = flt(frappe.query_report.get_filter_value("exchange_rate") || 1);
		let raw_num = flt(value);
		let display_num = raw_num * exchange_rate;

		// Re-format with converted value
		let display_value = exchange_rate !== 1 ? display_num : raw_num;
		let formatted =
			exchange_rate !== 1
				? format_currency(display_value, frappe.query_report.get_filter_value("currency"))
				: default_formatter(value, row, column, data);

		if (display_num === 0) return formatted;

		let color = _get_amount_color(display_num, data);
		if (color) {
			let weight = data.bold ? "font-weight:600;" : "";
			return `<span style="color:${color};${weight}">${formatted}</span>`;
		}

		return formatted;
	},

	// ─────────────────────────────────────────────────────────────
	// TREE OPTIONS
	// ─────────────────────────────────────────────────────────────
	tree: true,
	name_field: "account",
	parent_field: "parent_account",
	initial_depth: 2,
	get_datatable_options: function (options) {
		return Object.assign(options, {
			layout: "fixed",
			cellHeight: 36,
		});
	},
};

// ─────────────────────────────────────────────
// COLOR HELPER
// ─────────────────────────────────────────────

/**
 * Asset      → positive = Blue (normal debit balance), negative = Red
 * Liability /
 * Equity     → positive shown normally (no green for debts),
 *               negative = Red (abnormal debit balance)
 * Total rows → positive = neutral bold, negative = Red
 */
function _get_amount_color(num, data) {
	let root_type = data.root_type;

	if (root_type === "Asset") {
		return num > 0 ? "var(--blue-500)" : "var(--red-500)";
	}

	if (root_type === "Liability" || root_type === "Equity") {
		// Positive = normal credit balance → no special color (neutral)
		// Negative = abnormal → red
		return num > 0 ? "var(--red-500)" : "var(--blue-500)";
	}

	// Total / summary bold rows
	if (data.bold) {
		return num < 0 ? "var(--red-500)" : null;
	}

	return null;
}
