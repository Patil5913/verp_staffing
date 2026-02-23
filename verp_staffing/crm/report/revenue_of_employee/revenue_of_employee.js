// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Revenue Of Employee"] = {
	filters: [
		{
			fieldname: "employee",
			label: "Employee",
			fieldtype: "Link",
			options: "Employee",
			get_query: function () {
				return {
					query: "verp_staffing.crm.report.revenue_of_employee.revenue_of_employee.get_sales_hierarchy_employees",
				};
			},
		},
		{
			fieldname: "start_date",
			label: "Start Date",
			fieldtype: "Date",
		},
		{
			fieldname: "end_date",
			label: "End Date",
			fieldtype: "Date",
		},
		{
			fieldname: "timeline",
			label: "Timeline",
			fieldtype: "Select",
			options: "\nMonthly\n3 Months\n6 Months\nYearly",
		},
	],
};
