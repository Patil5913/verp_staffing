// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Balance Sheet"] = {
	// ─────────────────────────────────────────────────────────────
	// INTERNAL: restrict fiscal year dropdowns to company's years
	// ─────────────────────────────────────────────────────────────
	_set_fiscal_year_query: function (fy_names) {
		["from_fiscal_year", "to_fiscal_year"].forEach(function (fname) {
			let filter = frappe.query_report.get_filter(fname);
			if (!filter) return;
			filter.df.get_query = function () {
				return { filters: [["Fiscal Year", "name", "in", fy_names]] };
			};
			if (filter.df && filter.df.$input) {
				let ctrl = filter.df.$input.data("fieldobj");
				if (ctrl) ctrl.get_query = filter.df.get_query;
			}
		});
	},

	// ─────────────────────────────────────────────────────────────
	// INTERNAL: cascade company → currency, finance_book, fiscal years
	// ─────────────────────────────────────────────────────────────
	_apply_company_defaults: function (company, force_fy) {
		let me = frappe.query_reports["Balance Sheet"];

		frappe.db.get_value("Company", company, ["default_currency"], function (r) {
			if (!r) return;
			if (r.default_currency) {
				frappe.query_report.set_filter_value("currency", r.default_currency);
			}
		});

		frappe.db
			.get_list("Fiscal Year", {
				fields: ["name"],
				filters: [["Fiscal Year Company", "company", "=", company]],
				order_by: "year_start_date asc",
				limit: 500,
			})
			.then(function (rows) {
				if (!rows || !rows.length) return;
				let fy_names = rows.map(function (r) {
					return r.name;
				});
				let last_fy = fy_names[fy_names.length - 1];

				me._set_fiscal_year_query(fy_names);

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
		},
		{
			fieldname: "to_fiscal_year",
			label: __("End Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			depends_on: "eval:doc.filter_based_on=='Fiscal Year'",
			reqd: 0,
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
			label: __("Currency"),
			fieldtype: "Link",
			options: "Currency",
		},
		{
			fieldname: "view",
			label: __("Select View"),
			fieldtype: "Select",
			options: "Report View\nGrowth View",
			default: "Report View",
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
	//
	// Color rules (standard accounting convention):
	//
	//   ASSET accounts
	//     positive value  → Blue   (normal debit balance)
	//     negative value  → Red    (abnormal / credit balance)
	//
	//   LIABILITY / EQUITY accounts
	//     positive value  → Green  (normal credit balance)
	//     negative value  → Red    (abnormal / debit balance)
	//
	//   TOTAL rows (bold)
	//     positive value  → Green
	//     negative value  → Red
	//
	//   SECTION HEADERS (ASSETS / LIABILITIES / EQUITY)
	//     uppercase, larger weight, no color on amounts
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
				// Total rows
				return `<strong style="color: var(--text-color)">${label}</strong>`;
			}
			return default_formatter(value, row, column, data);
		}

		// ── Growth % columns — no accounting colors ───────────────
		if (column.fieldname && column.fieldname.endsWith("_growth")) {
			let formatted = default_formatter(value, row, column, data);
			let num = flt(value);
			if (num > 0) return `<span style="color: var(--green-500)">${formatted}</span>`;
			if (num < 0) return `<span style="color: var(--red-500)">${formatted}</span>`;
			return formatted;
		}

		// ── Amount columns ────────────────────────────────────────
		let formatted = default_formatter(value, row, column, data);
		let num = flt(value);

		// Zero values — no color
		if (num === 0) return formatted;

		let color = _get_amount_color(num, data);
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
// COLOR HELPER  (module-level, not inside the report object)
// ─────────────────────────────────────────────

/**
 * Returns a CSS color string for an amount cell.
 *
 * Accounting color convention:
 *   Asset        → positive = Blue  (normal debit balance)
 *                  negative = Red   (abnormal)
 *   Liability /
 *   Equity       → positive = Green (normal credit balance)
 *                  negative = Red   (abnormal)
 *   Total rows   → positive = Green, negative = Red
 */
function _get_amount_color(num, data) {
	// Total / summary rows
	let root_type = data.root_type;

	if (root_type === "Asset") {
		return num > 0 ? "var(--blue-500)" : "var(--red-500)";
	}

	if (root_type === "Liability" || root_type === "Equity") {
		return num > 0 ? "var(--red-500)" : "var(--blue-500)";
	}

	// Fallback: positive green, negative red
	return num > 0 ? "var(--green-500)" : "var(--red-500)";
}
