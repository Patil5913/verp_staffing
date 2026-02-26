frappe.query_reports["Call Details"] = {
	filters: [
		{
			fieldname: "employee",
			label: "Employee",
			fieldtype: "Link",
			options: "Employee",
			get_query: function () {
				return {
					query: "verp_staffing.crm.report.call_details.call_details.get_hierarchy_employees",
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
