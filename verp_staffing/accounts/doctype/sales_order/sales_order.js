// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Order", {
	async refresh(frm) {
		const config = await load_erp_config(frm);
		const requirements = await get_service_requirements(frm);

		if (!config.sendCandidateFormImmediately && requirements.candidate_required) {
			frm.add_custom_button(
				__("Send Details Form"),
				() => send_details_form(frm),
				__("Send"),
			);
		}

		if (requirements.agreement_required) {
			if (!config.sendAgreementImmediately && !frm.doc.agreement) {
				frm.add_custom_button(
					__("Send Agreement"),
					async () => {
						const key = `so_agreement_draft_${frm.doc.name}`;
						const draft = localStorage.getItem(key);

						if (!draft) {
							frappe.throw("Choose a template first");
							return;
						}

						const payload = JSON.parse(draft);

						const r = await frappe.call({
							method: "verp_staffing.crm.api.agreement.submit_and_generate",
							args: {
								sales_order: frm.doc.name,
								template: payload.template,
								data: JSON.stringify(payload.data),
							},
						});

						if (!r.message) {
							frappe.throw("Agreement generation failed");
						}

						localStorage.removeItem(key);

						await frm.reload_doc();

						send_agreement(frm);
					},
					__("Send"),
				);
			}

			if (frm.doc.agreement) {
				frm.add_custom_button("Download Agreement", function () {
					frappe.call({
						method: "verp_staffing.crm.api.agreement.download_agreement",
						args: { agreement: frm.doc.agreement },
						callback(r) {
							if (!r.message) {
								frappe.msgprint("No agreement file found.");
								return;
							}

							window.open(r.message.file_url);
						},
					});
				});
			}
		}

		render_agreement_ui(frm);
	},

	async validate(frm) {
		const config = await load_erp_config(frm);
		const requirements = await get_service_requirements(frm);

		if (config.sendAgreementImmediately && requirements.agreement_required) {
			const key = `so_agreement_draft_${frm.doc.name || "new"}`;
			const draft = localStorage.getItem(key);

			if (!draft) {
				frappe.throw("Agreement template must be selected before saving.");
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
		const requirements = await get_service_requirements(frm);

		if (config.sendCandidateFormImmediately && requirements.candidate_required) {
			console.log("immidiate send_details_form hit ++++++");

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
				},
			});

			if (!r.message) {
				frappe.throw("Agreement generation failed");
			}

			localStorage.removeItem(key);

			await frm.reload_doc();

			send_agreement(frm);
		}
	},
});

async function load_erp_config(frm) {
	if (frm._erp_config) {
		return frm._erp_config;
	}

	const r = await frappe.db.get_value("ERP Configuration", "ERP Configuration", [
		"send_candidate_form_immediatly_after_sales_order_creation",
		"send_agreement_immediatly_after_sales_order_creation",
	]);

	frm._erp_config = {
		sendCandidateFormImmediately: Number(
			r.message.send_candidate_form_immediatly_after_sales_order_creation,
		),
		sendAgreementImmediately: Number(
			r.message.send_agreement_immediatly_after_sales_order_creation,
		),
	};

	return frm._erp_config;
}

async function get_service_requirements(frm) {
	if (!frm.doc.services || frm.doc.services.length === 0) {
		return {
			candidate_required: false,
			agreement_required: false,
		};
	}

	const service_names = frm.doc.services.map((d) => d.service);

	const services = await frappe.db.get_list("Service", {
		fields: ["is_candidate_form_required", "is_agreement_required"],
		filters: {
			name: ["in", service_names],
		},
		limit: service_names.length,
	});

	let candidate_required = false;
	let agreement_required = false;

	services.forEach((s) => {
		if (s.is_candidate_form_required) {
			candidate_required = true;
		}
		if (s.is_agreement_required) {
			agreement_required = true;
		}
	});

	return {
		candidate_required,
		agreement_required,
	};
}

function render_agreement_ui(frm) {
	const wrapper = frm.get_field("agreement_html").$wrapper;
	wrapper.empty();

	if (frm.doc.agreement) {
		frappe.call({
			method: "frappe.client.get",
			args: { doctype: "Agreement", name: frm.doc.agreement },
			callback(r) {
				if (!r.message) {
					frappe.msgprint("Agreement not found.");
					return;
				}

				const pdf_url = r.message.pdf || "";
				if (pdf_url) {
					wrapper.append(`
                        <div style="padding: 10px;">
                            <h3>Agreement Already Created</h3>
                            <a href="${pdf_url}" class="btn btn-primary" download style="margin-bottom: 15px;">
                                Download Agreement PDF
                            </a>
                            <div style="margin-top:20px;">
                                <embed src="${pdf_url}" type="application/pdf" width="100%" height="600px" />
                            </div>
                        </div>
                    `);
				} else {
					wrapper.append(
						`<p style="color:red;">Agreement already created, but PDF file missing.</p>`,
					);
				}
			},
		});
		return; // Stop loading the builder if agreement exists
	}

	wrapper.append(`
        <div id="agreement_container">
            <h3>Agreement Builder</h3>
            <label>Choose Template</label>
            <select id="ag_template" class="form-control"></select>
            <div id="ag_dynamic_form" style="margin-top: 20px;"></div>
            <button class="btn btn-primary" id="ag_preview" style="margin-top: 15px;">Preview</button>
            <button class="btn btn-success" id="ag_submit" style="margin-left: 10px; margin-top: 15px;">Save</button>
        </div>
    `);

	load_templates(frm);
	bind_events(frm);
}

function load_templates(frm) {
	const select = frm.get_field("agreement_html").$wrapper.find("#ag_template");

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Pdf Agreement Template",
			filters: { is_active: 1 },
			fields: ["name", "title"],
		},
		callback(r) {
			select.empty();
			select.append(`<option value="">Select</option>`);
			(r.message || []).forEach((t) => {
				select.append(`<option value="${t.name}">${t.title || t.name}</option>`);
			});
		},
	});
}

function bind_events(frm) {
	const wrap = frm.get_field("agreement_html").$wrapper;

	wrap.on("change", "#ag_template", () => load_form_fields(frm));
	wrap.on("click", "#ag_preview", () => preview_inline(frm));
	wrap.on("click", "#ag_submit", () => submit_inline(frm));
}

function load_form_fields(frm) {
	const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
	const form_div = frm.get_field("agreement_html").$wrapper.find("#ag_dynamic_form");

	if (!template) {
		form_div.empty();
		return;
	}

	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Pdf Agreement Template", name: template },
		callback(r) {
			const tpl = r.message;
			const blocks = JSON.parse(tpl.fields_json || "[]");
			form_div.empty();

			blocks.forEach((b) => {
				if (["Text", "Number", "Date"].includes(b.type)) {
					form_div.append(`
                        <div style="margin-bottom: 10px;">
                            <label>${b.label || b.name}</label>
                            <input type="${b.type ?? "text"}" class="form-control ag-field"
                                data-field="${b.name}">
                        </div>
                    `);
				}
			});
		},
	});
}

function preview_inline(frm) {
	const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
	if (!template) return frappe.msgprint("Choose a template first");

	const data = collect_so_agreement_data(frm);

	frappe.call({
		method: "verp_staffing.crm.api.agreement.preview_agreement",
		args: { template, data: JSON.stringify(data) },
		callback(r) {
			if (!r.message) return frappe.msgprint("Preview error");
			window.open(r.message.file_url);
		},
	});
}

async function submit_inline(frm) {
	const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
	if (!template) {
		frappe.throw("Choose a template first");
	}

	const data = collect_so_agreement_data(frm);
	frappe.confirm("Confirm template selection?", () => {
		const key = `so_agreement_draft_${frm.doc.name}`;

		const payload = {
			template: template,
			data: data,
			timestamp: Date.now(),
		};
		localStorage.setItem(key, JSON.stringify(payload));
	});
}

function collect_so_agreement_data(frm) {
	const data = {};
	frm.fields_dict.agreement_html.$wrapper.find(".ag-field").each(function () {
		const key = $(this).data("field");
		data[key] = $(this).val();
	});

	// Include payment_terms
	data["Payment_Terms"] = (frm.doc.payment_terms || []).map((r) => ({
		date: r.date,
		amount: r.amount,
		is_received: r.is_received,
	}));

	return data;
}

async function send_agreement(frm) {
	let recipient = await frappe.call({
		method: "verp_staffing.crm.api.agreement.get_customer_email",
		args: { customer: frm.doc.customer },
	});
	recipient = recipient.message;

	if (!recipient) {
		frappe.msgprint(`Email not found for Customer: ${frm.doc.customer}`);
		return;
	}
	frappe.call({
		method: "verp_staffing.accounts.doctype.sales_order.sales_order.send_agreement_notification",
		args: {
			recipient,
			sales_order: frm.doc.name,
			customer: frm.doc.customer,
			agreement: frm.doc.agreement,
		},
		callback(r) {
			if (!r.message) frappe.throw("Failed to send email, retry again.");
			frappe.msgprint("Agreement created and sent successfully.");
			frm.reload_doc();
		},
	});
}

async function send_details_form(frm) {
	let recipient = await frappe.call({
		method: "verp_staffing.crm.api.agreement.get_customer_email",
		args: { customer: frm.doc.customer },
	});
	recipient = recipient.message;

	if (!recipient) {
		frappe.msgprint(`Email not found for Customer: ${frm.doc.customer}`);
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
