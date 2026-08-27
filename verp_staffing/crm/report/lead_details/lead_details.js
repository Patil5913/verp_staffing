// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Lead Details"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date",
		},
		{
			fieldname: "source",
			label: "Source",
			fieldtype: "Link",
			options: "Lead Source",
		},
		{
			fieldname: "lead_owner",
			label: "Lead Owner",
			fieldtype: "Link",
			options: "Employee",
			get_query: function () {
				return {
					query: "verp_staffing.crm.api.report_helper.get_lead_hierarchy_employees",
				};
			},
		},
	],
};