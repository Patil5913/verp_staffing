frappe.listview_settings["Customer"] = {
	add_fields: ["overall_status"],
	get_indicator: function (doc) {
		const color = get_status_color(doc.overall_status);

		return [doc.overall_status || "Unknown", color, "overall_status,=," + doc.overall_status];
	},
	refresh: function (listview) {
		setTimeout(() => {
			let primary_btn = listview.page.wrapper.find(".page-actions .btn-primary");

			if (primary_btn.length) {
				primary_btn.text("+ Add Customer");

				primary_btn.off("click").on("click", function (e) {
					e.preventDefault();
					e.stopPropagation();

					open_custom_dialog();
				});
			}
		}, 50);
	},
};

function get_status_color(status) {
	if (!status) return "gray";

	if (status.includes("Pending")) return "red";
	if (status.includes("Rework")) return "orange";
	if (status.includes("In Progress")) return "blue";

	if (
		status.includes("Completed") ||
		status.includes("Placed") ||
		status.includes("Moved To Onboarding") ||
		status.includes("Moved To CR")
	)
		return "green";

	if (status === "Ready") return "gray";

	return "gray";
}

function open_custom_dialog() {
	let dialog = new frappe.ui.Dialog({
		title: "Create Customer",

		fields: [
			{
				fieldname: "name1",
				fieldtype: "Data",
				label: "Customer Name",
				reqd: 1,
			},
			{
				fieldname: "customer_from",
				fieldtype: "Link",
				label: "Customer From",
				options: "DocType",
				get_query: function () {
					return {
						filters: {
							name: ["in", ["Lead", "Opportunity"]],
						},
					};
				},
				onchange: function () {
					let source = dialog.get_value("customer_from");

					if (source) {
						// 🔥 Update Party label dynamically
						dialog.set_df_property("party_name", "label", source);

						// Clear party_name when source changes
						dialog.set_value("party_name", "");
					}
				},
			},
			{
				fieldname: "party_name",
				fieldtype: "Dynamic Link",
				label: "Party",
				options: "customer_from",
				onchange: function () {
					let source_doctype = dialog.get_value("customer_from");
					let source_name = dialog.get_value("party_name");

					if (source_doctype && source_name) {
						let fetch_field = source_doctype === "Lead" ? "name1" : "title";

						frappe.db.get_value(source_doctype, source_name, fetch_field).then((r) => {
							if (r && r.message) {
								let base_name = r.message[fetch_field];
								dialog.set_value("name1", base_name ? base_name.trim() : "");
							}
						});
					}
				},
			},
		],

		primary_action_label: "Save",

		primary_action(values) {
			frappe.call({
				method: "frappe.client.insert",
				args: {
					doc: {
						doctype: "Customer",
						name1: values.name1,
						customer_from: values.customer_from,
						party_name: values.party_name,
					},
				},
				callback: function (r) {
					if (!r.exc) {
						dialog.hide();
						frappe.set_route("Form", "Customer", r.message.name);
					}
				},
			});
		},

		secondary_action_label: "Edit Full Form",
		secondary_action: function () {
			dialog.hide();
			frappe.new_doc("Customer");
		},
	});

	dialog.show();

	// 🔥 Move "Edit Full Form" to left side
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
