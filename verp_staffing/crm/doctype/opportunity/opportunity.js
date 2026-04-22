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

	async refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Sales",
			doctype: frm.doctype,
			type: "Form",
		};
		frappe.breadcrumbs.update();
		window.render_notes(frm);
		window.render_activity_section(frm);

		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details_html",
			customer: frm.doc.name,
			fields: display_fields,
		});

		if (frm.doc.status == "Converted") {
			frm.set_df_property("status", "read_only", 1);
		}
		frm.set_query("opportunity_owner", function () {
			return {
				filters: [["Employee Assignment Detail", "department", "=", "Sales"]],
			};
		});

		frm.add_custom_button(__("Create Customer"), function () {
			handle_create_customer(frm);
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
	},

	status(frm) {
		const prev_status = frm.doc._previous_status;
		const current_status = frm.doc.status;

		if (current_status === "Converted" && prev_status !== "Converted") {
			handle_create_customer(frm)
				.then(() => {
					frm.doc._previous_status = "Converted";
				})
				.catch(() => {
					// User clicked No — revert status back
					frm.doc._previous_status = prev_status || "Open";
					frm.set_value("status", prev_status || "Open");
					frappe.show_alert({
						message: "Status change cancelled",
						indicator: "orange",
					});
				});
		} else {
			frm.doc._previous_status = current_status;
		}
	},

	opportunity_from_lead: function (frm) {
		frm.trigger("fetch_source_details");
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
});

async function handle_create_customer(frm) {
	// if (frm.is_dirty()) {
	// 	await frm.save();
	// }

	// fetch existing customers
	const r = await frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Customer",
			filters: {
				customer_from: "Opportunity",
				party_name: frm.doc.name,
			},
			fields: ["name", "name1"],
		},
	});

	const customers = r.message || [];

	let message = "";

	if (customers.length) {
		const links = customers
			.map(
				(c) =>
					`<li>
						<a href="/app/customer/${c.name}" target="_blank">
							${c.name1} (${c.name})
						</a>
					</li>`,
			)
			.join("");

		message += `
			<p style="margin-bottom:8px;">
				<strong>Existing Customer(s):</strong>
			</p>
			<ul style="margin-bottom:12px;">
				${links}
			</ul>
		`;
	}

	message += `<p>Do you want to create a new customer?</p>`;

	return new Promise((resolve, reject) => {
		frappe.confirm(
			message,
			async () => {
				const res = await frm.call("create_customer");
				if (res.message && res.message.customer) {
					frappe.show_alert({
						message: __("New Customer {0} created", [res.message.customer]),
						indicator: "green",
					});
					frappe.set_route("Form", "Customer", res.message.customer);
				}
				resolve();
			},
			() => {
				reject(); // user clicked No
			},
		);
	});
}
