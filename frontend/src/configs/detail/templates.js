import TemplatePreview from "@/components/detail/templates/TemplatePreview.vue";

const preview = (kind) => ({ type: "component", component: TemplatePreview, props: { kind } });

// Email Template and Print Format: Administrator-only pages (see the sidebar profile menu and the
// route guard) for the Jinja/HTML the app sends and prints. Each has a Preview tab that renders
// the unsaved text against a real record.
export const emailTemplateConfig = {
	doctype: "Email Template",
	timeline: false,
	tabs: [
		{
			key: "details",
			label: "Template",
			sections: [
				{
					type: "fields",
					title: "Email Template",
					fieldnames: ["name", "subject", "use_html", "response", "response_html"],
					fieldOverrides: () => ({
						response_html: { rows: 100 },
						response: { rows: 50 },
					}),
				},
			],
		},
		{ key: "preview", label: "Preview", sections: [preview("email")] },
	],
};

export const printFormatConfig = {
	doctype: "Print Format",
	timeline: false,
	tabs: [
		{
			key: "details",
			label: "Format",
			sections: [
				{
					type: "fields",
					title: "Print Format",
					fieldnames: [
						"name",
						"doc_type",
						"module",
						"print_format_type",
						"standard",
						"custom_format",
						"disabled",
						"default_print_language",
					],
				},
				{
					type: "fields",
					title: "Template",
					fieldnames: ["html", "css"],
					fieldOverrides: () => ({
						html: { rows: 30 },
						css: { rows: 20 },
					}),
				},
				{
					type: "fields",
					title: "Page",
					fieldnames: [
						"font",
						"font_size",
						"margin_top",
						"margin_bottom",
						"margin_left",
						"margin_right",
						"page_number",
					],
				},
			],
		},
		{ key: "preview", label: "Preview", sections: [preview("print")] },
	],
};
