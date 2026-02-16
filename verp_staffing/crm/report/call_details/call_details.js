// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Call Details"] = {
	"filters": [
	
		{
			fieldname: "employee",
			label: "Employee",
			fieldtype: "Link",
			options: "Employee",
			get_query: function () {
				return {
					query: "verp_staffing.crm.report.call_details.call_details.get_hierarchy_employees"

				};
			}
		},





	]
};
