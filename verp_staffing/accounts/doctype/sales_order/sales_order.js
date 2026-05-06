// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Order", {
	async refresh(frm) {
		const config = await load_erp_config(frm);
		const requirements = get_requirements_from_config(frm, config);

		if (!config.sendCandidateFormImmediately && requirements.candidate_required) {
			frm.add_custom_button(
				__("Send Details Form"),
				() => send_details_form(frm),
				__("Send"),
			);
		}

		await update_agreement_module(frm);
	},

	services(frm) {
		update_agreement_module(frm);
	},

	async validate(frm) {
		const config = await load_erp_config(frm);
		const requirements = get_requirements_from_config(frm, config);

		if (config.sendAgreementImmediately && requirements.agreement_required) {
			const key = `so_agreement_draft_${frm.doc.name || "new"}`;
			const draft = localStorage.getItem(key);

			if (!draft) {
				frappe.throw(
					"Agreement template must be selected before saving for auto agreement send.",
				);
			}
		}

		if (config.sendCandidateFormImmediately && requirements.candidate_required) {
			let r = await frappe.call({
				method: "verp_staffing.crm.doctype.customer.get_customer_email",
				args: { customer: frm.doc.customer },
			});

			const recipient = r.message;

			const res = await frappe.db.get_value("Customer", frm.doc.customer, "lead_details");
			const lead_name = res.message.lead_details;

			if (!recipient) {
				frappe.throw(`
					Email is required to send agreement.<br><br>
					<a href="/app/lead-detail-form/${lead_name}" target="_blank">
						➜ Open Lead Detail Form
					</a>
				`);
			}
		}
	},

	before_save(frm) {
		if (frm.doc.__islocal) {
			frm._is_first_save = frm.doc.__islocal;
			frm._temp_name = frm.doc.name;
		}
	},

	async after_save(frm) {
		if (!frm._is_first_save) {
			return;
		}

		if (frm._temp_name) {
			const newKey = `so_agreement_draft_${frm.doc.name}`;

			Object.keys(localStorage).forEach((k) => {
				if (k.includes(frm._temp_name)) {
					const draft = localStorage.getItem(k);

					if (draft) {
						localStorage.setItem(newKey, draft);
					}

					localStorage.removeItem(k);
				}
			});
		}

		const config = await load_erp_config(frm);
		const requirements = get_requirements_from_config(frm, config);

		if (config.sendCandidateFormImmediately && requirements.candidate_required) {
			send_details_form(frm);
		}

		if (config.sendAgreementImmediately && requirements.agreement_required) {
			const key = `so_agreement_draft_${frm.doc.name}`;
			const draft = localStorage.getItem(key);

			if (!draft) {
				return;
			}

			const payload = JSON.parse(draft);

			const r = await frappe.call({
				method: "verp_staffing.crm.api.agreement.submit_and_generate",
				args: {
					sales_order: frm.doc.name,
					template: payload.template,
					data: JSON.stringify(payload.data),
					send_email: 1,
				},
			});

			if (!r.message) {
				frappe.throw("Agreement generation failed");
			}

			frappe.msgprint("Agreement send successfully.");
			localStorage.removeItem(key);

			await frm.reload_doc();
		}
	},
});

async function update_agreement_module(frm) {
	const config = await load_erp_config(frm);
	const requirements = get_requirements_from_config(frm, config);

	window.render_agreement_module({
		frm,
		wrapper: frm.get_field("agreement_html").$wrapper,
		sales_order: frm.doc.name,
		allow_create: true,
		auto_mode: config.sendAgreementImmediately && requirements.agreement_required && frm.is_new(),
	});
}

async function load_erp_config(frm) {
	if (frm._erp_config) {
		return frm._erp_config;
	}

	const r = await frappe.db.get_value("ERP Configuration", "ERP Configuration", [
		"send_candidate_form_immediatly_after_sales_order_creation",
		"send_agreement_immediatly_after_sales_order_creation",
		"candidate_details_form_fields",
	]);

	let rawConfig = {};
	try {
		rawConfig = r.message.candidate_details_form_fields
			? JSON.parse(r.message.candidate_details_form_fields)
			: {};
	} catch (e) {
		console.error("Invalid candidate_details_form_fields JSON", e);
		rawConfig = {};
	}

	// 🔥 Normalize structure (this is critical, don't skip)
	const serviceConfig = {};

	Object.keys(rawConfig).forEach((service) => {
		const cfg = rawConfig[service] || {};

		serviceConfig[service] = {
			fields: Array.isArray(cfg.fields) ? cfg.fields : [],
			isAgreementRequired: !!cfg.is_agreement_required,
			isCandidateFormRequired: !!cfg.is_candidate_form_required,
		};
	});

	frm._erp_config = {
		sendCandidateFormImmediately: Number(
			r.message.send_candidate_form_immediatly_after_sales_order_creation,
		),
		sendAgreementImmediately: Number(
			r.message.send_agreement_immediatly_after_sales_order_creation,
		),

		// 🔥 full service-wise config
		serviceConfig: serviceConfig,
	};

	return frm._erp_config;
}

function get_requirements_from_config(frm, config) {
	const services = (frm.fields_dict.services.get_value() || [])
		.map((row) => row.service)
		.filter(Boolean);

	let agreement_required = false;
	let candidate_required = false;

	services.forEach((service) => {
		const cfg = config.serviceConfig[service];

		if (!cfg) return;

		if (cfg.isAgreementRequired) agreement_required = true;
		if (cfg.isCandidateFormRequired) candidate_required = true;
	});

	return {
		agreement_required,
		candidate_required,
	};
}

async function send_details_form(frm) {
	let recipient = await frappe.call({
		method: "verp_staffing.crm.doctype.customer.get_customer_email",
		args: { customer: frm.doc.customer },
	});
	recipient = recipient.message;

	if (!recipient) {
		const res = await frappe.db.get_value("Customer", frm.doc.customer, "lead_details");
		const lead_name = res.message.lead_details;

		frappe.throw(`
					Email is required to send agreement.<br><br>
					<a href="/app/lead-detail-form/${lead_name}" target="_blank">
						➜ Open Lead Detail Form
					</a>
				`);
		return;
	}
	frappe.call({
		method: "verp_staffing.accounts.doctype.sales_order.sales_order.send_details_form_notification",
		args: {
			recipient,
			sales_order: frm.doc.name,
			customer: frm.doc.customer,
		},
		callback(r) {
			if (!r.message) frappe.throw("Failed to send email, retry again.");
			frappe.msgprint("Details form sent successfully.");
			frm.reload_doc();
		},
	});
}
