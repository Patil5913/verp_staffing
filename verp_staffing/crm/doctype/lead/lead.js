// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead", {
	onload(frm) {
		// apply_field_readonly_for_lead_owner(frm);

		// Always keep field visible but locked
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
		// apply_field_readonly_for_lead_owner(frm);

		if (frm.is_new()) return;

		// Fetch status and lead_owner from DB directly
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Lead",
				filters: { name: frm.doc.name },
				fieldname: ["status", "lead_owner"],
			},
			callback: function (lead_res) {
				if (!lead_res.message) return;

				const { status, lead_owner } = lead_res.message;

				if (status === "Opportunity") {
					frappe.call({
						method: "frappe.client.get_value",
						args: {
							doctype: "Employee",
							filters: { user: frappe.session.user },
							fieldname: "name",
						},
						callback: function (r) {
							const current_employee = r.message && r.message.name;
							const is_lead_owner = current_employee === lead_owner;

							// if (is_lead_owner) {
							// 	frm.add_custom_button(__("Request for Update"), () => {
							// 		open_request_for_update_dialog(frm);
							// 	});
							// } else {
							// 	check_and_show_give_permission_button(frm);
							// }
						},
					});
				} else {
					frm.add_custom_button("Create Opportunity", () => {
						open_create_opportunity_dialog(frm);
					});
				}
			},
		});

		if (frm.is_new()) {
			frm.add_custom_button("Show Form Tour", () => {
				const tour_name = "Lead Form";
				frm.tour.init({ tour_name }).then(() => frm.tour.start());
			});
		}

		const roles = frappe.user_roles;

		if (roles.includes("Extra Menu Item Not Show")) {
			const hideElements = ({ selectors = [], keywordSelectors = [], keywords = [] }) => {
				selectors.forEach((sel) => {
					const el = document.querySelector(sel);
					if (el) el.style.display = "none";
				});
				keywordSelectors.forEach((sel) => {
					document.querySelectorAll(sel).forEach((el) => {
						const text = el.innerText?.trim();
						if (text && keywords.some((k) => text.includes(k))) {
							el.style.display = "none";
							const li = el.closest("li");
							if (li) li.style.display = "none";
						}
					});
				});
			};

			const MENU_HIDE = ["Links", "Duplicate", "Copy to Clipboard"];

			const cleanMenu = () => {
				MENU_HIDE.forEach((label) => {
					try {
						frm.page.remove_menu_item(label);
					} catch {}
				});
				hideElements({
					keywordSelectors: [".dropdown-menu .dropdown-item"],
					keywords: MENU_HIDE,
				});
			};

			$(frm.page.wrapper).on("shown.bs.dropdown", cleanMenu);

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

			const runCleanup = () => {
				cleanMenu();
				cleanSidebar();
			};
			runCleanup();

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

// this code is unnessary if allthing working right so remove it

// frappe.ui.form.on("Lead Course", {
// 	start_date(frm, cdt, cdn) {
// 		let row = locals[cdt][cdn];
// 		window.LeadCourse.check_row(row);
// 	},
// 	end_date(frm, cdt, cdn) {
// 		let row = locals[cdt][cdn];
// 		window.LeadCourse.check_row(row);
// 	},
// 	grade(frm, cdt, cdn) {
// 		let row = locals[cdt][cdn];
// 		window.LeadCourse.check_row(row);
// 	},
// });

// function open_request_for_update_dialog(frm) {
// 	frappe.call({
// 		method: "verp_staffing.crm.api.permission_request._check_permission_status",
// 		args: { ref_doctype: frm.doctype, ref_name: frm.doc.name },
// 		callback(r) {
// 			const status = r.message && r.message.status;

// 			// if (status === "approved") {
// 			// 	// Permission still active — redirect to Lead Detail Form
// 			// 	redirect_to_lead_detail_form(frm);
// 			// 	return;
// 			// }

// 			if (status === "expired") {
// 				frappe.show_alert(
// 					{
// 						message: __(
// 							"Your previous permission has expired. You can request again.",
// 						),
// 						indicator: "orange",
// 					},
// 					5,
// 				);
// 			} else if (status === "pending") {
// 				frappe.show_alert(
// 					{
// 						message: __(
// 							"Your request is already pending. Please wait for your manager to approve it.",
// 						),
// 						indicator: "orange",
// 					},
// 					5,
// 				);
// 				return;
// 			}

// 			// Show dialog to enter reason
// 			const dialog = new frappe.ui.Dialog({
// 				title: __("Request Permission to Update Email"),
// 				fields: [
// 					{
// 						fieldname: "reason",
// 						fieldtype: "Small Text",
// 						label: __("Reason for Update"),
// 						reqd: 1,
// 						description: __(
// 							"Explain why you need to edit the email field on this Lead.",
// 						),
// 					},
// 				],
// 				primary_action_label: __("Send Request"),
// 				primary_action(values) {
// 					dialog.hide();
// 					frappe.call({
// 						method: "verp_staffing.crm.api.permission_request._request_permission",
// 						args: {
// 							ref_doctype: frm.doctype,
// 							ref_name: frm.doc.name,
// 							reason: values.reason,
// 						},
// 						// freeze: true,
// 						// freeze_message: __("Sending request to your manager..."),
// 						callback(res) {
// 							if (res.message && res.message.status === "success") {
// 								frappe.show_alert(
// 									{
// 										message: __(
// 											`Request sent to manager <b>${res.message.manager_employee}</b>. You will be notified when permission is granted.`,
// 										),
// 										indicator: "blue",
// 									},
// 									7,
// 								);
// 							}
// 						},
// 					});
// 				},
// 			});

// 			dialog.show();
// 		},
// 	});
// }

// function check_and_show_give_permission_button(frm) {
// 	frappe.call({
// 		method: "verp_staffing.crm.api.permission_request._check_pending_for_manager",
// 		args: { ref_doctype: frm.doctype, ref_name: frm.doc.name },
// 		callback(r) {
// 			if (!r.message || !r.message.has_pending) return;

// 			const { requested_by, reason } = r.message;

// 			$(`button:contains("Give Permission")`).closest(".btn-group").remove();

// 			frm.add_custom_button(__("Give Permission"), () => {
// 				// Dialog with Approve AND Decline
// 				const perm_dialog = new frappe.ui.Dialog({
// 					title: __("Permission Request"),
// 					fields: [
// 						{
// 							fieldtype: "HTML",
// 							fieldname: "request_info",
// 							options: `
//                                 <div style="padding: 10px 0;">
//                                     <p>
//                                         <b>${requested_by}</b> has requested permission
//                                         to update the email field on this Lead.
//                                     </p>
//                                     <p><b>Reason:</b> ${reason}</p>
//                                     <p>
//                                         If approved, permission will be valid for
//                                         <b>${r.message.expires_in_minutes} minutes</b> only.
//                                     </p>
//                                 </div>
//                             `,
// 						},
// 					],
// 					primary_action_label: __("Approve"),
// 					primary_action() {
// 						perm_dialog.hide();
// 						frappe.call({
// 							method: "verp_staffing.crm.api.permission_request._give_permission",
// 							args: { ref_doctype: frm.doctype, ref_name: frm.doc.name },
// 							callback(res) {
// 								if (res.message && res.message.status === "approved") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												`Permission granted for ${res.message.expires_in_minutes} minutes. <b>${requested_by}</b> has been notified.`,
// 											),
// 											indicator: "green",
// 										},
// 										6,
// 									);
// 									frm.reload_doc();
// 								}
// 							},
// 						});
// 					},
// 					secondary_action_label: __("Decline"),
// 					secondary_action() {
// 						perm_dialog.hide();
// 						frappe.call({
// 							method: "verp_staffing.crm.api.permission_request._decline_permission",
// 							args: { ref_doctype: frm.doctype, ref_name: frm.doc.name },
// 							callback(res) {
// 								if (res.message && res.message.status === "declined") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												`Request declined. <b>${requested_by}</b> has been notified.`,
// 											),
// 											indicator: "red",
// 										},
// 										6,
// 									);
// 									frm.reload_doc();
// 								}
// 							},
// 						});
// 					},
// 				});
// 				perm_dialog.show();
// 			});
// 		},
// 	});
// }

// // make field read only after lead become opportunity

// function apply_field_readonly_for_lead_owner(frm) {
// 	if (frm.is_new()) return;

// 	// Fetch lead_owner and status directly from DB
// 	// because frm.doc may not have them loaded yet
// 	frappe.call({
// 		method: "frappe.client.get_value",
// 		args: {
// 			doctype: "Lead",
// 			filters: { name: frm.doc.name },
// 			fieldname: ["status", "lead_owner"],
// 		},
// 		callback: function (lead_res) {
// 			if (!lead_res.message) return;

// 			const { status, lead_owner } = lead_res.message;

// 			if (status !== "Opportunity") return;

// 			// Check if logged-in user is the lead owner
// 			frappe.call({
// 				method: "frappe.client.get_value",
// 				args: {
// 					doctype: "Employee",
// 					filters: { user: frappe.session.user },
// 					fieldname: "name",
// 				},
// 				callback: function (emp_res) {
// 					if (!emp_res.message) return;
// 					if (emp_res.message.name !== lead_owner) return;

// 					// Lead owner — always lock source
// 					frm.set_df_property("source", "read_only", 1);
// 					frm.refresh_field("source");

// 					// Check permission status for email
// 					frappe.call({
// 						method: "verp_staffing.crm.api.permission_request._check_permission_status",
// 						args: {
// 							ref_doctype: "Lead",
// 							ref_name: frm.doc.name,
// 						},
// 						callback: function (perm_res) {
// 							const perm = perm_res.message && perm_res.message.status;

// 							if (perm === "approved") {
// 								frm.set_df_property("email", "read_only", 0);
// 								frm.refresh_field("email");
// 								frappe.show_alert(
// 									{
// 										message: __(
// 											"Permission granted. You can now update the email field.",
// 										),
// 										indicator: "green",
// 									},
// 									5,
// 								);
// 							} else {
// 								frm.set_df_property("email", "read_only", 1);
// 								frm.refresh_field("email");

// 								if (perm === "pending") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												"Email is locked. Your permission request is pending manager approval.",
// 											),
// 											indicator: "orange",
// 										},
// 										5,
// 									);
// 								} else if (perm === "declined") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												"Email is locked. Your permission request was declined. Please request again.",
// 											),
// 											indicator: "red",
// 										},
// 										5,
// 									);
// 								} else if (perm === "expired") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												"Email is locked. Your permission has expired. Please request again.",
// 											),
// 											indicator: "orange",
// 										},
// 										5,
// 									);
// 								}
// 							}
// 						},
// 					});
// 				},
// 			});
// 		},
// 	});
// }

function open_create_opportunity_dialog(frm) {
	if (frm.is_dirty()) {
		frm.save().then(() => {
			open_create_opportunity_dialog(frm);
		});
		return;
	}

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Opportunity",
			filters: { opportunity_from_lead: frm.doc.name },
			filters: { opportunity_from_lead: frm.doc.name },
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
								return { filters: { department: "Sales" } };
							},
						},
					],
					primary_action_label: __("Create"),
					primary_action(values) {
						dialog.hide();
						if (values.manual_assign) {
							create_opportunity(frm, values.opportunity_owner);
						} else {
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
	frappe.call({
		method: "frappe.client.insert",
		args: {
			doc: {
				doctype: "Opportunity",
				opportunity_from_lead: frm.doc.name,
				opportunity_owner: owner,
				name1: frm.doc.name1,
			},
		},
		callback: function (response) {
			frm.reload_doc();
			if (!response.exc && response.message) {
				frappe.msgprint({
					title: "Success",
					message: "Opportunity Created",
					indicator: "green",
				});
				frm.reload_doc();
			}
		},
		error: function (err) {
			frappe.msgprint({
				title: __("Error"),
				message: err && err.exc ? err.exc : __("Failed to create Opportunity"),
				indicator: "red",
			});
		},
	});
}
