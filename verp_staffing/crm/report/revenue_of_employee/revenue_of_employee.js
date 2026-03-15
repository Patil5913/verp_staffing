let bar_observer = null;
let bar_interval = null;

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

	onload: function () {
		start_bar_coloring();
	},

	after_datatable_render: function (table_instance) {

		table_instance.datamanager.data.forEach((rowData, rowIndex) => {

			if (!rowData) return;

			const revenue = rowData.total_revenue || 0;
			const target = rowData.target || 0;

			let color = "";

			if (revenue < target) {
				color = "#ffe5e5";
			}

			table_instance.style.setStyle(`.dt-row-${rowIndex} .dt-cell`, {
				backgroundColor: color
			});
		});

		start_bar_coloring();
	},
};


function apply_bar_colors() {

	const report_data = frappe.query_report.data || [];
	const bars = document.querySelectorAll(".dataset-units rect.bar.mini");

	if (!bars.length || !report_data.length) return false;

	bars.forEach((bar, index) => {

		const row = report_data[index];
		if (!row) return;

		const revenue = row.total_revenue || 0;
		const target = row.target || 0;

		const color = revenue < target ? "#f50004ff" : "#28a745";

		bar.style.setProperty("fill", color, "important");
	});

	return true;
}


function start_bar_coloring() {

	// stop previous interval
	if (bar_interval) {
		clearInterval(bar_interval);
		bar_interval = null;
	}

	// disconnect previous observer
	if (bar_observer) {
		bar_observer.disconnect();
		bar_observer = null;
	}

	let attempts = 0;

	bar_interval = setInterval(() => {

		const success = apply_bar_colors();
		attempts++;

		// stop after 5 seconds
		if (attempts > 50) {
			clearInterval(bar_interval);
			bar_interval = null;
			return;
		}

		// once bars colored, attach observer
		if (success) {

			clearInterval(bar_interval);
			bar_interval = null;

			const chart_area = document.querySelector(".frappe-chart") || document.body;

			bar_observer = new MutationObserver(() => {
				apply_bar_colors();
			});

			bar_observer.observe(chart_area, {
				childList: true,
				subtree: true
			});
		}

	}, 100);
}