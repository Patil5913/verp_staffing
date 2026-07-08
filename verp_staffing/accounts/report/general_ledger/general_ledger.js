// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["General Ledger"] = {
	onload: function (report) {
		frappe.db.get_single_value("Accounts Settings", "default_company").then((company) => {
			const current_company = report.get_filter_value("company");

			if (!current_company && company) {
				report.set_filter_value("company", company);
			}
		});
	},
	_setting_fiscal_year_dates: false,
	_fiscal_year_range: null, // to store range of fiscal year to reduce validation db queries { start_date: "2024-01-01", end_date: "2024-12-31" }
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
			on_change: function () {
				if (frappe.query_reports["General Ledger"]._setting_fiscal_year_dates) return;
				_validate_fiscal_year_against_dates();
			},
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
			on_change: function () {
				frappe.query_report.set_filter_value("fiscal_year", "");
			},
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
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				return {
					query: "verp_staffing.accounts.doctype.fiscal_year.fiscal_year.get_fiscal_years_for_company",
					filters: { company: company },
				};
			},
			on_change: function () {
				const fiscal_year = frappe.query_report.get_filter_value("fiscal_year");
				const report_def = frappe.query_reports["General Ledger"];

				if (!fiscal_year) {
					// clear cached range when FY is deselected
					report_def._fiscal_year_range = null;
					return;
				}
				// DB call per FY selection — result cached in memory
				frappe.db.get_value(
					"Fiscal Year",
					fiscal_year,
					["year_start_date", "year_end_date"],
					(r) => {
						if (!r) return;

						// cache dates — all subsequent validations read from here
						report_def._fiscal_year_range = {
							start: r.year_start_date,
							end: r.year_end_date,
						};

						report_def._setting_fiscal_year_dates = true;
						frappe.query_report.set_filter_value("from_date", r.year_start_date);
						frappe.query_report.set_filter_value("to_date", r.year_end_date);
						setTimeout(() => {
							report_def._setting_fiscal_year_dates = false;
						}, 0);
					},
				);
			},
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
				frappe.query_report.get_filter("party").df.options =
					frappe.query_report.get_filter_value("party_type") || "DocType";
				frappe.query_report.get_filter("party").refresh();
			},
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Link",
			options: "DocType",
			get_query: function () {
				const party_type = frappe.query_report.get_filter_value("party_type");
				if (!party_type) return {};
				return { doctype: party_type };
			},
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
			default: 1,
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

function _validate_fiscal_year_against_dates() {
	const report_def = frappe.query_reports["General Ledger"];
	const cached_range = report_def._fiscal_year_range;

	// no FY selected or not cached yet — nothing to validate
	if (!cached_range) return;

	const from_date = frappe.query_report.get_filter_value("from_date");
	const to_date = frappe.query_report.get_filter_value("to_date");
	if (!from_date || !to_date) return;

	const fy_start = frappe.datetime.str_to_obj(cached_range.start);
	const fy_end = frappe.datetime.str_to_obj(cached_range.end);
	const f_from = frappe.datetime.str_to_obj(from_date);
	const f_to = frappe.datetime.str_to_obj(to_date);

	if (f_from < fy_start || f_to > fy_end) {
		report_def._fiscal_year_range = null; // clear cache
		frappe.query_report.set_filter_value("fiscal_year", "");
	}
}
