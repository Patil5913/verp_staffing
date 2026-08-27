// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

let _isSalesUser = null;

frappe.ui.form.on("Sales Order", {
	setup(frm) {
		frm.set_query("item", "items", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];

			const selected_items = (doc.items || [])
				.filter((d) => d.item && d.name !== row.name)
				.map((d) => d.item);

			return {
				filters: [
					["is_service", "=", "1"],
					["disabled", "=", "0"],
					["Item", "name", "not in", selected_items],
				],
			};
		});
	},
	async refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Receivables",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();
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

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Sales Order";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

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
		sync_payment_term_so_currency(frm);
		(frm.doc.taxes || []).forEach((row) =>
			verp_staffing.purchase.tax.toggle_rate_amount_fields(frm, row.doctype, row.name),
		);
		await update_agreement_module(frm);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
		await render_invoices_tab(frm);
		if (!frm.is_new() && frm.doc.docstatus === 1) {
			await render_payment_term_actions(frm);
			toggle_payment_terms_add_button(frm);
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
			frappe
				.call("verp_staffing.accounts.api.get_defaults.get_default_company_account", {
					company: frm.doc.company,
					fieldname: "default_income_account",
				})
				.then((r) => {
					if (r.message) {
						frm.doc.items.forEach((item) => {
							item.income_account = r.message;
						});
						frm.refresh_field("items");
					}
				});
		}
	},
	currency: function (frm) {
		verp_staffing.purchase.exchange.update_description(frm);
		handle_currency(frm);
		verp_staffing.calculation_engine.calculate_invoice(frm);
		verp_staffing.calculation_engine.handle_rounded_total(frm);
		sync_payment_term_so_currency(frm);
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
			frappe
				.call("verp_staffing.accounts.api.get_defaults.get_default_company_account", {
					company: frm.doc.company,
					fieldname: "default_income_account",
				})
				.then((r) => {
					if (r.message) {
						row.income_account = r.message;

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
		frappe.model.set_value(cdt, cdn, "so_currency", frm.doc.currency);
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

async function is_sales_user() {
	if (_isSalesUser !== null) {
		return _isSalesUser;
	}

	const { message: departments = [] } = await frappe.call({
		method: "verp_staffing.crm.api.helpers.get_user_departments",
	});

	_isSalesUser = departments.includes("Sales");

	return _isSalesUser;
}

async function get_document_link(doctype_route, name) {
	if (!name) return "";

	const sales_user = await is_sales_user();

	if (sales_user) {
		return name;
	}

	return `
		<a href="/app/${doctype_route}/${name}" target="_blank">
			${name}
		</a>
	`;
}

// ── Keep so_currency in sync on every existing row (covers rows that
// existed before this field, and any change to the SO's own currency) ────
function sync_payment_term_so_currency(frm) {
	(frm.doc.payment_terms || []).forEach((row) => {
		if (row.so_currency !== frm.doc.currency) {
			frappe.model.set_value(row.doctype, row.name, "so_currency", frm.doc.currency);
		}
	});
}

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

// ── Auto-generate human-readable description (shows both currencies) ───
function update_payment_term_description(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.payment_condition) return;

	const amount = row.amount ? format_currency(row.amount, frm.doc.currency, 2) : "—";
	const converted =
		row.currency && row.currency !== frm.doc.currency && row.received_amount
			? ` (${format_currency(row.received_amount, row.currency, 2)})`
			: "";
	const amount_display = `${amount}${converted}`;

	let desc = "";

	if (row.payment_condition === "Not Applied") {
		desc = `Pay ${amount_display} — No condition applied (immediate or pre-paid)`;
	} else if (row.payment_condition === "Number of Days") {
		const days = row.counter || "?";
		const start = row.start_date ? frappe.datetime.str_to_user(row.start_date) : "?";
		const due = row.due_date ? frappe.datetime.str_to_user(row.due_date) : "not computed";

		desc = `Pay ${amount_display} after ${days} day(s) from ${start} — Due: ${due}`;
	} else {
		const required = row.counter || "?";
		const current = row.current_interview_count != null ? row.current_interview_count : "…";
		const remaining =
			row.counter != null && row.current_interview_count != null
				? Math.max(0, row.counter - row.current_interview_count)
				: "?";

		desc = `Pay ${amount_display} after ${required} interview(s) — Current: ${current}, Remaining: ${remaining}`;
	}

	frappe.model.set_value(cdt, cdn, "description", desc);
}

// ── Render per-row action button + invoice/company info ────────────────
async function render_payment_term_actions(frm) {
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

	grid.grid_rows.forEach(async (grid_row) => {
		const row = grid_row.doc;

		// Clean up previously added elements
		grid_row.wrapper
			.find(".btn-payment-action, .payment-lock-msg, .payment-invoice-info")
			.remove();

		// Always show "PaymentEntryId - Company" once a PE exists on this row
		if (row.payment_entry) {
			const $peInfo = $(`
				<div class="text-muted small payment-invoice-info" style="padding: 2px 8px;">
					${row.payment_entry} - ${row.company || "—"}
				</div>
			`);
			grid_row.wrapper.find(".data-row").append($peInfo);
		}

		if (row.payment_status === "Verified") return;

		if (row.payment_status === "Pending Verification") {
			const paymentEntryLink = row.payment_entry
				? `— ${await get_document_link("payment-entry", row.payment_entry)}`
				: "";

			const $info = $(`
                <span class="text-muted small payment-lock-msg" 
                      style="padding: 4px 8px; display: inline-block;">
                    Awaiting verification
                    ${paymentEntryLink}
                </span>
            `);

			$info.find(".pe-link").on("click", (e) => e.stopPropagation());
			grid_row.wrapper.find(".data-row").append($info);
			return;
		}

		// One unified action for every row — invoice/company/currency are
		// resolved automatically on the backend the first time, reused after
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
			open_mark_as_paid_dialog(frm, row, is_rerequest);
		});

		grid_row.wrapper.find(".data-row").append($btn);
	});
}

function open_mark_as_paid_dialog(frm, term_row, is_rerequest = false) {
	const needs_company = !term_row.sales_invoice;
	const so_currency = frm.doc.currency;

	let dialog;

	// Fetch the selected company's currency, toggle the exchange-rate field,
	// and refresh the received-amount preview accordingly.
	const refresh_preview = async () => {
		if (!needs_company) return;

		const company = dialog.get_value("company");
		const $preview = dialog.fields_dict.received_preview.$wrapper;

		if (!company) {
			dialog.set_df_property("conversion_rate", "hidden", 1);
			$preview.html("");
			return;
		}

		const r = await frappe.db.get_value("Company", company, "default_currency");
		const target_currency = (r.message && r.message.default_currency) || so_currency;
		const same_currency = target_currency === so_currency;

		dialog.set_df_property("conversion_rate", "hidden", same_currency ? 1 : 0);
		dialog.set_df_property("conversion_rate", "reqd", same_currency ? 0 : 1);

		if (same_currency) {
			dialog.set_value("conversion_rate", 1);
		}

		const rate = flt(dialog.get_value("conversion_rate")) || 0;
		const received = same_currency ? flt(term_row.amount) : flt(term_row.amount) * rate;

		$preview.html(`
			<div class="text-muted small" style="padding: 4px 0 8px;">
				Received Amount: <b>${format_currency(received, target_currency, 2)}</b>
			</div>
		`);
	};

	const dialog_fields = [
		{
			fieldtype: "HTML",
			fieldname: "summary_html",
			options: `
				<div class="alert alert-info" style="margin-bottom:12px">
					<b>Amount:</b> ${format_currency(term_row.received_amount ?? term_row.amount, term_row.currency || so_currency, 2)}<br>
					${
						term_row.sales_invoice
							? `<b>Invoice:</b> ${term_row.sales_invoice} (${term_row.currency || so_currency})`
							: `<b>Invoice:</b> will be created for the company selected below`
					}
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
	];

	if (needs_company) {
		dialog_fields.push(
			{
				fieldtype: "Link",
				options: "Company",
				fieldname: "company",
				label: __("Company"),
				default: frm.doc.company,
				reqd: 1,
				onchange: () => refresh_preview(),
			},
			{
				fieldtype: "Float",
				fieldname: "conversion_rate",
				label: __("Exchange Rate") + ` (1 ${so_currency} = ?)`,
				hidden: 1,
				onchange: () => refresh_preview(),
			},
			{
				fieldtype: "HTML",
				fieldname: "received_preview",
				options: "",
			},
		);
	}

	dialog_fields.push(
		{
			fieldtype: "Data",
			fieldname: "payer_account_name",
			label: __("Payer's Account Name"),
			reqd: 1,
		},
		{
			fieldtype: "Data",
			fieldname: "reference_no",
			label: __("Reference Id/ Transaction No/ Cheque No"),
			reqd: 1,
		},
		{
			fieldtype: "Data",
			fieldname: "remarks",
			label: __("Add Remarks (Amount paid in which account)"),
			reqd: 1,
		},
		{
			fieldtype: "Date",
			fieldname: "reference_date",
			label: __("Reference Date"),
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
	);

	dialog = new frappe.ui.Dialog({
		title: is_rerequest ? __("Re-request Verification") : __("Mark as Paid"),
		fields: dialog_fields,
		primary_action_label: is_rerequest ? __("Re-request") : __("Submit for Verification"),
		primary_action: async (values) => {
			if (needs_company) {
				const company = dialog.get_value("company");
				const conversion_rate = dialog.get_value("conversion_rate");
				if (!company) {
					frappe.msgprint(__("Company is required."));
					return;
				}
				if (!dialog.get_field("conversion_rate").df.hidden && flt(conversion_rate) <= 0) {
					frappe.msgprint(__("Enter a valid exchange rate."));
					return;
				}
			}

			dialog.disable_primary_action();
			try {
				const r = await frappe.call({
					method: "verp_staffing.accounts.doctype.sales_order.sales_order.create_payment_entry_from_term",
					args: {
						sales_order: frm.doc.name,
						payment_term_row: term_row.name,
						reference_no: values.reference_no,
						reference_date: values.reference_date,
						remarks: values.remarks,
						payer_account_name: values.payer_account_name,
						company: values.company || undefined,
						conversion_rate: values.conversion_rate || undefined,
					},
				});
				if (r.message) {
					dialog.hide();

					if (needs_company) {
						frappe.model.set_value(
							term_row.doctype,
							term_row.name,
							"company",
							r.message.company,
						);
						frappe.model.set_value(
							term_row.doctype,
							term_row.name,
							"currency",
							r.message.currency,
						);
						frappe.model.set_value(
							term_row.doctype,
							term_row.name,
							"conversion_rate",
							r.message.conversion_rate,
						);
						frappe.model.set_value(
							term_row.doctype,
							term_row.name,
							"received_amount",
							r.message.received_amount,
						);
					}

					frappe.msgprint({
						title: is_rerequest ? __("Re-requested") : __("Submitted"),
						message: `Payment Entry <b>${r.message.payment_entry}</b> 
                                    ${is_rerequest ? "re-submitted" : "submitted"} for verification.<br>
                                    Invoice: <b>${r.message.invoice}</b><br><br>
                                    <a href="/app/payment-entry/${r.message.payment_entry}" target="_blank">
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

	if (needs_company) {
		dialog.set_value("company", frm.doc.company);
		refresh_preview();
	}

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

// ── Invoices tab — multiple invoices per SO, infinite scroll (5 per page) ──
async function render_invoices_tab(frm) {
	const wrapper = frm.get_field("invoices_html").$wrapper;

	if (frm.is_new()) {
		wrapper.html(
			`<p class="text-muted" style="padding:10px">
                Save the Sales Order first to see linked invoices.
            </p>`,
		);
		return;
	}

	frm._invoice_offset = 0;
	frm._invoice_has_more = true;
	frm._invoice_loading = false;

	wrapper.html(`
		<div class="invoices-scroll-wrapper" style="max-height: 320px; overflow-y: auto; padding: 10px;">
			<table class="table table-bordered table-hover" style="margin-bottom: 0;">
				<thead>
					<tr>
						<th>Invoice</th>
						<th>Company</th>
						<th>Date</th>
						<th>Created By</th>
						<th>Grand Total</th>
						<th>Outstanding</th>
						<th>Status</th>
					</tr>
				</thead>
				<tbody class="invoices-tbody"></tbody>
			</table>
			<p class="text-muted small invoices-empty-msg" style="padding: 10px; display:none;">
				No invoices created yet.
			</p>
			<p class="text-muted small text-center invoices-loading-msg" style="padding: 6px; display:none;">
				Loading...
			</p>
		</div>
	`);

	const $scrollWrapper = wrapper.find(".invoices-scroll-wrapper");
	$scrollWrapper.off("scroll.invoice_paging").on("scroll.invoice_paging", () => {
		const el = $scrollWrapper[0];
		if (
			frm._invoice_has_more &&
			!frm._invoice_loading &&
			el.scrollTop + el.clientHeight >= el.scrollHeight - 40
		) {
			load_invoice_page(frm);
		}
	});

	await load_invoice_page(frm);
}

async function load_invoice_page(frm) {
	if (frm._invoice_loading || !frm._invoice_has_more) return;
	frm._invoice_loading = true;

	const wrapper = frm.get_field("invoices_html").$wrapper;
	wrapper.find(".invoices-loading-msg").show();
	const is_first_page = frm._invoice_offset === 0;

	try {
		const r = await frappe.call({
			method: "verp_staffing.accounts.doctype.sales_order.sales_order.get_linked_invoices",
			args: {
				sales_order: frm.doc.name,
				limit_start: frm._invoice_offset,
				limit_page_length: 5,
			},
		});

		const { invoices = [], has_more = false } = r.message || {};
		frm._invoice_has_more = has_more;
		frm._invoice_offset += invoices.length;

		if (is_first_page && invoices.length === 0) {
			wrapper.find(".invoices-empty-msg").show();
			return;
		}

		const $tbody = wrapper.find(".invoices-tbody");

		for (const inv of invoices) {
			const invoiceLink = await get_document_link("sales-invoice", inv.name);
			const draftBadge =
				inv.docstatus === 0
					? `<span class="indicator-pill orange" style="margin-left:6px;">Draft</span>`
					: inv.docstatus === 2
						? `<span class="indicator-pill orange" style="margin-left:6px;">Cancelled</span>`
						: "";
			const { label, color } = get_invoice_indicator(inv);

			$tbody.append(`
				<tr>
					<td>${invoiceLink}${draftBadge}</td>
					<td>${frappe.utils.escape_html(inv.company || "")}</td>
					<td>${frappe.datetime.str_to_user(inv.posting_date)}</td>
					<td>${frappe.utils.escape_html(inv.owner_fullname || "")}</td>
					<td>${format_currency(inv.grand_total, inv.currency)}</td>
					<td>${format_currency(inv.outstanding_amount, inv.currency)}</td>
					<td>
						<span class="indicator-pill ${color}">${__(label)}</span>
					</td>
				</tr>
			`);
		}
	} finally {
		frm._invoice_loading = false;
		wrapper.find(".invoices-loading-msg").hide();
	}
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
		"Not Applied": {
			counter: 1,
			start_date: 1,
			due_date: 1,
			current_interview_count: 1,
			received_amount: 1,
		},
		"Number of Days": {
			counter: 0,
			start_date: 0,
			due_date: 1,
			current_interview_count: 1,
			received_amount: 1,
		},
		"Number of Interviews": {
			counter: 0,
			start_date: 1,
			due_date: 1,
			current_interview_count: 1,
			received_amount: 1,
		},
	};
	const config = read_only_map[condition] || read_only_map["Not Applied"];
	console.log("config: ", config);
	const grid = frm.fields_dict["payment_terms"].grid;
	const grid_row = grid.grid_rows.find((r) => r.doc.name === cdn);
	if (!grid_row) return;

	Object.entries(config).forEach(([fieldname, read_only]) => {
		grid_row.set_field_property(fieldname, "read_only", read_only);
	});
}
