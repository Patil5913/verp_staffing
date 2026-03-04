// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Lead Per Employee"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date"
		},
		{
			fieldname: "to_date",
			label: "To Date",
			fieldtype: "Date"
		},
		{
			fieldname: "visa_status",
			label: "Visa Status",
			fieldtype: "Select",
			options: [
				"",
				"F1 CPT",
				"F1 OPT",
				"STEM OPT",
				"H1 B",
				"H4",
				"GREEN CARD",
				"USC",
				"EB - 1",
				"EB - 2",
				"EB - 3",
				"L - 1",
				"L - 2",
				"TN",
				"O - 1",
				"WORK PERMIT",
				"PR"
			]
		}
	]
};
