frappe.provide("verp_staffing.setup");

frappe.setup.utils.bind_email_events = function (slide) {
	const email = slide.get_input("business_email");
	const provider = slide.get_input("email_provider");

	email.off(".email_provider").on("input.email_provider change.email_provider", function () {
		update_provider_field(slide);
		const detected = detect_email_provider($(this).val());

		if (detected) {
			slide.get_field("email_provider").set_input(detected);
			apply_provider_defaults(slide, detected);
		}
	});

	slide
		.get_input("business_email")
		.off(".email_provider")
		.on("input.email_provider change.email_provider", function () {
			update_provider_field(slide);
		});

	update_provider_field(slide);
	provider.off(".provider_defaults").on("change.provider_defaults", function () {
		apply_provider_defaults(slide, $(this).val());
	});

	update_provider_field(slide);
};

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
			{
				fieldname: "add_sample_data",
				label: __("Add Sample Data"),
				fieldtype: "Check",
				default: 0,
				description: __(
					"Seeds departments, users, employees, leads, opportunities, " +
						"customers, orders and invoices so you can explore the system " +
						"immediately. You can safely skip this on a production setup.",
				),
			},
			{
				fieldtype: "Section Break",
				label: __("Email Configuration"),
			},
			{
				fieldname: "business_email",
				fieldtype: "Data",
				label: __("Business Email"),
				options: "Email",
				reqd: 1,
			},
			{
				fieldname: "email_password",
				fieldtype: "Password",
				label: __("Password / App Password"),
				reqd: 1,
			},
			{
				fieldname: "email_provider",
				fieldtype: "Autocomplete",
				label: __("Provider"),
				options: Object.entries(verp_staffing.setup.EMAIL_PROVIDERS)
					.map(([key, provider]) => ({
						value: key,
						label: provider.label,
					}))
					.sort((a, b) => a.label.localeCompare(b.label))
					.map((d) => `${d.label}`)
					.join("\n"),
			},
			{
				fieldtype: "Section Break",
				label: __("Additional Domain Settings"),
				collapsible: 1,
				collapsed: 1,
			},

			{
				fieldname: "email_server",
				label: __("Incoming Server"),
				fieldtype: "Data",
			},

			{
				fieldname: "incoming_port",
				label: __("Incoming Port"),
				fieldtype: "Int",
			},
			{
				fieldname: "use_imap",
				label: __("Use IMAP"),
				fieldtype: "Check",
				default: 1,
			},

			{
				fieldname: "use_ssl",
				label: __("Use SSL"),
				fieldtype: "Check",
			},

			{
				fieldname: "use_tls",
				label: __("Use TLS"),
				fieldtype: "Check",
			},
			{
				fieldtype: "Column Break",
			},

			{
				fieldname: "smtp_server",
				label: __("SMTP Server"),
				fieldtype: "Data",
			},

			{
				fieldname: "smtp_port",
				label: __("SMTP Port"),
				fieldtype: "Int",
			},
			{
				fieldname: "use_starttls",
				label: __("Use STARTTLS"),
				fieldtype: "Check",
			},

			{
				fieldname: "use_ssl_for_outgoing",
				label: __("Use SSL for Outgoing"),
				fieldtype: "Check",
			},

			{
				fieldtype: "Section Break",
			},

			{
				fieldname: "append_emails_to_sent_folder",
				label: __("Append Emails to Sent Folder"),
				fieldtype: "Check",
				default: 1,
				hidden: 1,
			},

			{
				fieldname: "sent_folder_name",
				label: __("Sent Folder Name"),
				fieldtype: "Data",
				hidden: 1,
			},
		],
		onload(slide) {
			frappe.setup.utils.bind_email_events(slide);
		},
		on_next(slide) {
			if (!validate_organization_setup(slide)) {
				return false;
			}

			return slide.get_values();
		},
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

function validate_organization_setup(slide) {
	const values = slide.get_values();

	if (!values.company_name) {
		frappe.msgprint(__("Company Name is required."));
		return false;
	}

	if (!values.fy_start_date || !values.fy_end_date) {
		frappe.msgprint(__("Fiscal Year dates are required."));
		return false;
	}
	if (!detect_email_provider(values.business_email) && !values.email_provider) {
		frappe.msgprint(__("Please select your email provider."));
		return false;
	}
	if (
		frappe.datetime.str_to_obj(values.fy_start_date) >=
		frappe.datetime.str_to_obj(values.fy_end_date)
	) {
		frappe.msgprint(__("Fiscal Year End Date must be after Start Date."));
		return false;
	}

	if (!values.business_email) {
		frappe.msgprint(__("Business Email is required."));
		return false;
	}

	if (!values.email_password) {
		frappe.msgprint(__("Email Password is required."));
		return false;
	}

	return true;
}

function detect_email_provider(email) {
	if (!email?.includes("@")) return null;

	const domain = email.split("@").pop().toLowerCase();

	for (const [key, provider] of Object.entries(verp_staffing.setup.EMAIL_PROVIDERS)) {
		if (provider.domains.includes(domain)) {
			return key;
		}
	}

	return null;
}

function update_provider_field(slide) {
	const provider = detect_email_provider(slide.get_value("business_email") || "");

	if (provider) {
		slide.get_field("email_provider").set_input(provider);
		apply_provider_defaults(slide, provider);
	}
}

function apply_provider_defaults(slide, provider) {
	const config =
		verp_staffing.setup.EMAIL_PROVIDERS[provider.toLowerCase().split(" ").join("_")];
	if (!config) return;

	const defaults = config.defaults || {};

	Object.entries(defaults).forEach(([fieldname, value]) => {
		const field = slide.get_field(fieldname);

		if (field) {
			field.set_input(value);
		}
	});
}
