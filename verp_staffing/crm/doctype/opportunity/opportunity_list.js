frappe.listview_settings["Opportunity"] = {
	onload(listview) {
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

	refresh: function (listview) {
		setTimeout(() => {
			let primary_btn = listview.page.wrapper.find(".page-actions .btn-primary");

			if (primary_btn.length) {
				primary_btn.text("+ Add Opportunity");

				primary_btn.off("click").on("click", function (e) {
					e.preventDefault();
					e.stopPropagation();

					open_custom_dialog();
				});
			}
		}, 50);
	},

	get_indicator: function (doc) {
		if (doc.status === "Converted") {
			return [__("Converted"), "green", "status,=,Converted"];
		}
		if (doc.status === "Lost") {
			return [__("Lost"), "red", "status,=,Lost"];
		}
		if (doc.status === "Replied") {
			return [__("Replied"), "blue", "status,=,Replied"];
		}
		if (doc.status === "Open") {
			return [__("Open"), "orange", "status,=,Open"];
		}

		// default
		return [__(doc.status), "gray", `status,=,${doc.status}`];
	},
};

function open_custom_dialog() {
	let dialog = new frappe.ui.Dialog({
		title: "Create Opportunity",

		fields: [
			{
				fieldname: "name1",
				fieldtype: "Data",
				label: "Opportunity Name",
				reqd: 1,
			},
			{
				fieldname: "opportunity_from_lead",
				fieldtype: "Link",
				label: "Opportunity From Lead",
				options: "Lead",

				onchange: function () {
					let lead = dialog.get_value("opportunity_from_lead");

					if (lead) {
						frappe.db.get_value("Lead", lead, "name1").then((r) => {
							if (r && r.message) {
								let lead_name = r.message.name1;

								dialog.set_value("name1", lead_name ? lead_name.trim() : "");
							}
						});
					}
				},
			},
			{
				fieldname: "referral_customer",
				fieldtype: "Link",
				label: "Referral From Customer",
				options: "Customer",
			},
		],

		primary_action_label: "Save",

		primary_action(values) {
			let doc = {
				doctype: "Opportunity",
				name1: values.name1,
			};

			// If Lead selected
			if (values.opportunity_from_lead) {
				doc.opportunity_from_lead = values.opportunity_from_lead;
			}

			// If Referral Customer selected
			if (values.referral_customer) {
				doc.referral_customer = values.referral_customer;
			}

			frappe.db.get_value("Employee", { user: frappe.session.user }, "name").then((r) => {
				if (r && r.message && r.message.name) {
					doc.opportunity_owner = r.message.name;
				}

				frappe.call({
					method: "frappe.client.insert",
					args: { doc: doc },
					callback: function (r) {
						if (r.message) {
							dialog.hide();
							frappe.show_alert({
								message: __("Opportunity created"),
								indicator: "green",
							});
							frappe.set_route("Form", "Opportunity", r.message.name);
						}
					},
					error: function (r) {
						frappe.msgprint({
							title: __("Error"),
							message: r.message || __("Failed to create Opportunity"),
							indicator: "red",
						});
					},
				});
			});
		},

		secondary_action_label: "Edit Full Form",
		secondary_action: function () {
			dialog.hide();
			frappe.new_doc("Opportunity");
		},
	});

	dialog.show();

	setTimeout(() => {
		let footer = dialog.$wrapper.find(".modal-footer");

		let secondary_btn = footer.find(".btn-secondary");
		secondary_btn.prependTo(footer); // move to beginning

		footer.css({
			display: "flex",
			justifyContent: "space-between",
		});
	}, 10);
}
