// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt
let interview_offset = 0;
const interview_limit = 5;
let CURRENT_EMPLOYEE = null;

frappe.ui.form.on("Customer", {
	setup(frm) {
		$(frm.wrapper).on("shown.bs.tab", ".nav-link", () => {
			render_tab_data(frm);
		});
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

		set_customer_owner(frm);

		window.render_notes(frm);
		window.render_activity_section(frm);

		if (frappe.session.user != "Administrator") {
			toggle_tab_view(frm);
		}

		frm.set_query("customer_owner", function () {
			return {
				filters: [["Employee Assignment Detail", "department", "=", "Sales"]],
			};
		});

		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Employee",
				filters: { user: frappe.session.user },
				fieldname: "name",
			},
			callback(r) {
				CURRENT_EMPLOYEE = r.message?.name;
			},
		});

		if (!frm.is_new()) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Employee",
					filters: { user: frappe.session.user },
					fieldname: "name",
				},
				callback: function (r) {
					const current_employee = r.message && r.message.name;
					const is_customer_owner = current_employee === frm.doc.customer_owner;

					if (is_customer_owner) {
						// Check if candidate form required
						frappe.call({
							method: "verp_staffing.crm.api.permission_request.get_candidate_form_required_status",
							args: { customer_name: frm.doc.name },
							callback: function (res) {
								if (!res.message || !res.message.required) return;

								// Candidate form required — check if already pending
								frappe.call({
									method: "verp_staffing.crm.api.permission_request.get_owner_pending_field_update_request",
									args: { customer_name: frm.doc.name },
									callback: function (pend_res) {
										if (pend_res.message && pend_res.message.has_pending) {
											frappe.show_alert(
												{
													message: __(
														"Your update request is pending manager approval.",
													),
													indicator: "orange",
												},
												5,
											);
											return;
										}
										// Show Update Detail button
										frm.add_custom_button(__("Update Detail"), () => {
											customer_owner_open_update_detail_dialog(frm);
										});
									},
								});
							},
						});
					}
					customer_show_accept_updates(frm);
				},
			});
		}
		render_tab_data(frm);
		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details_html",
			customer: frm.doc.name,
			fields: display_fields,
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Customer";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		window.add_forward_button(frm,service_name="Sales");

		if (frm.doc.chat_access !== "Active") {
			frm.add_custom_button("Portal & Chat Access", () => open_portal_access_dialog(frm));
		} else {
			frm.add_custom_button("Revoke Portal Access", () => {
				frappe.confirm(
					"The customer will be signed out and lose access to the portal and chat straight away. You can restore it later by sending access again. Continue?",
					() => {
						frappe.call({
							method: "verp_staffing.crm.api.customer_chat.revoke_portal_access",
							args: { customer: frm.doc.name },
							freeze: true,
							callback() {
								frappe.show_alert({ message: "Portal access revoked", indicator: "orange" });
								frm.reload_doc();
							},
						});
					}
				);
			});
		}
	},

	sales_order: function (frm) {
		frappe.new_doc("Sales Order", { customer: frm.doc.name });
	},

	customer_from: function (frm) {
		if (frm.doc.customer_from) {
			frm.set_df_property("party_name", "label", frm.doc.customer_from);
		}
		set_customer_owner(frm);
		set_customer_owner(frm);
	},

	party_name: function (frm) {
		frm.trigger("fetch_source_details");
		if (!frm.is_new()) {
			load_lead_details_after_save(frm);
		}
		if (frm.doc.customer_from && frm.doc.party_name) {
			let source_doctype = frm.doc.customer_from;
			let source_name = frm.doc.party_name;
			let fetch_field = source_doctype === "name1";

			frappe.db.get_value(source_doctype, source_name, fetch_field).then((r) => {
				if (r && r.message) {
					let base_name = r.message[fetch_field];
					frm.set_value("name1", base_name ? base_name.trim() : "");
				}
			});
		}
		set_customer_owner(frm);
	},
	validate: function (frm) {
		if (frm.doc.customer_from === "Lead" && !frm.doc.party_name) {
			frappe.msgprint(__("Please select a Lead."));
			frappe.validated = false;
		} else if (frm.doc.customer_from === "Opportunity" && !frm.doc.party_name) {
			frappe.msgprint(__("Please select an Opportunity."));
			frappe.validated = false;
		}
	},
});

function render_tab_data(frm) {
	if (frm.is_new()) return;
	const active_tab = frm.active_tab_map && frm.active_tab_map[frm.doc.name];
	if (active_tab.df.fieldname === "history_tab") {
		load_customer_history_if_needed(frm);
	} else if (active_tab.df.fieldname === "sales_tab") {
		window.render_owned_sales_orders(frm, "sales_content", frm.doc.name);
	}
}

function load_customer_history_if_needed(frm) {
	if (!frm.doc.name) return;
	if (frm.__history_loaded_for === frm.doc.name) return; // already loaded for this doc

	frm.__history_loaded_for = frm.doc.name;

	if (frm.fields_dict.customer_details) {
		frm.fields_dict.customer_details.$wrapper.html(
			"<p style='color:#888'>Loading history...</p>",
		);
	}

	window.verp_staffing.render_customer_history_widget(frm, {
		fieldname: "customer_details",
		customer: frm.doc.name,
		doctype: "Customer",
	});
}

function set_customer_owner(frm) {
	if (frm.doc.customer_owner) return;

	if (frm.doc.customer_from === "Opportunity" && frm.doc.party_name) {
		frappe.db.get_value("Opportunity", frm.doc.party_name, "opportunity_owner").then((r) => {
			if (!r.message || !r.message.opportunity_owner) return;
			frm.set_value("customer_owner", r.message.opportunity_owner);
		});
	} else if (frm.doc.customer_from === "Lead" && frm.doc.party_name) {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Employee",
				filters: [["Employee", "user", "=", frappe.session.user]],
				fields: ["name"],
				limit: 1,
			},
			callback: function (r) {
				if (r.message && r.message.length > 0) {
					frm.set_value("customer_owner", r.message[0].name);
				}
			},
		});
	} else {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Employee",
				filters: [["Employee", "user", "=", frappe.session.user]],
				fields: ["name"],
				limit: 1,
			},
			callback: function (r) {
				if (r.message && r.message.length > 0) {
					frm.set_value("customer_owner", r.message[0].name);
				}
			},
		});
	}
}

function toggle_tab_view(frm) {
	frappe.call({
		method: "verp_staffing.employee.doctype.employee.employee.get_user_departments",
		callback: function (r) {
			const departments = r.message || [];

			// reset all first (important)
			frm.toggle_display("sales_tab", true);
			frm.toggle_display("sales_content", true);
			frm.toggle_display("technical_tab", true);
			frm.toggle_display("technical_content", true);
			frm.toggle_display("marketing_tab", true);
			frm.toggle_display("marketing_content", true);

			// Onboarding (NEW)
			if (!departments.includes("Onboarding")) {
				// hide onboarding section if not onboarding user
				frm.toggle_display("after_placement_details", false);
			} else {
				frm.toggle_display("after_placement_details", true);
			}
		},
	});
}

function customer_owner_open_update_detail_dialog(frm) {
	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_lead_detail_field_values",
		args: { customer_name: frm.doc.name },
		callback: function (r) {
			const current_values = r.message || {};

			frappe.call({
				method: "verp_staffing.crm.api.permission_request.get_customer_owner_updatable_fields",
				callback: function (fields_res) {
					const dept_fields = fields_res.message || {
						simple_fields: {},
						table_fields: {},
					};
					_open_update_detail_dialog(
						frm,
						current_values,
						dept_fields.simple_fields || {},
						dept_fields.table_fields || {},
						"owner",
					);
				},
			});
		},
	});
}

function customer_show_accept_updates(frm) {
	$(`button:contains("Accept Updates")`).closest(".btn-group").remove();
	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_all_pending_field_update_requests",
		args: { customer_name: frm.doc.name },
		callback(r) {
			$(`button:contains("Accept Updates")`).closest(".btn-group").remove();
			if (!r.message || !r.message.length) return;

			frm.add_custom_button(__("Accept Updates"), () => {
				_open_accept_updates_dialog(frm, r.message, "owner");
			});
		},
	});
}

// One button for the customer's portal and chat: it opens the email for review, and sending
// it is what creates the customer's website user (nothing is created with the Customer).
function open_portal_access_dialog(frm) {
	frappe.call({
		method: "verp_staffing.crm.api.customer_chat.get_portal_access_draft",
		args: { customer: frm.doc.name },
		freeze: true,
		callback(r) {
			const draft = r.message;
			if (!draft) return;
			if (!draft.chat_installed) {
				frappe.msgprint("The Vrugle Chat app is not installed on this site.");
				return;
			}
			if (draft.ended) {
				frappe.msgprint("This customer's service has ended, so access cannot be issued.");
				return;
			}
			if (!draft.to) {
				frappe.msgprint({
					title: "Email Missing",
					message: "Add an email address to this customer's Lead Details first.",
				});
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: draft.already_sent ? "Resend Portal & Chat Access" : "Send Portal & Chat Access",
				size: "large",
				fields: [
					{ fieldname: "to", fieldtype: "Data", label: "To", read_only: 1, default: draft.to },
					{ fieldname: "subject", fieldtype: "Data", label: "Subject", reqd: 1, default: draft.subject },
					{ fieldname: "message", fieldtype: "Text Editor", label: "Message", default: draft.message },
					{
						fieldname: "details",
						fieldtype: "HTML",
						options: `<div class="text-muted small" style="border:1px solid var(--border-color);border-radius:8px;padding:10px 12px">
							The email also contains the sign-in link (${frappe.utils.escape_html(draft.login_url)}),
							their email <b>${frappe.utils.escape_html(draft.to)}</b> and a newly generated password.
							${draft.already_sent ? "<br><b>Their current password will stop working.</b>" : ""}
						</div>`,
					},
				],
				primary_action_label: draft.already_sent ? "Resend" : "Send",
				primary_action(values) {
					dialog.disable_primary_action();
					frappe.call({
						method: "verp_staffing.crm.api.customer_chat.send_portal_access",
						args: { customer: frm.doc.name, subject: values.subject, message: values.message },
						freeze: true,
						callback(res) {
							if (res.message) {
								dialog.hide();
								frappe.show_alert({ message: "Portal & chat access sent", indicator: "green" });
								frm.reload_doc();
							}
						},
						error() {
							dialog.enable_primary_action();
						},
					});
				},
			});
			dialog.show();
		},
	});
}
