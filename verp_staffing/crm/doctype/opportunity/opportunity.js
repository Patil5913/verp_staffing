// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Opportunity", {
	onload(frm) {
		if (frm.is_new()) {
			frm.set_value("sales_stage", "Prospecting");
		}

		const roles = frappe.user_roles;
		const user = frappe.session.user;
		if (user != "Administrator") {
			// Only apply to Lead Employee
			if (
				roles.includes("Lead Employee") ||
				roles.includes("Lead Manager") ||
				roles.includes("Lead Master Manager")
			) {
				frappe.msgprint("You are not allowed to access Opportunity list.");
				frappe.set_route("desk");
			}
		}
	},

	refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);
		if (frm.doc.status == "Converted") {
			frm.set_df_property("status", "read_only", 1);
		}

		frm.set_query("opportunity_owner", function () {
			return {
				filters: [["Employee Assignment Detail", "department", "=", "Sales"]],
			};
		});

		frm.add_custom_button(__("Create Customer"), function () {
			open_create_sales_order_dialog(frm);
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Opportunity Form";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		if (!frm.doc.opportunity_owner) {
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Employee",
					filters: [
						["Employee", "user", "=", frappe.session.user],
						["Employee Assignment Detail", "department", "=", "Sales"],
					],
					fields: ["name"],
					limit: 1,
				},
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						frm.set_value("opportunity_owner", r.message[0].name);
					}
				},
			});
		}
		// but still allow changes *except* Converted
		frm.doc._previous_status = frm.doc.status; //save the last status

		const roles = frappe.user_roles;

		if (roles.includes("Extra Menu Item Not Show")) {
			/* ----------------------------------------------------
               GENERIC REUSABLE HIDE FUNCTION
            ---------------------------------------------------- */
			const hideElements = ({ selectors = [], keywordSelectors = [], keywords = [] }) => {
				// Hide specific selectors
				selectors.forEach((sel) => {
					const el = document.querySelector(sel);
					if (el) el.style.display = "none";
				});
				// Hide based on keywords
				keywordSelectors.forEach((sel) => {
					document.querySelectorAll(sel).forEach((el) => {
						const text = el.innerText?.trim();
						if (text && keywords.some((k) => text.includes(k))) {
							el.style.display = "none";

							// Hide li wrapper if exists (for dropdown)
							const li = el.closest("li");
							if (li) li.style.display = "none";
						}
					});
				});
			};

			/* ----------------------------------------------------
               MENU CLEANUP
            ---------------------------------------------------- */
			const MENU_HIDE = ["Links", "Duplicate", "Copy to Clipboard"];

			const cleanMenu = () => {
				// Frappe API removal
				MENU_HIDE.forEach((label) => {
					try {
						frm.page.remove_menu_item(label);
					} catch {}
				});
				// DOM cleanup using reusable function
				hideElements({
					keywordSelectors: [".dropdown-menu .dropdown-item"],
					keywords: MENU_HIDE,
				});
			};

			// Re-clean when dropdown opens
			$(frm.page.wrapper).on("shown.bs.dropdown", cleanMenu);

			/* ----------------------------------------------------
               SIDEBAR CLEANUP
            ---------------------------------------------------- */
			const SIDEBAR_KEYWORDS = ["Assigned", "Share"];

			const cleanSidebar = () => {
				hideElements({
					selectors: [
						".form-sidebar .assigned-to",
						".form-sidebar .btn-share",
						".form-sidebar .shared-with",
					],
					keywordSelectors: [".form-sidebar *"],
					keywords: SIDEBAR_KEYWORDS,
				});
			};

			/* ----------------------------------------------------
               RUN CLEANUP ONCE + SINGLE RETRY TIMER
            ---------------------------------------------------- */
			const runCleanup = () => {
				cleanMenu();
				cleanSidebar();
			};

			// Run immediately
			runCleanup();

			// One timer for everything (menu + sidebar)
			let attempts = 0;
			const timer = setInterval(() => {
				runCleanup();
				if (attempts++ > 12) clearInterval(timer);
			}, 200);
		}

		if (!frm.is_new()) {
			load_lead_details_after_save(frm);
		}
	},

	status(frm) {
		// store safe previous value
		frm.doc.__last_sync_status = frm.doc.status;
	},


	opportunity_from_lead: function (frm) {
		frm.trigger("fetch_source_details");
		if (!frm.is_new()) {
			load_lead_details_after_save(frm);
		}
		if (frm.doc.opportunity_from_lead) {

			let source_name = frm.doc.opportunity_from_lead;

			frappe.db.get_value("Lead", source_name, "name1").then((r) => {
				if (r && r.message) {
					let base_name = r.message.name1;
					frm.set_value("name1", base_name ? base_name.trim() : "");
				}
			});
		}
	},

	name1: function (frm) {
		if (frm.fields_dict.title) {
			frm.set_value("title", frm.doc.name1);
		}
	},

	fetch_source_details: function (frm) {
		if (frm.doc.opportunity_from_lead) {
			frappe.db.get_value("Lead", frm.doc.opportunity_from_lead, "source", function (r) {
				if (r) {
					if (r.source) {
						frm.set_value("source", r.source);
					}
				}
			});
		}
	},

// 	validate: function (frm) {
// 		if (!frm.doc.opportunity_from_lead) {
// 			frappe.msgprint(__("Please select a Lead."));
// 			frappe.validated = false;
// }
// 			},

	after_save(frm) {
		load_lead_details_after_save(frm);
	},
});

function open_create_sales_order_dialog(frm) {
	if (frm.is_dirty()) {
		frm.save().then(() => {
			open_create_sales_order_dialog(frm);
		});
		return;
	}

	// Dialog Fields
	const dialog = new frappe.ui.Dialog({
		title: "Create Sales Order",
		fields: [
			{
				label: "Date",
				fieldname: "date",
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
				reqd: 1,
			},

			{
				fieldtype: "Section Break",
				label: "Services",
			},
			{
				fieldname: "services",
				fieldtype: "MultiSelectList",
				label: "Services",
				reqd: 1,
				get_data: function (txt) {
					return frappe.db
						.get_list("Service", {
							fields: ["name"],
							filters: {
								name: ["like", `%${txt}%`],
							},
							limit: 20,
						})
						.then((r) =>
							r.map((d) => ({
								value: d.name,
								description: d.name,
							})),
						);
				},
			},

			{
				fieldtype: "Section Break",
				label: "Payment Terms",
			},
			{
				fieldname: "payment_terms",
				fieldtype: "Table",
				label: "Payment Terms",
				reqd: 1,
				options: "Customer Payment Terms",
				fields: [
					{
						fieldtype: "Date",
						fieldname: "date",
						label: "Date",
						reqd: 1,
						in_list_view: 1,
					},
					{
						fieldtype: "Currency",
						fieldname: "amount",
						label: "Amount",
						reqd: 1,
						in_list_view: 1,
					},
					{
						fieldtype: "Select",
						fieldname: "payment_condition",
						label: "Payment Condition",
						options: "Number of Days\nNumber of Interviews",
						default: "Number of Days",
						reqd: 1,
						in_list_view: 1,
					},
					{
						fieldtype: "Int",
						fieldname: "counter",
						label: "Counter",
						default: 1,
						non_negative: 1,
						reqd: 1,
						in_list_view: 1,
					},
					{
						fieldtype: "Check",
						fieldname: "is_received",
						label: "Received?",
						default: 0,
						in_list_view: 1,
					},
				],
			},
		],

		primary_action_label: "Create Sales Order",
		primary_action(values) {
			dialog.hide();

			frappe.call({
				method: "verp_staffing.crm.api.sales_order_api.create_sales_order",
				args: {
					opportunity: frm.doc.name,
					opportunity_from_lead: frm.doc.opportunity_from_lead,
					data: values,
				},
				callback: function (r) {
					if (r.message?.customer) {
						frappe.set_route("Form", "Customer", r.message.customer);
					}
				},
			});
		},
	});

	dialog.show();
}
