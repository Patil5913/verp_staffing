frappe.provide("verp_staffing.setup");

frappe.setup.on("before_load", function () {
	frappe.setup.add_slide({
		name: "organization_setup",
		title: __("Organization Setup"),
		icon: "fa fa-building",
		fields: [
			{
				fieldname: "company_name",
				label: __("Company Name"),
				fieldtype: "Data",
				reqd: 1,
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "fy_start_date",
				label: __("Fiscal Year Start Date"),
				fieldtype: "Date",
				reqd: 1,
			},
			{
				fieldname: "fy_end_date",
				label: __("Fiscal Year End Date"),
				fieldtype: "Date",
				reqd: 1,
			},
			{
				fieldtype: "Section Break",
			},
			// --- Sample data toggle, same pattern ERPNext uses on its
			// "Add a few sample records to explore the system" checkbox ---
			{
				fieldname: "add_sample_data",
				label: __("Add Sample Data"),
				fieldtype: "Check",
				default: 0,
				description: __(
					"Seeds departments, users, employees, leads, opportunities, " +
						"customers, orders and invoices so you can explore the system " +
						"immediately. You can safely skip this on a production setup."
				),
			},
		],

		validate: function () {
			if (
				!this.values.company_name ||
				!this.values.fy_start_date ||
				!this.values.fy_end_date
			) {
				return false;
			}

			if (this.values.fy_start_date > this.values.fy_end_date) {
				frappe.msgprint(__("Fiscal Year Start Date must be before End Date"));
				return false;
			}

			return true;
		},
	});
});