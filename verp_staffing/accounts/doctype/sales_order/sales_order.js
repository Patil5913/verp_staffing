// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Order", {
	async refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Receivables",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();
		verp_staffing.purchase.items.update_items_currency_labels(frm);
		verp_staffing.purchase.exchange.update_description(frm);

		const config = await load_erp_config(frm);
		const requirements = get_requirements_from_config(frm, config);

		if (requirements.candidate_required) {
			frm.add_custom_button(
				__("Send Details Form"),
				() => send_details_form(frm),
				__("Send"),
			);
		}
		// Apply field visibility on every grid render for existing rows
		const grid = frm.fields_dict["payment_terms"].grid;
		const original_refresh = grid.refresh.bind(grid);
		grid.refresh = function () {
			original_refresh();
			// Apply toggle to all rendered rows after grid refreshes
			setTimeout(() => {
				(frm.doc.payment_terms || []).forEach((term) => {
					if (term.name) {
						toggle_payment_term_fields(frm, "Customer Payment Terms", term.name);
					}
				});
			}, 0);
		};
		// Trigger once immediately for already-rendered rows
		setTimeout(() => {
			(frm.doc.payment_terms || []).forEach((term) => {
				if (term.name) {
					toggle_payment_term_fields(frm, "Customer Payment Terms", term.name);
				}
			});
		}, 0);
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
		if (!frm.is_new() && frm.doc.docstatus === 1) {
			frappe.call({
				method: "verp_staffing.accounts.doctype.sales_order.sales_order.get_sales_invoice_for_order",
				args: { sales_order: frm.doc.name },
				callback: async (r) => {
					if (!r.message) {
						//Si not exists
						frm.add_custom_button(
							__("Sales Invoice"),
							() => {
								frappe.confirm(
									"Create a Sales Invoice for all items in this Sales Order?",
									async () => {
										const r = await frappe.call({
											method: "verp_staffing.accounts.doctype.sales_order.sales_order.create_sales_invoice_from_sales_order",
											args: { sales_order: frm.doc.name },
										});
										if (r.message) {
											frappe.msgprint({
												title: __("Invoice Created"),
												message: `Sales Invoice <b>${r.message}</b> created.<br><br>
                                        <a href="/app/sales-invoice/${r.message}" target="_blank">
                                            Open Invoice →
                                        </a>`,
												indicator: "green",
											});
											// remove button after successfull invoice creation
											frm.remove_custom_button(
												__("Sales Invoice"),
												__("Create"),
											);
											await render_invoices_tab(frm);
											await render_payment_term_actions(frm, r.message);
										}
									},
								);
							},
							__("Create"),
						);
					}
					await render_payment_term_actions(frm, r.message);
				},
			});
			toggle_payment_terms_add_button(frm);
		}
	},
	// before_submit(frm) {
	// 	frappe.dom.freeze(__("Processing submission..."));
	// },

	// on_submit(frm) {
	// 	frappe.dom.unfreeze();
	// 	frm.reload_doc();
	// },
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
		validate_payment_terms_total(frm);
		const config = await load_erp_config(frm);
	},

	before_save(frm) {
		if (frm.doc.__islocal) {
			frm._is_first_save = frm.doc.__islocal;
			frm._temp_name = frm.doc.name;
		}
	},

	async after_save(frm) {
		// frappe.dom.unfreeze();

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

		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Item",
				filter: { name: row.item },
				fieldname: ["stock_uom"],
			},
			callback: function (r) {
				if (r.message) {
					frappe.model.set_value(
						cdt,
						cdn,
						"uom",
						r.message.stock_uom ?? r.message.stock_uom,
					);
				}
			},
		});
		row.qty = 1;
		if (row.rate) row.amount = row.qty * row.rate;
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

frappe.ui.form.on("Customer Payment Terms", {
	validate(frm) {
		validate_payment_terms_total(frm);
	},
	// ── Condition changed ──────────────────────────────────────────
	payment_condition(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const prev = row._prev_payment_condition;
		toggle_payment_term_fields(frm, cdt, cdn);

		// Always update prev tracker
		row._prev_payment_condition = row.payment_condition;

		// No actual change (reload cycle) — only update description
		if (prev === row.payment_condition) {
			update_payment_term_description(frm, cdt, cdn);
			return;
		}

		if (row.payment_condition === "Not Applied") {
			frappe.model.set_value(cdt, cdn, "start_date", null);
			frappe.model.set_value(cdt, cdn, "due_date", null);
			frappe.model.set_value(cdt, cdn, "counter", 0);
			frappe.model.set_value(cdt, cdn, "current_interview_count", 0);
		} else if (row.payment_condition === "Number of Days") {
			frappe.model.set_value(cdt, cdn, "current_interview_count", 0);
			// Only clear due_date if genuinely switching from another condition
			frappe.model.set_value(cdt, cdn, "due_date", null);
		} else {
			// Number of Interviews
			// Only clear days-related fields if switching from Number of Days
			frappe.model.set_value(cdt, cdn, "start_date", null);
			frappe.model.set_value(cdt, cdn, "due_date", null);
			fetch_and_set_interview_count(frm, cdt, cdn);
		}
		update_payment_term_description(frm, cdt, cdn);
	},
	payment_terms_add(frm, cdt, cdn) {
		const so_total = frm.doc.disable_rounded_total
			? flt(frm.doc.grand_total)
			: flt(frm.doc.rounded_total || frm.doc.grand_total);

		const used = (frm.doc.payment_terms || [])
			.filter((row) => row.name !== cdn) // exclude the newly added row
			.reduce((sum, row) => sum + flt(row.amount || 0), 0);

		const remaining = Math.max(0, so_total - used);

		frappe.model.set_value(cdt, cdn, "amount", remaining);
	},
	payment_terms_remove(frm) {
		const so_total = frm.doc.disable_rounded_total
			? flt(frm.doc.grand_total)
			: flt(frm.doc.rounded_total || frm.doc.grand_total);
		toggle_payment_terms_add_button(frm, so_total);
	},

	// ── Start date changed (Number of Days only) ───────────────────
	start_date(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const today = frappe.datetime.get_today();
		if (row.start_date && row.start_date < today) {
			frappe.model.set_value(cdt, cdn, "start_date", today);
			frappe.msgprint({
				title: __("Invalid Date"),
				message: "Start date cannot be before today.",
				indicator: "red",
			});
			return;
		}

		compute_due_date(frm, cdt, cdn);

		update_payment_term_description(frm, cdt, cdn);
	},
	// ── Counter changed ────────────────────────────────────────────
	counter(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.payment_condition === "Number of Days") {
			compute_due_date(frm, cdt, cdn);
			const grid_row = frm.fields_dict["payment_terms"].grid.get_row(cdn);
			if (grid_row) grid_row.refresh_field("due_date");
		}
		update_payment_term_description(frm, cdt, cdn);
	},

	// ── Amount changed ─────────────────────────────────────────────
	amount(frm, cdt, cdn) {
		update_payment_term_description(frm, cdt, cdn);
		validate_payment_terms_total(frm);
	},

	// ── Row form opened — refresh interview count if applicable ────
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		toggle_payment_term_fields(frm, cdt, cdn);
		if (row.payment_condition === "Number of Interviews") {
			fetch_and_set_interview_count(frm, cdt, cdn);
		}
	},
	onload(frm, cdt, cdn) {
		toggle_payment_term_fields(frm, cdt, cdn);
	},
});

// ── Compute due_date = start_date + counter days ───────────────────────
function compute_due_date(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (row.__syncing) return;

	if (!row.start_date || !row.counter) {
		return;
	}
	const due = frappe.datetime.add_days(row.start_date, row.counter);

	if (row.due_date === due) return;
	// Write directly to locals — no event chain triggered
	locals[cdt][cdn].due_date = due;

	// Refresh only the due_date field in the matching grid row
	const grid = frm.fields_dict["payment_terms"].grid;
	const grid_row = grid.grid_rows.find((r) => r.doc.name === cdn);
	if (grid_row) {
		grid_row.refresh_field("due_date");
	}
}

// ── Fetch live interview count from Python and set on row ─────────────
async function fetch_and_set_interview_count(frm, cdt, cdn) {
	if (!frm.doc.customer) return;

	const r = await frappe.call({
		method: "verp_staffing.accounts.doctype.sales_order.sales_order.get_interview_count_for_customer",
		args: { customer: frm.doc.customer },
	});

	const count = r.message || 0;
	frappe.model.set_value(cdt, cdn, "current_interview_count", count);

	// Re-render description now that count is known
	update_payment_term_description(frm, cdt, cdn);
}

// ── Auto-generate human-readable description ───────────────────────────
function update_payment_term_description(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.payment_condition) return;

	const amount = row.amount ? format_currency(row.amount, frm.doc.currency, 4) : "—";

	let desc = "";

	if (row.payment_condition === "Not Applied") {
		desc = `Pay ${amount} — No condition applied (immediate or pre-paid)`;
	} else if (row.payment_condition === "Number of Days") {
		const days = row.counter || "?";
		const start = row.start_date ? frappe.datetime.str_to_user(row.start_date) : "?";
		const due = row.due_date ? frappe.datetime.str_to_user(row.due_date) : "not computed";

		desc = `Pay ${amount} after ${days} day(s) from ${start} — Due: ${due}`;
	} else {
		const required = row.counter || "?";
		const current = row.current_interview_count != null ? row.current_interview_count : "…";
		const remaining =
			row.counter != null && row.current_interview_count != null
				? Math.max(0, row.counter - row.current_interview_count)
				: "?";

		desc = `Pay ${amount} after ${required} interview(s) — Current: ${current}, Remaining: ${remaining}`;
	}

	frappe.model.set_value(cdt, cdn, "description", desc);
}

async function render_payment_term_actions(frm, si_name) {
	const grid = frm.fields_dict["payment_terms"].grid;

	grid.wrapper.off("click.fix_modal", ".grid-row-open .btn-open-row, .grid-row .btn-open-row");
	$(document).off("hidden.bs.modal.pt_fix");
	$(document).on("hidden.bs.modal.pt_fix", ".modal", function () {
		// Clean up stuck modal state
		setTimeout(() => {
			if (!$(".modal.show").length && !$(".modal:visible").length) {
				$("body").removeClass("modal-open");
				$(".modal-backdrop").remove();
				$("body").css("padding-right", "");
			}
		}, 100);
	});
	grid.grid_rows.forEach((grid_row) => {
		const row = grid_row.doc;

		// Clean up previously added elements
		grid_row.wrapper.find(".btn-payment-action, .payment-lock-msg").remove();

		if (row.payment_status === "Verified") return;

		if (row.payment_status === "Pending Verification") {
			const $info = $(`
                <span class="text-muted small payment-lock-msg" 
                      style="padding: 4px 8px; display: inline-block;">
                    Awaiting verification
                    ${
						row.payment_entry
							? `— <a href="/app/payment-entry/${row.payment_entry}" target="_blank">
                               ${row.payment_entry}
                           </a>`
							: ""
					}
                </span>
            `);

			$info.find(".pe-link").on("click", (e) => e.stopPropagation());
			grid_row.wrapper.find(".data-row").append($info);
			return;
		}

		if (!si_name) {
			const $lock = $(`
                <span class="text-muted small payment-lock-msg" 
                      style="padding: 4px 8px; display: inline-block;">
                    Create Invoice first
                </span>
            `);
			grid_row.wrapper.find(".data-row").append($lock);
			return;
		}

		const is_rerequest = row.payment_status === "Rejected";
		const btn_label = is_rerequest ? "Re-request" : "Mark as Paid";
		const btn_class = is_rerequest ? "btn-warning" : "btn-primary";

		const $btn = $(`
            <button class="btn btn-xs ${btn_class} btn-payment-action" 
                    style="margin: 2px 8px;">
                ${btn_label}
            </button>
        `);

		$btn.on("click", (e) => {
			e.stopPropagation();
			open_mark_as_paid_dialog(frm, row, si_name, is_rerequest);
		});

		grid_row.wrapper.find(".data-row").append($btn);
	});
}

function open_mark_as_paid_dialog(frm, term_row, si_name, is_rerequest = false) {
	const amount = format_currency(term_row.amount, frm.doc.currency, 2);

	const dialog = new frappe.ui.Dialog({
		title: is_rerequest ? __("Re-request Verification") : __("Mark as Paid"),
		fields: [
			{
				fieldtype: "HTML",
				options: `
                    <div class="alert alert-info" style="margin-bottom:12px">
                        <b>Amount:</b> ${amount}<br>
                        <b>Invoice:</b> ${si_name}<br>
                        <b>Condition:</b> ${term_row.description || term_row.payment_condition}
                        ${
							is_rerequest && term_row.payment_entry
								? `<br><b>Payment Entry:</b> 
                               <a href="/app/payment-entry/${term_row.payment_entry}" target="_blank">
                                   ${term_row.payment_entry}
                               </a>`
								: ""
						}
                    </div>
                `,
			},
			{
				fieldtype: "Data",
				fieldname: "reference_no",
				label: __("Reference / Cheque No"),
				reqd: 1,
			},
			{
				fieldtype: "Date",
				fieldname: "reference_date",
				label: __("Reference Date"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
		],
		primary_action_label: is_rerequest ? __("Re-request") : __("Submit for Verification"),
		primary_action: async (values) => {
			dialog.disable_primary_action();
			try {
				const r = await frappe.call({
					method: "verp_staffing.accounts.doctype.sales_order.sales_order.create_payment_entry_from_term",
					args: {
						sales_order: frm.doc.name,
						payment_term_row: term_row.name,
						reference_no: values.reference_no,
						reference_date: values.reference_date,
					},
				});
				if (r.message) {
					dialog.hide();
					frappe.msgprint({
						title: is_rerequest ? __("Re-requested") : __("Submitted"),
						message: `Payment Entry <b>${r.message}</b> 
                                    ${is_rerequest ? "re-submitted" : "submitted"} for verification.<br><br>
                                    <a href="/app/payment-entry/${r.message}" target="_blank">
                                        Open Payment Entry →
                                    </a>`,
						indicator: "blue",
					});
					await frm.reload_doc();
				}
			} catch (e) {
				dialog.enable_primary_action();
			}
		},
	});

	dialog.show();
}

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
		method: "verp_staffing.crm.doctype.customer.customer.get_customer_email",
		args: { customer: frm.doc.customer },
	});
	recipient = recipient.message;

	if (!recipient) {
		const res = await frappe.db.get_value("Customer", frm.doc.customer, "lead_details");
		console.log("res: ", res);
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
			frm.validated = false;
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
		return { label: "Partially Paid", color: "blue" };
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
		method: "verp_staffing.accounts.doctype.sales_order.sales_order.get_linked_invoice",
		args: { sales_order: frm.doc.name },
	});

	const invoices = r.message || [];
	const invoice = invoices.length ? invoices[0] : null;
	const wrapper = frm.get_field("invoices_html").$wrapper;
	if (!invoice) {
		wrapper.html(
			`<p class="text-muted" style="padding:10px">
                No invoice created yet.
            </p>`,
		);
		return;
	}

	const { label, color } = get_invoice_indicator(invoice);

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
						<tbody>
							<tr>
						<td>
							<a href="/app/sales-invoice/${invoice.name}" target="_blank">
								${invoice.name}
							</a>
						</td>
						<td>${frappe.datetime.str_to_user(invoice.posting_date)}</td>
						<td>${format_currency(invoice.grand_total, invoice.currency)}</td>
						<td>${format_currency(invoice.outstanding_amount, invoice.currency)}</td>
						<td>
							<span class="indicator-pill ${color}">
								${__(label)}
							</span>
						</td>
            		</tr>
				</tbody>
            </table>
        </div>
    `);
}

// ── Validates total payment terms don't exceed SO grand total ──────────
function validate_payment_terms_total(frm) {
	const terms = frm.doc.payment_terms || [];
	const terms_total = terms.reduce((sum, row) => sum + flt(row.amount || 0), 0);

	const so_total = flt(
		frm.doc.disable_rounded_total
			? frm.doc.grand_total
			: frm.doc.rounded_total || frm.doc.grand_total,
	);

	if (!so_total) return; // SO total not computed yet — skip
	if (flt(terms_total, 2) > flt(so_total, 2)) {
		const excess = flt(terms_total - so_total, 2);

		// Auto-correct the last editable row
		for (let i = terms.length - 1; i >= 0; i--) {
			const row = terms[i];
			if (!in_list(["Pending Verification", "Verified"], row.payment_status)) {
				const corrected = Math.max(0, flt(row.amount) - excess);
				frappe.model.set_value(row.doctype, row.name, "amount", corrected);
				break;
			}
		}

		frappe.throw(
			`Total payment terms (${format_currency(terms_total, frm.doc.currency, 2)}) ` +
				`exceeds Sales Order total (${format_currency(so_total, frm.doc.currency, 2)}) ` +
				`by ${excess}.`,
		);
	}
	toggle_payment_terms_add_button(frm, so_total);
}

function toggle_payment_terms_add_button(frm, so_total) {
	// Restrict user from futher terms after terms total and so total becomes equal
	if (!so_total) {
		//calculate total if not provided
		so_total = flt(
			frm.doc.disable_rounded_total
				? frm.doc.grand_total
				: frm.doc.rounded_total || frm.doc.grand_total,
		);
	}

	const terms_total = (frm.doc.payment_terms || []).reduce(
		(sum, row) => sum + flt(row.amount || 0),
		0,
	);

	const grid = frm.fields_dict["payment_terms"].grid;

	if (so_total && flt(terms_total, 2) >= flt(so_total, 2)) {
		//hide add button
		grid.wrapper.find(".grid-add-row, .grid-add-multiple-rows").hide();
	} else {
		grid.wrapper.find(".grid-add-row, .grid-add-multiple-rows").show();
	}
}

function toggle_payment_term_fields(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const condition = row.payment_condition;

	const read_only_map = {
		"Not Applied": { counter: 1, start_date: 1, due_date: 1, current_interview_count: 1 },
		"Number of Days": { counter: 0, start_date: 0, due_date: 1, current_interview_count: 1 },
		"Number of Interviews": {
			counter: 0,
			start_date: 1,
			due_date: 1,
			current_interview_count: 1,
		},
	};

	const config = read_only_map[condition] || read_only_map["Not Applied"];
	const grid = frm.fields_dict["payment_terms"].grid;
	const grid_row = grid.grid_rows.find((r) => r.doc.name === cdn);
	if (!grid_row) return;

	Object.entries(config).forEach(([fieldname, read_only]) => {
		grid_row.set_field_property(fieldname, "read_only", read_only);
	});
}
