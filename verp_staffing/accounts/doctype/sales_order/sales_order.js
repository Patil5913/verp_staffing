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
		verp_staffing.purchase.items.update_items_currency_labels(frm);
		verp_staffing.purchase.exchange.update_description(frm);

		// Set query filter on items child table's item field
		frm.fields_dict["items"].grid.get_field("item").get_query = function () {
			return {
				filters: {
					is_service: 1,
					disabled: 0,
				},
			};
		};
		(frm.doc.taxes || []).forEach((row) =>
			verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, row.doctype, row.name),
		);
		await update_agreement_module(frm);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
		await render_invoices_tab(frm);

		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Sales Invoice"),
				() => {
					open_create_invoice_dialog(frm);
				},
				__("Create"),
			);
		}
	},
	onload(frm) {
		set_account_queries(frm);
		if (!frm.doc.company) {
			frappe.call({
				method: "verp_staffing.accounts.doctype.company.company.fetch_default_company",
				callback(r) {
					if (r.message) {
						frm.set_value("company", r.message);
					}
				},
			});
		}
	},
	async validate(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
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
	company: function (frm) {
		verp_staffing.purchase.exchange.update_description(frm);
		handle_currency(frm);

		handle_discount_account(frm);
		if (!frm.doc.company) return;
		set_account_queries(frm);

		if (frm.doc.items && frm.doc.items.length) {
			frappe.db
				.get_value("Company", frm.doc.company, "default_expense_account")
				.then((r) => {
					if (!r.message.default_expense_account) {
						frappe.throw("Default Company Expense Account not set");
					}
					if (r.message && r.message.default_expense_account) {
						frm.doc.items.forEach((item) => {
							item.expense_account = r.message.default_expense_account;
						});
						frm.refresh_field("items");
					}
				});
		}
	},
	currency: function (frm) {
		verp_staffing.purchase.items.update_items_currency_labels(frm);
		verp_staffing.purchase.exchange.update_description(frm);
		handle_currency(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
	},
	conversion_rate: function (frm) {
		verp_staffing.purchase.exchange.update_description(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
	},
	additional_discount_percentage(frm) {
		let discount_amount = 0;
		discount_amount =
			(flt(frm.doc.total) * flt(frm.doc.additional_discount_percentage || 0)) / 100;

		frm.set_value("discount_amount", discount_amount);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	discount_amount(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
		handle_discount_account(frm);
	},
	disable_rounded_total(frm) {
		verp_staffing.calculation_engine.calculate_rounding(frm);
	},
});

// Child table handler — re-apply filter when a new row is added
frappe.ui.form.on("Items Table", {
	item(frm, cdt, cdn) {
		if (frm.doc.doctype !== "Sales Order") return;

		const row = locals[cdt][cdn];

		if (!row.item) return;

		row.type = "Sales";

		frappe.db.get_value("Item", row.item, "stock_uom").then((r) => {
			if (r.message && r.message.stock_uom) {
				row.uom = r.message.stock_uom;
			}
			row.qty = 1;

			frm.refresh_field("items");
		});

		if (frm.doc.company) {
			frappe.db.get_value("Company", frm.doc.company, "default_income_account").then((r) => {
				if (r.message?.default_income_account) {
					row.income_account = r.message.default_income_account;

					frm.refresh_field("items");
				}
			});
		}
		verp_staffing.calculation_engine.calculate_invoice(frm);
		update_agreement_module(frm);
	},
	items_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "type", "Sales");
		verp_staffing.calculation_engine.calculate_invoice(frm);
		frm.fields_dict["items"].grid.get_field("item").get_query = function () {
			return {
				filters: {
					is_service: 1,
					disabled: 0,
				},
			};
		};
		update_agreement_module(frm);
	},
	items_remove: function (frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
		update_agreement_module(frm);
	},

	qty: function (frm, cdt, cdn) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},

	rate: function (frm, cdt, cdn) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
});

frappe.ui.form.on("Taxes and Charges", {
	refresh(frm) {
		(frm.doc.taxes || []).forEach((row) =>
			verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, row.doctype, row.name),
		);
	},
	charge_type(frm, cdt, cdn) {
		verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, cdt, cdn);
	},
	rate(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	tax_amount(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	taxes_add(frm, cdt, cdn) {
		verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, cdt, cdn);
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	taxes_remove(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
	},
	row_id(frm) {
		verp_staffing.calculation_engine.calculate_invoice(frm);
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
		auto_mode:
			config.sendAgreementImmediately && requirements.agreement_required && frm.is_new(),
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

	// Normalize structure (this is critical, don't skip)
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

		// full service-wise config
		serviceConfig: serviceConfig,
	};

	return frm._erp_config;
}

function get_requirements_from_config(frm, config) {
	// Read item names directly from the items child table
	// These are already guaranteed is_service=1 via the get_query filter
	const items = (frm.doc.items || []).map((row) => row.item).filter(Boolean);

	let agreement_required = false;
	let candidate_required = false;

	items.forEach((item) => {
		const cfg = config.serviceConfig[(item || "").trim()];

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

function handle_currency(frm) {
	set_currency_labels(frm);
	if (frm.doc.currency === frm.doc.company_currency) {
		// Same currency
		frm.set_value("conversion_rate", 1);
		frm.set_df_property("conversion_rate", "hidden", 1);
		frm.set_df_property("conversion_rate", "reqd", 0);

		toggle_base_fields(frm, false);
	} else {
		// Different currency
		frm.set_df_property("conversion_rate", "hidden", 0);
		frm.set_df_property("conversion_rate", "reqd", 1);

		toggle_base_fields(frm, true);
	}
}

function set_account_queries(frm) {
	frm.set_query("income_account", "items", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__",
				},
			};
		}

		return {
			filters: {
				account_type: ["in", ["Income", "Income Account"]],
				report_type: "Profit and Loss",
				is_group: 0,
				company: frm.doc.company,
			},
		};
	});

	frm.set_query("account_head", "taxes", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__",
				},
			};
		}

		return {
			filters: {
				account_type: ["in", ["Tax", "Chargeable", "Expense", "Income Account"]],
				is_group: 0,
				company: frm.doc.company,
			},
		};
	});

	frm.set_query("additional_discount_account", () => {
		if (!frm.doc.company) {
			return {
				filters: {
					name: "__invalid__",
				},
			};
		}

		return {
			filters: {
				company: frm.doc.company,
				is_group: 0,
				report_type: "Profit and Loss",
			},
		};
	});
}

function handle_discount_account(frm) {
	if (!frm.doc.company) return;

	if (flt(frm.doc.discount_amount) > 0 && !frm.doc.additional_discount_account) {
		frappe.db.get_value("Company", frm.doc.company, "default_discount_account").then((r) => {
			if (r.message && r.message.default_discount_account) {
				frm.set_value("additional_discount_account", r.message.default_discount_account);
			}
		});
	}
}

function set_currency_labels(frm) {
	const currency = frm.doc.currency || "";
	const company_currency = frm.doc.company_currency || "";

	const fields = [
		"total",
		"net_total",
		"grand_total",
		"rounded_total",
		"discount_amount",
		"rounding_adjustment",
		"total_taxes_and_charges",
	];
	fields.forEach((field) => {
		frm.set_df_property(
			field,
			"label",
			`${frm.fields_dict[field].df.label.split(" (")[0]} (${currency})`,
		);
	});
	const company_currency_field = [
		"base_total",
		"base_net_total",
		"base_grand_total",
		"base_rounded_total",
		"base_rounding_adjustment",
		"base_total_taxes_and_charges",
		"base_in_words",
		"base_discount_amount",
	];
	company_currency_field.forEach((field) => {
		if (currency && company_currency && currency !== company_currency) {
			frm.set_df_property(field, "hidden", false);
		} else {
			frm.set_df_property(field, "hidden", true);
		}

		frm.set_df_property(
			field,
			"label",
			`${frm.fields_dict[field].df.label.split(" (")[0]} (${company_currency})`,
		);
	});
}

function toggle_base_fields(frm, show) {
	const fields = [
		"base_total",
		"base_net_total",
		"base_grand_total",
		"base_rounded_total",
		"base_discount_amount",
	];

	fields.forEach((f) => {
		frm.set_df_property(f, "hidden", show ? 0 : 1);
		if (show) {
			frm.set_value(f, 0);
		}
	});
}

function get_invoice_indicator(inv) {
	const today = frappe.datetime.get_today();
	if (inv.outstanding_amount < 0) return { label: "Credit Note Issued", color: "grey" };
	if (inv.outstanding_amount == 0) return { label: "Paid", color: "green" };
	if (inv.outstanding_amount > 0 && inv.due_date && inv.due_date < today)
		return { label: "Overdue", color: "red" };
	if (inv.outstanding_amount > 0 && inv.outstanding_amount < inv.grand_total)
		return { label: "Partly Paid", color: "blue" };
	return { label: "Unpaid", color: "orange" };
}

async function render_invoices_tab(frm) {
	if (frm.is_new()) {
		frm.get_field("invoices_html").$wrapper.html(
			`<p class="text-muted" style="padding:10px">
                Save the Sales Order first to see linked invoices.
            </p>`,
		);
		return;
	}

	const r = await frappe.call({
		method: "verp_staffing.accounts.doctype.sales_order.sales_order.get_linked_invoices",
		args: { sales_order: frm.doc.name },
	});

	const invoices = r.message || [];
	const wrapper = frm.get_field("invoices_html").$wrapper;

	if (!invoices.length) {
		wrapper.html(
			`<p class="text-muted" style="padding:10px">
                No invoices created yet.
            </p>`,
		);
		return;
	}

	const rows = invoices
		.map((inv) => {
			const { label, color } = get_invoice_indicator(inv);
			return `
            <tr>
                <td>
                    <a href="/app/sales-invoice/${inv.name}" target="_blank">
                        ${inv.name}
                    </a>
                </td>
                <td>${frappe.datetime.str_to_user(inv.posting_date)}</td>
                <td>${format_currency(inv.grand_total, inv.currency)}</td>
                <td>${format_currency(inv.outstanding_amount, inv.currency)}</td>
                <td>
                    <span class="indicator-pill ${color}">
                        ${__(label)}
                    </span>
                </td>
            </tr>
        `;
		})
		.join("");

	wrapper.html(`
        <div style="padding: 10px">
            <table class="table table-bordered table-hover">
                <thead>
                    <tr>
                        <th>Invoice</th>
                        <th>Date</th>
                        <th>Grand Total</th>
                        <th>Outstanding</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `);
}

function format_currency(value, currency) {
	return frappe.format(value, { fieldtype: "Currency", options: currency });
}

function open_create_invoice_dialog(frm) {
	const items = frm.doc.items || [];

	if (!items.length) {
		frappe.msgprint("No items found on this Sales Order.");
		return;
	}

	// Build checklist rows — each item is pre-checked
	const item_rows = items
		.map(
			(row) => `
        <tr>
            <td style="width:40px;text-align:center">
                <input 
                    type="checkbox" 
                    class="so-item-check" 
                    data-rowname="${row.name}"
                    checked
                />
            </td>
            <td>${row.item}</td>
            <td style="text-align:right">${row.qty}</td>
            <td style="text-align:right">
                ${frappe.format(row.rate, { fieldtype: "Currency", options: frm.doc.currency })}
            </td>
            <td style="text-align:right">
                ${frappe.format(row.amount, { fieldtype: "Currency", options: frm.doc.currency })}
            </td>
        </tr>
    `,
		)
		.join("");

	const dialog = new frappe.ui.Dialog({
		title: __("Create Sales Invoice"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "items_html",
				options: `
                    <div style="margin-bottom:8px">
                        <a href="#" id="check-all" style="margin-right:12px">Check All</a>
                        <a href="#" id="uncheck-all">Uncheck All</a>
                    </div>
                    <table class="table table-bordered table-condensed">
                        <thead>
                            <tr>
                                <th></th>
                                <th>Item</th>
                                <th style="text-align:right">Qty</th>
                                <th style="text-align:right">Rate</th>
                                <th style="text-align:right">Amount</th>
                            </tr>
                        </thead>
                        <tbody>${item_rows}</tbody>
                    </table>
                `,
			},
		],
		primary_action_label: __("Create Invoice"),
		primary_action: async () => {
			const selected = [];
			dialog.$wrapper.find(".so-item-check:checked").each(function () {
				selected.push($(this).data("rowname"));
			});

			if (!selected.length) {
				frappe.msgprint("Please select at least one item.");
				return;
			}

			dialog.disable_primary_action();

			try {
				const r = await frappe.call({
					method: "verp_staffing.accounts.doctype.sales_order.sales_order.create_sales_invoice",
					args: {
						sales_order: frm.doc.name,
						selected_items: JSON.stringify(selected),
					},
				});

				if (r.message) {
					dialog.hide();
					frappe.msgprint({
						title: __("Invoice Created"),
						message: `Sales Invoice <b>${r.message}</b> created successfully.
                            <br><br>
                            <a href="/app/sales-invoice/${r.message}" target="_blank">
                                Open Invoice →
                            </a>`,
						indicator: "green",
					});
					await render_invoices_tab(frm);
				}
			} catch (e) {
				dialog.enable_primary_action();
			}
		},
	});

	dialog.show();

	// Wire up check all / uncheck all
	dialog.$wrapper.find("#check-all").on("click", (e) => {
		e.preventDefault();
		dialog.$wrapper.find(".so-item-check").prop("checked", true);
	});
	dialog.$wrapper.find("#uncheck-all").on("click", (e) => {
		e.preventDefault();
		dialog.$wrapper.find(".so-item-check").prop("checked", false);
	});
}
