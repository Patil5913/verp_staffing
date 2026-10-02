let bar_observer = null;
let bar_interval = null;

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

	onload: function (report) {
		start_bar_coloring();
	},

	after_datatable_render: function (table_instance) {
		setTimeout(() => {
			color_rows(table_instance);
			start_bar_coloring();
		}, 50);
	},
};

function color_rows(table_instance) {
	if (!table_instance) return;

	const report_data = frappe.query_report.data || [];

	report_data.forEach((row, rowIndex) => {
		if (!row) return;

		if (row.to_highlight) {
			table_instance.style.setStyle(`.dt-row-${rowIndex} .dt-cell`, {
				backgroundColor: "#ffe5e5",
			});
		} else {
			table_instance.style.setStyle(`.dt-row-${rowIndex} .dt-cell`, {
				backgroundColor: "",
			});
		}
	});
}

function apply_bar_colors() {
	const report_data = frappe.query_report.data || [];
	const bars = document.querySelectorAll(".dataset-units rect.bar.mini");
	if (!bars.length || !report_data.length) return false;

	bars.forEach((bar, index) => {
		const row = report_data[index];
		if (!row) return;
		const completed = row.completed_target || 0;
		const target = row.target || 0;
		const color = completed < target ? "#f50004ff" : "#28a745";
		bar.style.setProperty("fill", color, "important");
	});

	return true;
}

function start_bar_coloring() {
	// Clear any existing interval
	if (bar_interval) {
		clearInterval(bar_interval);
		bar_interval = null;
	}

	// Disconnect existing observer
	// if (bar_observer) {
	// 	bar_observer.disconnect();
	// 	bar_observer = null;
	// }

	// Keep trying every 100ms until bars are colored
	bar_interval = setInterval(() => {
		// const success = apply_bar_colors();
		// attempts++;

		// Stop after success or 5 seconds
		// if (attempts > 1) {
		// 	clearInterval(bar_interval);
		// 	bar_interval = null;
		// 	return;
		// }

		// if (success) {
		clearInterval(bar_interval);
		bar_interval = null;

		// After success, watch for any re-render that resets colors
		const chart_area = document.querySelector(".frappe-chart") || document.body;
		bar_observer = new MutationObserver(() => {
			const bars = document.querySelectorAll(".dataset-units rect.bar.mini");
			if (bars.length > 0) {
				// Check if colors got reset
				const first_bar = bars[0];
				const current_fill = first_bar.style.getPropertyValue("fill");
				apply_bar_colors();
			}
		});

		bar_observer.observe(chart_area, {
			childList: true,
			subtree: true,
			attributes: true,
			attributeFilter: ["style"],
		});
		// }
	});
}
