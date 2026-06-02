// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

function toggle_filters(report) {
	const periodicity = report.get_filter_value("periodicity");

	const customer = report.get_filter("customer");
	const limit = report.get_filter("limit");

	const to_date = report.get_filter("to_date");

	const year = report.get_filter("year");

	if (!periodicity) {
		customer.df.hidden = 0;
		to_date.df.hidden = 0;
		year.df.hidden = 1;
	} else if (periodicity === "Monthly" || periodicity === "Quarterly") {
		customer.df.hidden = 1;
		to_date.df.hidden = 1;
		year.df.hidden = 0;
		limit.df.hidden = 1;
	} else {
		//yearly
		customer.df.hidden = 1;
		to_date.df.hidden = 1;
		year.df.hidden = 167;
		limit.df.hidden = 1;
	}

	customer.refresh();
	limit.refresh();
	to_date.refresh();
	year.refresh();
}

frappe.query_reports["Future Interviews Per Customer"] = {
	onload: function (report) {
		toggle_filters();

		report.get_filter("periodicity").df.on_change = function () {
			toggle_filters();
			report.refresh();
		};
	},
	filters: [
		{
			fieldname: "to_date",
			label: "Up To Date",
			fieldtype: "Date",
		},
		{
			fieldname: "customer",
			label: "Customer",
			fieldtype: "Link",
			options: "Customer",
			get_query: function () {
				return {
					query: "verp_staffing.marketing.report.future_interviews_per_customer.future_interviews_per_customer.get_customers_with_interviews",
				};
			},
		},
		{
			fieldname: "periodicity",
			label: "Periodicity",
			fieldtype: "Select",
			options: "\nMonthly\nQuarterly\nYearly",
			on_change: function (report) {
				// Clear hidden filters
				report.set_filter_value("customer", null);

				report.set_filter_value("to_date", null);

				toggle_filters(report);

				report.refresh();
			},
		},
		{
			fieldname: "year",
			label: "Year",
			fieldtype: "Int",
			default: new Date().getFullYear(),
			hidden: 1,
		},
		{
			fieldname: "limit",
			label: "Limit",
			fieldtype: "Int",
			default: 25,
			description: "Maximum 500 records",
			on_change: function (report) {
				const value = cint(report.get_filter_value("limit"));

				if (value > 500) {
					frappe.msgprint(__("Maximum allowed limit is 500"));

					report.set_filter_value("limit", 500);
				}
			},
		},
	],
};
