// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead", {
	onload(frm) {
		// Always keep field visible
		frm.set_df_property("lead_owner", "read_only_onload", 1);
		// If lead_owner is empty → auto assign employee of logged-in user
		if (!frm.doc.lead_owner) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Employee",
					filters: { user: frappe.session.user },
					fieldname: "name",
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value("lead_owner", r.message.name);

						// Lock the field so user cannot change
						frm.set_df_property("lead_owner", "read_only", 1);
					}
				},
			});
		} else {
			// If already set → lock it
			frm.set_df_property("lead_owner", "read_only", 1);
		}
		// Stop user from selecting Converted manually
		frm.set_df_property("status", "read_only", 1);
	},

	refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);

		frm.add_custom_button(__("Create Opportunity"), () => {
			open_create_opportunity_dialog(frm);
		});

		if (frm.is_new()) {
			frm.add_custom_button("Show Form Tour", () => {
				const tour_name = "Lead Form";

				frm.tour.init({ tour_name }).then(() => frm.tour.start());
			});
		}

		const roles = frappe.user_roles;

		if (roles.includes("Extra Menu Item Not Show")) {
			//    GENERIC REUSABLE HIDE FUNCTION
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

			//    MENU CLEANUP
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

			//    SIDEBAR CLEANUP
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

			//    RUN CLEANUP ONCE + SINGLE RETRY TIMER
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

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Lead Form";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
	},
});

frappe.ui.form.on("Lead Course", {
	start_date(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		window.LeadCourse.check_row(row);
	},
	end_date(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		window.LeadCourse.check_row(row);
	},
	grade(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		window.LeadCourse.check_row(row);
	},
});

function open_create_opportunity_dialog(frm) {
	// If lead isn't saved yet, ask to save first
	if (frm.is_dirty()) {
		frm.save().then(() => {
			open_create_opportunity_dialog(frm);
		});
		return;
	}

	// Check if Opportunity already exists for this Lead
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Opportunity",
			filters: { party_name: frm.doc.name, opportunity_from: "Lead" },
			limit_page_length: 1,
		},
		callback: function (r) {
			if (r.message && r.message.length > 0) {
				frappe.msgprint({
					title: __("Error"),
					message: __("An Opportunity already exists for this Lead."),
					indicator: "red",
				});
			} else {
				// Open a dialog to create Opportunity
				const dialog = new frappe.ui.Dialog({
					title: __("Create Opportunity from Lead"),
					fields: [
						{
							fieldname: "manual_assign",
							fieldtype: "Check",
							label: "Want to assign Opportunity Owner Manually?",
						},
						{
							fieldname: "opportunity_owner",
							label: "Opportunity Owner",
							fieldtype: "Link",
							options: "Employee",
							depends_on: "eval:doc.manual_assign == 1",
							mandatory_depends_on: "eval:doc.manual_assign == 1",
							get_query() {
								return {
									filters: {
										department: "Sales", // Only show Sales department employees
									},
								};
							},
						},
					],
					primary_action_label: __("Create"),
					primary_action(values) {
						dialog.hide();
						if (values.manual_assign) {
							// if user select owner manually then direct create
							create_opportunity(frm, values.opportunity_owner);
						} else {
							// else get employee with lowest count and create opportunity
							frappe.call({
								method: "verp_staffing.crm.api.auto_assign.get_auto_assign_employee",
								args: {
									department: "Sales",
									target_doctype: "Opportunity",
									owner_field: "opportunity_owner",
								},
								callback(r) {
									if (r.message) {
										create_opportunity(frm, r.message);
									}
								},
							});
						}
					},
				});
				dialog.show();
			}
		},
	});
}

function create_opportunity(frm, owner) {
	const opportunity_doc = {
		doctype: "Opportunity",
		opportunity_from: "Lead",
		party_name: frm.doc.name,
		opportunity_owner: owner,
		name1: frm.doc.name,
	};

	frappe.call({
		method: "frappe.client.insert",
		args: {
			doc: opportunity_doc,
		},
		callback: function (response) {
			if (!response.exc && response.message) {
				frappe.msgprint({
					title: __("Success"),
					message: __("Opportunity Created"),
					indicator: "green",
				});
			}
		},
		error: function (err) {
			// show server error (if any)
			frappe.msgprint({
				title: __("Error"),
				message: err && err.exc ? err.exc : __("Failed to create Opportunity"),
				indicator: "red",
			});
		},
	});
}
