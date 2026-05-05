// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

let _plan_cost = 0;
let _plan_billing_interval = null;
let _plan_billing_interval_count = 0;

frappe.ui.form.on("Subscription", {
	// ================================================================
	// Form refresh: dynamic filters + action buttons
	// ================================================================

	refresh(frm) {
		frm.trigger("setup_action_buttons");
		// Re-load plan info on refresh so totals can recompute correctly
		if (frm.doc.plan) {
			frappe.db.get_doc("Subscription Plan", frm.doc.plan).then((plan) => {
				_plan_cost = plan.rate || 0;
				_plan_billing_interval = plan.billing_interval || null;
				_plan_billing_interval_count = plan.billing_interval_count || 0;
				render_grand_totals(frm);
			});
		} else {
			render_grand_totals(frm);
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("Generate Invoice Now", () => {
				frappe.call({
					method: "verp_staffing.accounts.doctype.subscription.subscription.generate_invoice_now",
					args: {
						subscription: frm.doc.name,
					},
					freeze: true,
					freeze_message: "Generating invoice...",
					callback: function (r) {
						if (r.message) {
							frappe.msgprint({
								title: "Success",
								message: `Invoice created: ${r.message}`,
								indicator: "green",
							});

							frm.reload_doc();
						} else {
							frappe.msgprint({
								title: "No Invoice",
								message: "No invoice generated (not due or skipped).",
								indicator: "orange",
							});
						}
					},
				});
			});
		}
	},

	onload: function (frm) {
		set_account_queries(frm);
	},

	setup_action_buttons(frm) {
		if (frm.doc.docstatus !== 1) return;

		const status = frm.doc.status;

		// ---------------- CANCEL ----------------
		if (!["Cancelled", "Completed"].includes(status)) {
			frm.add_custom_button(
				__("Cancel Subscription"),
				() => {
					const current_end = get_current_period_end(frm);

					// CASE 1: cancel_at_period_end = TRUE → only info, no confirm
					if (frm.doc.cancel_at_period_end && current_end) {
						frappe.msgprint(
							__(
								"Cancellation will take effect at the end of the current billing period ({0}).",
								[frappe.datetime.str_to_user(current_end)],
							),
						);

						return;
					}

					// CASE 2: immediate cancel → confirmation required
					frappe.confirm(
						__("This will cancel the subscription immediately. Continue?"),
						() => {
							frm.call("cancel_subscription").then(() => {
								frappe.msgprint(__("Subscription cancelled successfully"));
								frm.reload_doc();
							});
						},
					);
				},
				__("Actions"),
			);
		}

		// ---------------- PAUSE ----------------
		if (!frm.doc.is_paused && !["Trialing", "Cancelled", "Completed"].includes(status)) {
			frm.add_custom_button(
				__("Pause Subscription"),
				() => {
					const d = new frappe.ui.Dialog({
						title: __("Pause Subscription"),
						fields: [
							{
								label: __("Resume On"),
								fieldname: "resume_date",
								fieldtype: "Date",
								reqd: 1,
								default: frappe.datetime.add_days(frappe.datetime.get_today(), 7),
							},
						],
						primary_action_label: __("Pause"),
						primary_action(values) {
							frm.call("pause_subscription", {
								resume_date: values.resume_date,
							}).then(() => {
								frappe.msgprint(__("Subscription paused successfully"));
								d.hide();
								frm.reload_doc();
							});
						},
					});
					d.show();
				},
				__("Actions"),
			);
		}

		// ---------------- RESUME ----------------
		if (frm.doc.is_paused) {
			frm.add_custom_button(
				__("Resume Subscription"),
				() => {
					frappe.confirm(
						__("Are you sure you want to resume this subscription?"),
						() => {
							frm.call("resume_subscription").then(() => {
								frappe.msgprint(__("Subscription resumed successfully"));
								frm.reload_doc();
							});
						},
					);
				},
				__("Actions"),
			);
		}
	},

	// ================================================================
	// Field-change reactivity
	// ================================================================

	subscription_type(frm) {
		if (frm.doc.subscription_type === "Sales") {
			if (frm.doc.party_type !== "Customer") {
				frm.set_value("party_type", "Customer");
				frm.set_value("party", null);
			}
		} else if (frm.doc.subscription_type === "Purchase") {
			if (frm.doc.party_type !== "Supplier") {
				frm.set_value("party_type", "Supplier");
				frm.set_value("party", null);
			}
		}
	},

	party_type(frm) {
		frm.set_value("party", null);
	},

	company: function (frm) {
		if (!frm.doc.company) return;
		set_account_queries(frm);
	},

	billing_currency(frm) {
		if (frm.doc.billing_currency && frm.doc.billing_currency === frm.doc.company_currency) {
			frm.set_value("conversion_rate", 1);
		}
		(frm.doc.items || []).forEach((row) => {
			if (row.plan) validate_plan_currency(frm, row);
		});
		render_grand_totals(frm);
	},

	start_date(frm) {
		// If trial_period_end is before start_date, snap it to start_date
		if (
			frm.doc.start_date &&
			frm.doc.trial_period_end &&
			frappe.datetime.str_to_obj(frm.doc.trial_period_end) <
				frappe.datetime.str_to_obj(frm.doc.start_date)
		) {
			frm.set_value("trial_period_end", frm.doc.start_date);
		}

		validate_end_date_alignment(frm);
		render_grand_totals(frm);
	},

	end_date(frm) {
		validate_end_date_alignment(frm);
		render_grand_totals(frm);
	},

	trial_period_end(frm) {
		// trial runs from start_date to trial_period_end; can't end before it begins
		if (
			frm.doc.start_date &&
			frm.doc.trial_period_end &&
			frappe.datetime.str_to_obj(frm.doc.trial_period_end) <
				frappe.datetime.str_to_obj(frm.doc.start_date)
		) {
			frm.set_value("trial_period_end", frm.doc.start_date);
		}
		validate_end_date_alignment(frm);
		render_grand_totals(frm);
	},

	is_paused(frm) {
		if (!frm.doc.is_paused) {
			frm.set_value("pause_resume_date", null);
		}
	},

	cancel_at_period_end(frm) {
		if (frm.doc.cancel_at_period_end && frm.doc.docstatus === 1) {
			const current_end = get_current_period_end(frm);
			if (current_end) {
				frappe.show_alert({
					message: __(
						"This subscription will be cancelled at the end of the current period ({0})",
						[frappe.datetime.str_to_user(current_end)],
					),
					indicator: "orange",
				});
			}
		}
	},

	generate_invoice_at(frm) {
		if (frm.doc.generate_invoice_at !== "Days before the current subscription period") {
			frm.set_value("number_of_days", 0);
		}
		render_grand_totals(frm);
	},

	number_of_days(frm) {
		render_grand_totals(frm);
	},

	days_until_due(frm) {
		render_grand_totals(frm);
	},

	plan(frm) {
		if (!frm.doc.plan) {
			_plan_cost = 0;
			_plan_billing_interval = null;
			_plan_billing_interval_count = 0;
			compute_net_total(frm);
			render_grand_totals(frm);
			return;
		}
		frappe.db.get_doc("Subscription Plan", frm.doc.plan).then((plan) => {
			_plan_cost = plan.rate || 0;
			_plan_billing_interval = plan.billing_interval || null;
			_plan_billing_interval_count = plan.billing_interval_count || 0;
			compute_net_total(frm);
			validate_end_date_alignment(frm);
			render_grand_totals(frm);
		});
	},

	qty(frm) {
		compute_net_total(frm);
		render_grand_totals(frm);
	},
});

// ================================================================
// Subscription One Time Charge child events
// ================================================================

frappe.ui.form.on("Subscription One Time Charge", {
	qty(frm, cdt, cdn) {
		calculate_one_time_charge_amount(cdt, cdn);
		render_grand_totals(frm);
	},
	rate(frm, cdt, cdn) {
		calculate_one_time_charge_amount(cdt, cdn);
		render_grand_totals(frm);
	},
	one_time_charges_add(frm) {
		render_grand_totals(frm);
	},
	one_time_charges_remove(frm) {
		render_grand_totals(frm);
	},
});

// ================================================================
// Subscription Discount Schedule child events
// ================================================================

frappe.ui.form.on("Subscription Discount Schedule", {
	from_invoice_number(frm) {
		render_grand_totals(frm);
	},
	to_invoice_number(frm) {
		render_grand_totals(frm);
	},
	discount_type(frm) {
		render_grand_totals(frm);
	},
	discount_value(frm) {
		render_grand_totals(frm);
	},
	applies_on(frm) {
		render_grand_totals(frm);
	},
	discount_schedule_add(frm) {
		render_grand_totals(frm);
	},
	discount_schedule_remove(frm) {
		render_grand_totals(frm);
	},
});

frappe.ui.form.on("Taxes and Charges", {
	charge_type(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (row.charge_type === "Actual") {
			frappe.model.set_value(cdt, cdn, "rate", 0);

			frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn].toggle_editable("rate", false);
			frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn].toggle_editable(
				"tax_amount",
				true,
			);
		} else {
			frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn].toggle_editable("rate", true);
			frm.fields_dict["taxes"].grid.grid_rows_by_docname[cdn].toggle_editable(
				"tax_amount",
				false,
			);
		}
		render_grand_totals(frm);
	},
	rate(frm) {
		render_grand_totals(frm);
	},
	tax_amount(frm) {
		render_grand_totals(frm);
	},
	taxes_add(frm) {
		render_grand_totals(frm);
	},
	taxes_remove(frm) {
		render_grand_totals(frm);
	},
	row_id(frm) {
		render_grand_totals(frm);
	},
});

// ================================================================
// Helpers (module-private)
// ================================================================

function compute_net_total(frm) {
	frm.set_value("net_total", flt(frm.doc.qty) * flt(_plan_cost));
}

function populate_tax_rows_display(frm) {
	// Populate `tax_amount` and `total` columns of the visible Taxes table
	// using the CURRENT (first regular) invoice's discounted net as the base.
	// This gives the user immediate feedback on how taxes resolve for the
	// current period; the schedule below shows how each invoice differs.
	const taxes = frm.doc.taxes || [];
	if (!taxes.length) return;

	const net_per_invoice = flt(frm.doc.qty) * flt(_plan_cost);
	const discount_for_current = compute_discount_for_invoice(frm, 1, net_per_invoice);
	const taxable_net = Math.max(0, net_per_invoice - discount_for_current);

	let cumulative_total = taxable_net;

	taxes.forEach((tax, i) => {
		let tax_amount = 0;

		if (tax.charge_type === "Actual") {
			tax_amount = flt(tax.tax_amount || 0);
		} else if (tax.charge_type === "On Net Total") {
			tax_amount = (taxable_net * flt(tax.rate)) / 100;
		} else if (tax.charge_type === "On Previous Row Amount") {
			const prev = taxes[i - 1];
			if (prev) tax_amount = (flt(prev.tax_amount) * flt(tax.rate)) / 100;
		} else if (tax.charge_type === "On Previous Row Total") {
			const prev = taxes[i - 1];
			if (prev) tax_amount = (flt(prev.total) * flt(tax.rate)) / 100;
		} else if (tax.charge_type === "On Item Quantity") {
			tax_amount = flt(frm.doc.qty) * flt(tax.rate);
		}

		cumulative_total += tax_amount;

		// Skip "Actual" since the user types tax_amount directly
		if (tax.charge_type !== "Actual") {
			frappe.model.set_value(tax.doctype, tax.name, "tax_amount", tax_amount);
		}
		frappe.model.set_value(tax.doctype, tax.name, "total", cumulative_total);
	});

	frm.refresh_field("taxes");
}

function calculate_one_time_charge_amount(cdt, cdn) {
	const row = locals[cdt][cdn];

	const qty = flt(row.qty);
	const rate = flt(row.rate);

	frappe.model.set_value(cdt, cdn, "amount", qty * rate);
}

function get_current_period_end(frm) {
	// Compute the end date of the current (first regular) billing period
	// without storing it on the doc. Used by Cancel button & alerts.
	if (
		!frm.doc.start_date ||
		!frm.doc.plan ||
		!_plan_billing_interval ||
		!_plan_billing_interval_count
	)
		return null;

	let billing_start = frappe.datetime.str_to_obj(frm.doc.start_date);
	if (frm.doc.trial_period_end) {
		const trial_end = frappe.datetime.str_to_obj(frm.doc.trial_period_end);
		billing_start = new Date(trial_end);
		billing_start.setDate(billing_start.getDate() + 1);
	}

	const next_period_start = calculate_end_date(
		billing_start,
		_plan_billing_interval,
		_plan_billing_interval_count,
	);

	const period_end = new Date(next_period_start);
	period_end.setDate(period_end.getDate() - 1);

	return frappe.datetime.obj_to_str(period_end);
}

function validate_end_date_alignment(frm) {
	// `end_date` must align with a billing period boundary.
	// A valid end_date is one of:
	//   billing_start - 1 day                          (no regular invoices)
	//   billing_start + 1*(interval*count) - 1 day     (1 invoice)
	//   billing_start + 2*(interval*count) - 1 day     (2 invoices)
	//   ...
	// where billing_start = start_date (or trial_period_end + 1 day).
	//
	// If the user picks a date that doesn't land on one of these boundaries,
	// snap it down to the nearest valid boundary and warn.
	if (
		!frm.doc.end_date ||
		!frm.doc.start_date ||
		!_plan_billing_interval ||
		!_plan_billing_interval_count
	)
		return;

	const end_date = frappe.datetime.str_to_obj(frm.doc.end_date);

	let billing_start = frappe.datetime.str_to_obj(frm.doc.start_date);
	if (frm.doc.trial_period_end) {
		const trial_end = frappe.datetime.str_to_obj(frm.doc.trial_period_end);
		billing_start = new Date(trial_end);
		billing_start.setDate(billing_start.getDate() + 1);
	}

	// end_date must be >= billing_start - 1 day at minimum, else invalid
	const min_valid = new Date(billing_start);
	min_valid.setDate(min_valid.getDate() - 1);
	if (end_date < min_valid) {
		frm.set_value("end_date", frappe.datetime.obj_to_str(min_valid));
		frappe.show_alert({
			message: __("End Date adjusted to align with billing cycle: {0}", [
				frappe.datetime.str_to_user(frappe.datetime.obj_to_str(min_valid)),
			]),
			indicator: "orange",
		});
		return;
	}

	// Walk billing periods forward; collect valid boundaries until we pass end_date
	let last_valid = new Date(min_valid);
	let cursor = new Date(billing_start);
	const HARD_CAP = 1000;

	for (let i = 0; i < HARD_CAP; i++) {
		const next_period_start = calculate_end_date(
			cursor,
			_plan_billing_interval,
			_plan_billing_interval_count,
		);
		const period_end = new Date(next_period_start);
		period_end.setDate(period_end.getDate() - 1);

		// Exact match -> already aligned, nothing to do
		if (datesEqual(period_end, end_date)) return;

		if (period_end > end_date) break;

		last_valid = period_end;
		cursor = next_period_start;
	}

	// Snap down to the last valid boundary <= end_date
	if (!datesEqual(last_valid, end_date)) {
		frm.set_value("end_date", frappe.datetime.obj_to_str(last_valid));
		frappe.show_alert({
			message: __(
				"End Date must align with the billing cycle ({0} × {1}). Adjusted to {2}.",
				[
					_plan_billing_interval_count,
					_plan_billing_interval,
					frappe.datetime.str_to_user(frappe.datetime.obj_to_str(last_valid)),
				],
			),
			indicator: "orange",
		});
	}
}

function datesEqual(a, b) {
	return (
		a.getFullYear() === b.getFullYear() &&
		a.getMonth() === b.getMonth() &&
		a.getDate() === b.getDate()
	);
}

function calculate_end_date(start_date, interval, count) {
	count = flt(count);
	let date = new Date(start_date);

	if (interval === "Day") {
		date.setDate(date.getDate() + count);
		return date;
	}
	if (interval === "Week") {
		date.setDate(date.getDate() + count * 7);
		return date;
	}
	if (interval === "Month") {
		date.setMonth(date.getMonth() + count);
		return date;
	}
	if (interval === "Year") {
		date.setFullYear(date.getFullYear() + count);
		return date;
	}
	return date;
}

function validate_plan_currency(frm, row) {
	if (!row.plan || !frm.doc.billing_currency) return;
	frappe.db.get_value("Subscription Plan", row.plan, "currency").then((r) => {
		const plan_currency = r.message && r.message.currency;
		if (plan_currency && plan_currency !== frm.doc.billing_currency) {
			frappe.show_alert({
				message: __("Row {0}: plan currency {1} ≠ billing currency {2}", [
					row.idx,
					plan_currency,
					frm.doc.billing_currency,
				]),
				indicator: "red",
			});
		}
	});
}

// ================================================================
// GRAND TOTAL CALCULATION ENGINE
// ================================================================
//
// Builds a per-invoice schedule for the entire subscription duration:
//
//   1. Trial invoices (grand_total = 0) -- one logical row covering the
//      trial period if a trial exists.
//   2. Regular billing periods, starting from `effective_start`
//      (= trial_end + 1 day, or start_date if no trial), repeating
//      every (billing_interval * billing_interval_count) until end_date.
//
// For each REGULAR invoice (numbered 1..N, trial NOT counted):
//   net_total       = qty * plan.rate
//   discount        = sum of applicable Subscription Discount Schedule
//                     rows whose [from_invoice_number, to_invoice_number]
//                     range covers this invoice number.
//                     - "Percentage" + applies_on "Net Amount"
//                         => net_total * value%
//                     - "Percentage" + applies_on "Plan Rate"
//                         => qty * (plan.rate * value%)   (== same math here)
//                     - "Fixed Amount" + applies_on "Net Amount"
//                         => value (capped at net_total)
//                     - "Fixed Amount" + applies_on "Plan Rate"
//                         => qty * value (capped at net_total)
//   discounted_net  = max(0, net_total - discount)
//   one_time_total  = sum(one_time_charges.amount) -- ONLY on the
//                     first regular invoice (invoice #1).
//   taxable_base    = discounted_net   (taxes apply on net, per spec)
//   taxes           = computed using Taxes and Charges rows, same
//                     algorithm as _calculate_taxes(), but using
//                     `taxable_base` as the "net total" reference.
//   grand_total     = discounted_net + one_time_total + taxes_total
//
// Output is rendered into the `total_html` field as a table:
//   Invoice # | Period Start | Period End | Grand Total
// ================================================================

function render_grand_totals(frm) {
	const wrapper = frm.fields_dict.total_html && frm.fields_dict.total_html.$wrapper;
	if (!wrapper) return;

	// Always keep the visible Taxes table in sync with current-invoice values
	populate_tax_rows_display(frm);

	// Guard: need a plan and a start date to compute anything meaningful
	if (
		!frm.doc.start_date ||
		!frm.doc.plan ||
		!_plan_billing_interval ||
		!_plan_billing_interval_count
	) {
		wrapper.html(
			`<div class="text-muted" style="padding:8px;">
				${__("Set Plan and Start Date to see invoice schedule.")}
			</div>`,
		);
		return;
	}

	const schedule = build_invoice_schedule(frm);
	if (!schedule || !schedule.length) {
		wrapper.html(
			`<div class="text-muted" style="padding:8px;">
				${__("No invoices to project. Check start/end dates.")}
			</div>`,
		);
		return;
	}

	const currency = frm.doc.billing_currency || frm.doc.company_currency || "";

	let total_grand = 0;
	let rows_html = "";

	const fmt_date = (d) => (d ? frappe.datetime.str_to_user(frappe.datetime.obj_to_str(d)) : "—");

	schedule.forEach((inv) => {
		total_grand += flt(inv.grand_total);

		const label = inv.is_trial
			? `<span class="indicator-pill yellow">${__("Trial")}</span>`
			: `#${inv.invoice_number}`;

		rows_html += `
			<tr>
				<td style="text-align:center;">${label}</td>
				<td>${fmt_date(inv.period_start)}</td>
				<td>${fmt_date(inv.period_end)}</td>
				<td>${fmt_date(inv.invoice_date)}</td>
				<td>${fmt_date(inv.due_date)}</td>
				<td style="text-align:right;">${format_currency(inv.net_total, currency)}</td>
				<td style="text-align:right;">${
					inv.discount_total ? "-" + format_currency(inv.discount_total, currency) : "—"
				}</td>
				<td style="text-align:right;">${
					inv.one_time_total ? format_currency(inv.one_time_total, currency) : "—"
				}</td>
				<td style="text-align:right;">${
					inv.taxes_total ? format_currency(inv.taxes_total, currency) : "—"
				}</td>
				<td style="text-align:right;"><strong>${format_currency(inv.grand_total, currency)}</strong></td>
			</tr>
		`;
	});

	const html = `
		<div style="overflow-x:auto;">
			<table class="table table-bordered" style="margin-bottom:8px; font-size: 12px;">
				<thead style="background:#f5f7fa;">
					<tr>
						<th style="text-align:center; width: 70px;">${__("Invoice")}</th>
						<th style="width: 105px;">${__("Period Start")}</th>
						<th style="width: 105px;">${__("Period End")}</th>
						<th style="width: 105px;">${__("Invoice Date")}</th>
						<th style="width: 105px;">${__("Due Date")}</th>
						<th style="text-align:right;">${__("Net Total")}</th>
						<th style="text-align:right;">${__("Discount")}</th>
						<th style="text-align:right;">${__("One-Time")}</th>
						<th style="text-align:right;">${__("Taxes")}</th>
						<th style="text-align:right;">${__("Grand Total")}</th>
					</tr>
				</thead>
				<tbody>${rows_html}</tbody>
				<tfoot>
					<tr style="background:#fafafa;">
						<th colspan="9" style="text-align:right;">${__("Subscription Total")}</th>
						<th style="text-align:right;">${format_currency(total_grand, currency)}</th>
					</tr>
				</tfoot>
			</table>
		</div>
	`;

	wrapper.html(html);
}

function build_invoice_schedule(frm) {
	const schedule = [];

	const start_date = frappe.datetime.str_to_obj(frm.doc.start_date);
	const end_date = frm.doc.end_date ? frappe.datetime.str_to_obj(frm.doc.end_date) : null;

	const generate_at = frm.doc.generate_invoice_at || "End of the current subscription period";
	const number_of_days = cint(frm.doc.number_of_days);
	const days_until_due = cint(frm.doc.days_until_due);

	// ---- Trial period invoice (grand_total = 0) ----
	// Trial runs from start_date to trial_period_end (if trial_period_end is set).
	// If trial_period_end is empty, there is no trial.
	let billing_start = start_date;
	if (frm.doc.trial_period_end) {
		const trial_end = frappe.datetime.str_to_obj(frm.doc.trial_period_end);

		// Trial invoice is "issued" at start of trial; no money due, but we
		// still surface the date for completeness.
		schedule.push({
			is_trial: true,
			invoice_number: 0,
			period_start: start_date,
			period_end: trial_end,
			invoice_date: start_date,
			due_date: null,
			net_total: 0,
			discount_total: 0,
			one_time_total: 0,
			taxes_total: 0,
			grand_total: 0,
		});

		// Regular billing begins the day after the trial ends
		billing_start = new Date(trial_end);
		billing_start.setDate(billing_start.getDate() + 1);
	}

	// ---- If open-ended (no end_date), only project the CURRENT (first) invoice ----
	const max_invoices_when_open = 1;

	const interval = _plan_billing_interval;
	const count = flt(_plan_billing_interval_count);

	const net_per_invoice = flt(frm.doc.qty) * flt(_plan_cost);
	const one_time_total_first = (frm.doc.one_time_charges || []).reduce(
		(s, r) => s + flt(r.amount),
		0,
	);

	let invoice_number = 1;
	let period_start = new Date(billing_start);

	// safety cap to avoid runaway loops on weird data
	const HARD_CAP = 1000;

	while (true) {
		// Compute period_end = period_start + (interval * count) - 1 day
		// (so periods are inclusive and don't overlap)
		const next_period_start = calculate_end_date(period_start, interval, count);
		const period_end = new Date(next_period_start);
		period_end.setDate(period_end.getDate() - 1);

		// Stop if we've passed end_date
		if (end_date && period_start > end_date) break;

		// If period_end exceeds end_date, clip it (final partial period)
		let clipped_end = period_end;
		if (end_date && period_end > end_date) {
			clipped_end = end_date;
		}

		// ---- Invoice date for this cycle ----
		let invoice_date;
		if (generate_at === "Beginning of the current subscription period") {
			invoice_date = new Date(period_start);
		} else if (generate_at === "Days before the current subscription period") {
			invoice_date = new Date(period_start);
			invoice_date.setDate(invoice_date.getDate() - number_of_days);
		} else {
			// Default: "End of the current subscription period"
			invoice_date = new Date(clipped_end);
		}

		// ---- Due date = invoice_date + days_until_due ----
		const due_date = new Date(invoice_date);
		due_date.setDate(due_date.getDate() + days_until_due);

		const discount_total = compute_discount_for_invoice(frm, invoice_number, net_per_invoice);
		const discounted_net = Math.max(0, net_per_invoice - discount_total);

		const one_time_total = invoice_number === 1 ? one_time_total_first : 0;

		const taxes_total = compute_taxes_for_invoice(frm, discounted_net);

		const grand_total = discounted_net + one_time_total + taxes_total;

		schedule.push({
			is_trial: false,
			invoice_number,
			period_start: new Date(period_start),
			period_end: new Date(clipped_end),
			invoice_date,
			due_date,
			net_total: net_per_invoice,
			discount_total,
			one_time_total,
			taxes_total,
			grand_total,
		});

		// Termination conditions
		if (!end_date) {
			if (invoice_number >= max_invoices_when_open) break;
		} else {
			if (clipped_end >= end_date) break;
		}

		if (invoice_number >= HARD_CAP) break;

		// Advance to next period
		period_start = next_period_start;
		invoice_number += 1;
	}

	return schedule;
}

function compute_discount_for_invoice(frm, invoice_number, net_total) {
	const rows = frm.doc.discount_schedule || [];
	if (!rows.length) return 0;

	let total_discount = 0;

	rows.forEach((row) => {
		const from_n = cint(row.from_invoice_number) || 1;
		const to_n = row.to_invoice_number ? cint(row.to_invoice_number) : null;

		const in_range = invoice_number >= from_n && (to_n === null || invoice_number <= to_n);
		if (!in_range) return;

		const value = flt(row.discount_value);
		const qty = flt(frm.doc.qty);
		const plan_rate = flt(_plan_cost);

		let amt = 0;

		if (row.discount_type === "Percentage") {
			if (row.applies_on === "Plan Rate") {
				// Discount applied to plan rate, then multiplied by qty
				amt = qty * ((plan_rate * value) / 100);
			} else {
				// Default: applies_on === "Net Amount"
				amt = (net_total * value) / 100;
			}
		} else {
			// Fixed Amount
			if (row.applies_on === "Plan Rate") {
				amt = qty * value;
			} else {
				amt = value;
			}
		}

		total_discount += amt;
	});

	// Cap so discount can't exceed net total
	if (total_discount > net_total) total_discount = net_total;
	return total_discount;
}

function compute_taxes_for_invoice(frm, taxable_net) {
	const taxes = frm.doc.taxes || [];
	if (!taxes.length) return 0;

	// We mirror _calculate_taxes() but operate on the per-invoice
	// `taxable_net` (== discounted net for that invoice) rather than the
	// header-level recurring_total. This way percentage-based taxes
	// reflect the actual invoice base.
	let cumulative_total = taxable_net;
	let taxes_total = 0;
	const computed = []; // hold {tax_amount, total} for previous-row refs

	taxes.forEach((tax, i) => {
		let tax_amount = 0;

		if (tax.charge_type === "Actual") {
			tax_amount = flt(tax.tax_amount || 0);
		} else if (tax.charge_type === "On Net Total") {
			tax_amount = (taxable_net * flt(tax.rate)) / 100;
		} else if (tax.charge_type === "On Previous Row Amount") {
			const prev = computed[i - 1];
			if (prev) tax_amount = (flt(prev.tax_amount) * flt(tax.rate)) / 100;
		} else if (tax.charge_type === "On Previous Row Total") {
			const prev = computed[i - 1];
			if (prev) tax_amount = (flt(prev.total) * flt(tax.rate)) / 100;
		} else if (tax.charge_type === "On Item Quantity") {
			tax_amount = flt(frm.doc.qty) * flt(tax.rate);
		}

		cumulative_total += tax_amount;
		taxes_total += tax_amount;

		computed.push({
			tax_amount: tax_amount,
			total: cumulative_total,
		});
	});

	return taxes_total;
}

function set_account_queries(frm) {
	// store previous company
	let previous_company = frm.doc.company;

	function account_filter() {
		if (!frm.doc.company) {
			return { filters: { name: "__invalid__" } };
		}

		return {
			filters: {
				account_type: ["in", ["Tax", "Chargeable", "Expense"]],
				is_group: 0,
				company: frm.doc.company,
			},
		};
	}

	function discount_account_filter() {
		if (!frm.doc.company) {
			return { filters: { name: "__invalid__" } };
		}

		return {
			filters: {
				company: frm.doc.company,
				is_group: 0,
				report_type: "Profit and Loss",
			},
		};
	}

	// apply queries
	frm.set_query("account", "one_time_charges", account_filter);
	frm.set_query("account_head", "taxes", account_filter);
	frm.set_query("additional_discount_account", discount_account_filter);

	// handle company change
	frm.fields_dict.company.df.onchange = function () {
		const current_company = frm.doc.company;

		// do nothing if same company
		if (current_company === previous_company) return;

		// update tracker
		previous_company = current_company;

		// clear child tables
		(frm.doc.one_time_charges || []).forEach((row) => {
			frappe.model.set_value(row.doctype, row.name, "account", null);
		});

		(frm.doc.taxes || []).forEach((row) => {
			frappe.model.set_value(row.doctype, row.name, "account_head", null);
		});

		// clear main field
		frm.set_value("additional_discount_account", null);
	};
}
