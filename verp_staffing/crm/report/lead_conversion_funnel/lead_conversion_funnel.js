// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Lead Conversion Funnel"] = {
	"filters": [

	],
	get_chart_options(chart) {
		const custom_colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF']; // Define custom colors

		return {
			data: {
				labels: chart.data.labels,
				datasets: chart.data.datasets.map(dataset => {
					// Assign the custom colors array to the dataset or the main data object
					return {
						...dataset,
						colors: custom_colors.slice(0, dataset.values.length) // Use part of or full array
					};
				}),
				colors: custom_colors // Alternatively, set it at the top level data object
			},
			// ... other chart options
		};
	}
};
