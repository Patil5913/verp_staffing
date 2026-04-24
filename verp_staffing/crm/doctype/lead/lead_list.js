frappe.listview_settings["Lead"] = {
	refresh(listview) {
		setTimeout(() => {
			let primary_btn = listview.page.wrapper.find(".page-actions .btn-primary");

			if (primary_btn.length) {
				primary_btn.text("+ Add Lead");

				primary_btn.off("click").on("click", function (e) {
					e.preventDefault();
					e.stopPropagation();

					open_custom_dialog();
				});
			}
		}, 50);

		const page = listview.page;
		if (!page) return;

		// setTimeout(() => {
		// 	page.wrapper.find(".add-new-column").hide();

		// 	// Hide "Select Kanban" button
		// 	page.inner_toolbar.find("button").each(function () {
		// 		if ($(this).text().includes("Select Kanban")) {
		// 			$(this).parent().hide();
		// 		}
		// 	});
		// }, 50);

		// setTimeout(() => {
		// 	page.wrapper.find(".add-new-column").hide();
		// }, 50);
	},
	get_indicator: function (doc) {
		const status_colors = {
			Won: "green",
			Lost: "red",
			Interested: "blue",
			Opportunity: "orange",
		};

		return [__(doc.status), status_colors[doc.status] || "black", "status,=," + doc.status];
	},
};

function open_custom_dialog() {
	let dialog = new frappe.ui.Dialog({
		title: "Create Lead",

		fields: [
			{
				fieldname: "name1",
				fieldtype: "Data",
				label: "Lead name",
				reqd: 1,
			},
			{
				fieldname: "personal_phone_number",
				fieldtype: "Data",
				label: "Phone Number (Provide country code with number Exp: +1xxxxxxxxxx)",
				placeholder: "Exp: +1xxxxxxxxxx or +91xxxxxxxxxx",
			},
			{
				fieldname: "email",
				fieldtype: "Data",
				label: "Email",
			},
		],

		primary_action_label: "Save",

		primary_action(values) {
			if (values.personal_phone_number) {
				validate_phone(values.personal_phone_number, "Phone Number");
			}

			let doc = {
				doctype: "Lead",
				name1: values.name1,
				personal_phone_number: values.personal_phone_number,
				email: values.email,
			};

			frappe.call({
				method: "frappe.client.insert",
				args: { doc: doc },
				callback: function (r) {
					if (!r.exc) {
						dialog.hide();
						frappe.set_route("Form", "Lead", r.message.name);
					}
				},
			});
		},

		secondary_action_label: "Edit Full Form",
		secondary_action: function () {
			dialog.hide();
			frappe.new_doc("Lead");
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

function validate_phone(phone, label) {
	phone = (phone || "").trim();

	if (!phone) {
		frappe.throw(`${label} is required`);
	}

	const phone_regex = /^\+[1-9]\d{9,14}$/;

	if (!phone_regex.test(phone)) {
		frappe.throw(`${label} must be in format +countrycode followed by numbers`);
	}

	return true;
}
