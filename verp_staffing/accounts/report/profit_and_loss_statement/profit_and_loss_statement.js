// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

// profit_and_loss_statement.js
// Frappe Script Report – Profit and Loss Statement
// Identical filter behaviour to Balance Sheet report.

frappe.query_reports["Profit and Loss Statement"] = {
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
	// force_fy = true  → always overwrite fiscal year values
	// force_fy = false → only overwrite if current value is invalid
	// ─────────────────────────────────────────────────────────────
	_apply_company_defaults: function (company, force_fy) {
		let me = frappe.query_reports["Profit and Loss Statement"];

		// 1. Company → default_currency
		frappe.db.get_value("Company", company, ["default_currency"], function (r) {
			if (!r) return;
			if (r.default_currency) {
				frappe.query_report.set_filter_value("currency", r.default_currency);
			}

			// ── NEW: reset exchange rate field when company changes ──────
			let selected = frappe.query_report.get_filter_value("currency");
			me._toggle_exchange_rate_field(selected, r.default_currency);
		});

		// 2. Fiscal years whose included_companies contains this company
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
	// ONLOAD – auto-populate from Accounts Settings → Company
	// ─────────────────────────────────────────────────────────────
	onload: function (report) {
		let me = frappe.query_reports["Profit and Loss Statement"];

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
	// FILTERS  (identical structure to Balance Sheet)
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
					frappe.query_reports["Profit and Loss Statement"]._apply_company_defaults(
						company,
						true,
					);
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

		// Fiscal Year sub-fields
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

		// Date Range sub-fields
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
			on_change: function () {
				let me = frappe.query_reports["Profit and Loss Statement"];
				let selected = frappe.query_report.get_filter_value("currency");
				let company = frappe.query_report.get_filter_value("company");
				if (!company) return;

				frappe.db.get_value("Company", company, "default_currency", function (r) {
					let company_currency = r && r.default_currency;
					me._toggle_exchange_rate_field(selected, company_currency);
				});
			},
		},
		{
			fieldname: "presentation_exchange_rate",
			label: __("Exchange Rate"),
			fieldtype: "Float",
			default: 1,
			hidden: 1,
			precision: 6,
			on_change: function () {
				let me = frappe.query_reports["Profit and Loss Statement"];
				let rate = frappe.query_report.get_filter_value("presentation_exchange_rate") || 1;
				let from = frappe.query_report.get_filter_value("currency");
				let company = frappe.query_report.get_filter_value("company");

				if (!from || !company) return;

				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "view",
			label: __("Select View"),
			fieldtype: "Select",
			options: "Report View\nGrowth View\nMargin View",
			default: "Report View",
		},

		// ── Checkboxes ─────────────────────────────────────────────
		{
			fieldname: "show_accumulated_values",
			label: __("Show Accumulated Values (YTD)"),
			fieldtype: "Check",
			default: 0,
			description: __(
				"When checked, each period column shows year-to-date totals instead of that period's movement.",
			),
		},
		{
			fieldname: "include_default_fb_entries",
			label: __("Include Default FB Entries"),
			fieldtype: "Check",
			default: 1, // ON by default
		},
		{
			fieldname: "show_zero_values",
			label: __("Show Zero Values"),
			fieldtype: "Check",
			default: 0, // OFF by default
		},
	],

	// ─────────────────────────────────────────────────────────────
	// FORMATTER
	// ─────────────────────────────────────────────────────────────
	formatter: function (value, row, column, data, default_formatter) {
		if (!data) return value;

		let view = frappe.query_report.get_filter_value("view") || "Report View";

		// ── Margin View: all numeric columns show % of Total Income ─
		if (view === "Margin View" && column.fieldname !== "account") {
			// Python sets a  _margin  suffixed key for each period fieldname
			let margin_key = column.fieldname + "_margin";
			let margin = data[margin_key];

			if (margin === undefined || margin === null) {
				// Section headers / spacer rows have no margin — render blank
				return "";
			}

			let pct = frappe.utils.flt(margin, 2);
			let color =
				pct < 0 ? "var(--red-500)" : pct > 0 ? "var(--green-500)" : "var(--text-muted)";
			let bold = data.bold ? "font-weight:700;" : "";
			return `<span style="color:${color};${bold}">${pct}%</span>`;
		}

		// ── Growth View: Python sets _growth suffixed key ───────────
		if (
			view === "Growth View" &&
			column.fieldname !== "account" &&
			column.fieldname.endsWith("_growth")
		) {
			let pct = frappe.utils.flt(value, 2);
			let color = pct < 0 ? "var(--red-500)" : "var(--green-500)";
			return `<span style="color:${color}">${pct}%</span>`;
		}

		value = default_formatter(value, row, column, data);

		// Section headers: INCOME / EXPENSES
		if (data.indent === 0 && data.is_group && column.fieldname === "account") {
			value = `<span style="font-size:12px;font-weight:700;letter-spacing:0.08em;
				text-transform:uppercase;color:var(--text-color)">${data.account}</span>`;
		}

		// Bold total rows
		if (data.bold && column.fieldname !== "account") {
			value = `<strong>${value}</strong>`;
		}

		// Net Profit row: green (profit) or red (loss)
		if (column.fieldname !== "account") {
			let num = flt(data[column.fieldname]);

			if (data.is_net_profit) {
				let color = num >= 0 ? "var(--green-500)" : "var(--red-500)";

				value = `
					<span style="
						color:${color};
						font-weight:700;
					">
						${value}
					</span>
				`;
			} else if (data.root_type === "Income") {
				value = `
					<span style="color:var(--red-500)">
						${value}
					</span>
				`;
			} else if (data.root_type === "Expense") {
				value = `
					<span style="color:#3b82f6">
						${value}
					</span>
				`;
			}
		}

		return value;
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

	// ── Show/hide exchange rate field and update its description ──
	_toggle_exchange_rate_field: function (selected_currency, company_currency) {
		let me = frappe.query_reports["Profit and Loss Statement"];
		let show = !!(
			selected_currency &&
			company_currency &&
			selected_currency !== company_currency
		);

		frappe.query_report.toggle_filter_display("presentation_exchange_rate", !show);

		if (!show) {
			frappe.query_report.set_filter_value("presentation_exchange_rate", 1);
			frappe.query_report.refresh(); // re-run with rate=1 (no conversion)
			return;
		}

		frappe.query_report.set_filter_value("presentation_exchange_rate", 1);
	},
};
