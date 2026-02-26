frappe.query_reports["Interview Target Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: "Select Date",
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
			on_change: function () {
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "employee",
			label: "Employee",
			fieldtype: "Link",
			options: "Employee",
			get_query: function () {
				return {
					query: "verp_staffing.marketing.report.interview_target_report.interview_target_report.get_marketing_hierarchy_employees",
				};
			},
		},
	],

	after_datatable_render: function (table_instance) {
		table_instance.datamanager.data.forEach((rowData, rowIndex) => {
			if (rowData.to_highlight) {
				table_instance.style.setStyle(`.dt-row-${rowIndex} .dt-cell`, {
					backgroundColor: "#ffe5e5",
				});
			}
		});
	},
};