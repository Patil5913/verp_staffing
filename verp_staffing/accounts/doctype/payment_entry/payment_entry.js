// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payment Entry", {
	refresh(frm) {
		if (frm.doc.party_type && !frm.party_account_type) {
			frappe.db.get_value("Party Type", frm.doc.party_type, "account_type").then((r) => {
				frm.party_account_type = r.message?.account_type || null;
			});
		}
		set_currency_labels(frm);
		hide_unhide_fields(frm);
		if (frm.doc.docstatus === 2) return; // Cancelled — nothing to show
		// Lock paid_amount if linked to a payment term
		if (frm.doc.payment_term_row) {
			frm.set_df_property("paid_amount", "read_only", 1);
			// Lock references table — no add, delete, or edit
			frm.set_df_property("references", "read_only", 1);
			frm.set_df_property("references", "cannot_add_rows", 1);
			frm.set_df_property("references", "cannot_delete_rows", 1);

			// Hide the "Get Outstanding" buttons since user can't modify references
			frm.set_df_property("get_outstanding_invoices", "hidden", 1);
			frm.set_df_property("get_outstanding_orders", "hidden", 1);
		}
		const status = frm.doc.verification_status;
		const is_locked = frm.doc.docstatus === 1; // Submitted = locked

		// ── Approve button ─────────────────────────────────────────────
		// Visible when: Pending Verification or Rejected, not yet submitted
		if (!is_locked && status !== "Verified" && status !== null) {
			frm.add_custom_button(
				__("Approve"),
				async () => {
					frappe.confirm(
						`Approve this payment of <b>${frm.doc.paid_amount}</b>
                     <br>This will submit the Payment Entry and cannot be undone.`,
						async () => {
							const r = await frappe.call({
								method: "verp_staffing.accounts.doctype.sales_order.sales_order.verify_payment_entry",
								args: { payment_entry: frm.doc.name },
							});
							if (r.message === "verified") {
								frappe.msgprint({
									title: __("Approved"),
									message: "Payment Entry approved and submitted.",
									indicator: "green",
								});
								frm.reload_doc();
							}
						},
					);
				},
				__("Actions"),
			).addClass("btn-success");
		}

		// ── Reject button ──────────────────────────────────────────────
		// Visible when: Pending Verification only, not submitted, not already verified
		if (!is_locked && status === "Pending Verification") {
			frm.add_custom_button(
				__("Reject"),
				() => {
					const d = new frappe.ui.Dialog({
						title: __("Reject Payment"),
						fields: [
							{
								fieldtype: "Small Text",
								fieldname: "remarks",
								label: __("Reason for Rejection"),
								reqd: 1,
								description:
									"Your name and timestamp will be added automatically.",
							},
						],
						primary_action_label: __("Reject"),
						primary_action: async (values) => {
							d.disable_primary_action();
							try {
								const r = await frappe.call({
									method: "verp_staffing.accounts.doctype.sales_order.sales_order.reject_payment_entry",
									args: {
										payment_entry: frm.doc.name,
										remarks: values.remarks,
									},
								});
								if (r.message === "rejected") {
									d.hide();
									frappe.msgprint({
										title: __("Rejected"),
										message:
											"Payment Entry rejected. Salesperson can re-request.",
										indicator: "red",
									});
									frm.reload_doc();
								}
							} catch (e) {
								d.enable_primary_action();
							}
						},
					});
					d.show();
				},
				__("Actions"),
			).addClass("btn-danger");
		}

		// ── Status indicator banner ────────────────────────────────────
		render_verification_banner(frm);
	},
	onload: function (frm) {
		frm.ignore_doctypes_on_cancel_all = [
			"Sales Invoice",
			"Purchase Invoice",
			"Journal Entry",
			"Bank Transaction",
			"Purchase Order",
			"Sales Order",
		];

		// When the form opens fresh (not from an invoice), clear account
		// currency fields so the user starts clean.
		if (frm.doc.__islocal && !frm.doc.paid_from) {
			frm.set_value("paid_from_account_currency", null);
		}
		if (frm.doc.__islocal && !frm.doc.paid_to) {
			frm.set_value("paid_to_account_currency", null);
		}
	},

	setup: function (frm) {
		// Party Type – custom Party Type master
		frm.set_query("party_type", function () {
			return {
				query: "verp_staffing.accounts.doctype.party_type.party_type.get_party_type",
				filters: {
					account_type:
						frm.doc.payment_type === "Receive"
							? "Receivable"
							: frm.doc.payment_type === "Pay"
								? "Payable"
								: undefined,
				},
			};
		});

		frm.set_query("paid_from", function () {
			validate_company(frm);
			const party_account_type = frm.party_account_type || "Receivable";
			const account_types = ["Pay", "Internal Transfer"].includes(frm.doc.payment_type)
				? ["Bank", "Cash"]
				: [party_account_type].concat(
						frm.doc.party_type === "Shareholder" ? ["Equity"] : [],
					);
			return {
				filters: {
					account_type: ["in", account_types],
					is_group: 0,
					company: frm.doc.company,
				},
			};
		});

		frm.set_query("paid_to", function () {
			validate_company(frm);
			const party_account_type = frm.party_account_type || "Receivable";
			const account_types = ["Receive", "Internal Transfer"].includes(frm.doc.payment_type)
				? ["Bank", "Cash"]
				: [party_account_type].concat(
						frm.doc.party_type === "Shareholder" ? ["Equity"] : [],
					);
			return {
				filters: {
					account_type: ["in", account_types],
					is_group: 0,
					company: frm.doc.company,
				},
			};
		});

		frm.set_query("party_bank_account", function () {
			return {
				filters: {
					is_company_account: 0,
					party_type: frm.doc.party_type,
					party: frm.doc.party,
				},
			};
		});

		frm.set_query("bank_account", function () {
			return { filters: { is_company_account: 1, company: frm.doc.company } };
		});

		frm.set_query("account", "deductions", function () {
			return { filters: { is_group: 0, company: frm.doc.company } };
		});

		frm.set_query("reference_doctype", "references", function () {
			let doctypes = [];
			if (frm.party_account_type === "Receivable" || frm.doc.party_type === "Customer") {
				doctypes = ["Sales Invoice", "Journal Entry"];
			} else if (frm.party_account_type === "Payable" || frm.doc.party_type === "Supplier") {
				doctypes = ["Purchase Order", "Purchase Invoice", "Journal Entry"];
			}
			return { filters: [["DocType", "name", "in", doctypes]] };
		});

		frm.set_query("reference_name", "references", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			const filters = { docstatus: 1 };
			if (frm.doc.company) filters["company"] = frm.doc.company;
			const party_type_doctypes = [
				"Sales Invoice",
				"Sales Order",
				"Purchase Invoice",
				"Purchase Order",
			];
			if (
				frm.doc.party_type &&
				frm.doc.party &&
				in_list(party_type_doctypes, row.reference_doctype)
			) {
				filters[frm.doc.party_type.toLowerCase()] = frm.doc.party;
			}
			return { filters };
		});

		frm.set_query("account_head", "taxes", function () {
			return { filters: { is_group: 0, company: frm.doc.company } };
		});
	},

	company: function (frm) {
		set_currency_labels(frm);
		hide_unhide_fields(frm);
	},

	currency: async function (frm) {
		const r = await frappe.db.get_value("Company", frm.doc.company, "default_currency");
		const company_currency = r.message.default_currency;
		if (frm.doc.currency === company_currency) {
			frm.set_value("conversion_rate", 1);
		}
		set_currency_labels(frm);
		update_exchange_description(frm);
		recalculate_base_amounts(frm);
		hide_unhide_fields(frm);
	},

	conversion_rate: function (frm) {
		update_exchange_description(frm);
		recalculate_base_amounts(frm);
	},

	payment_type: function (frm) {
		if (frm.doc.payment_type === "Internal Transfer") {
			["party", "party_type", "paid_from", "paid_to"].forEach((f) => frm.set_value(f, null));
			frm.clear_table("references");
			frm.refresh_field("references");
		} else {
			if (frm.doc.party) on_party_change(frm);
		}
	},

	party_type: function (frm) {
		if (!frm.doc.party_type) {
			frm.party_account_type = null;
			return;
		}

		frappe.db.get_value("Party Type", frm.doc.party_type, "account_type").then((r) => {
			frm.party_account_type = r.message?.account_type || null;
			frm.refresh_field("reference_doctype");
		});

		frappe.db.exists("Party Type", frm.doc.party_type).then((exists) => {
			if (!exists) {
				frm.set_value("party_type", "");
				frappe.msgprint(
					__("'{0}' is not configured in Party Type master.", [frm.doc.party_type]),
				);
				return;
			}
			if (frm.doc.party) {
				[
					"party",
					"paid_from",
					"paid_to",
					"paid_from_account_currency",
					"paid_to_account_currency",
				].forEach((f) => frm.set_value(f, null));
				frm.clear_table("references");
				frm.refresh_field("references");
			}
		});
	},

	party: function (frm) {
		if (!frm.doc.company) {
			frappe.msgprint("Please select Company first");
			frm.set_value("party", "");
			return;
		}
		on_party_change(frm);
	},

	get_outstanding_invoices: function (frm) {
		get_outstanding_documents(frm, true, false);
	},

	get_outstanding_orders: function (frm) {
		get_outstanding_documents(frm, false, true);
	},

	paid_from: function (frm) {
		if (frm.doc.paid_from && frm.doc.paid_to && frm.doc.paid_from === frm.doc.paid_to) {
			frappe.throw(__("Paid From and Paid To accounts cannot be the same."));
		}
		if (frm.set_party_account_based_on_party) return;
		set_account_currency_and_balance(
			frm,
			frm.doc.paid_from,
			"paid_from_account_currency",
			function (frm) {
				if (frm.doc.payment_type === "Pay") on_paid_amount_change(frm);
				on_paid_from_currency_change(frm);
			},
		);
	},

	paid_to: function (frm) {
		if (frm.doc.paid_from && frm.doc.paid_to && frm.doc.paid_from === frm.doc.paid_to) {
			frappe.throw(__("Paid From and Paid To accounts cannot be the same."));
		}
		if (frm.set_party_account_based_on_party) return;
		set_account_currency_and_balance(
			frm,
			frm.doc.paid_to,
			"paid_to_account_currency",
			function (frm) {
				on_paid_to_currency_change(frm);
			},
		);
	},

	paid_from_account_currency: function (frm) {
		on_paid_from_currency_change(frm);
	},

	paid_to_account_currency: function (frm) {
		on_paid_to_currency_change(frm);
	},

	paid_amount: function (frm) {
		on_paid_amount_change(frm);
	},

	write_off_difference_amount: function (frm) {
		set_write_off_deduction(frm);
	},
});

frappe.ui.form.on("Payment Entry Reference", {
	reference_doctype: function (frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "reference_name", null);
	},

	reference_name: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.reference_name || !row.reference_doctype) return;

		const party_account_currency =
			frm.doc.payment_type === "Receive"
				? frm.doc.paid_from_account_currency
				: frm.doc.paid_to_account_currency;

		frappe.call({
			method: "verp_staffing.accounts.doctype.payment_entry.payment_entry.get_reference_details",
			args: {
				reference_doctype: row.reference_doctype,
				reference_name: row.reference_name,
				party_account_currency: party_account_currency || frm.doc.company_currency,
				party_type: frm.doc.party_type,
				party: frm.doc.party,
			},
			callback: function (r) {
				if (!r.message) return;
				const d = r.message;

				if (flt(d.outstanding_amount) <= 0) {
					frappe.msgprint({
						title: __("Already Paid"),
						indicator: "red",
						message: __(
							"{0} '{1}' has no outstanding amount. It is already fully paid.",
							[row.reference_doctype, row.reference_name],
						),
					});
					frappe.model.set_value(cdt, cdn, "reference_name", "");
					frappe.model.set_value(cdt, cdn, "invoice_currency", "");
					frappe.model.set_value(cdt, cdn, "allocated_amount", 0);
					frappe.model.set_value(cdt, cdn, "outstanding_amount", 0);
					frappe.model.set_value(cdt, cdn, "total_amount", 0);
					return;
				}

				if (frm.doc.currency && d.currency && frm.doc.currency !== d.currency) {
					frappe.msgprint({
						title: __("Currency Mismatch"),
						indicator: "red",
						message: __(
							"Invoice currency is <b>{0}</b> but Payment Entry currency is <b>{1}</b>. Both Currencys must be same.",
							[d.currency, frm.doc.currency],
						),
					});
					frappe.model.set_value(cdt, cdn, "reference_name", "");
					frappe.model.set_value(cdt, cdn, "invoice_currency", "");
					frappe.model.set_value(cdt, cdn, "allocated_amount", 0);
					return;
				}

				frappe.model.set_value(cdt, cdn, "invoice_currency", d.currency);
				frappe.model.set_value(cdt, cdn, "total_amount", flt(d.total_amount));
				frappe.model.set_value(cdt, cdn, "outstanding_amount", flt(d.outstanding_amount));
				frappe.model.set_value(cdt, cdn, "allocated_amount", flt(d.outstanding_amount));
				frappe.model.set_value(cdt, cdn, "exchange_rate", flt(d.exchange_rate) || 1);
				if (d.due_date) frappe.model.set_value(cdt, cdn, "due_date", d.due_date);

				frm.refresh_field("references");
				frm.fields_dict.references.grid.refresh();
				set_total_allocated_amount(frm);
			},
		});
	},

	allocated_amount: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (flt(row.allocated_amount) > flt(row.outstanding_amount)) {
			frappe.msgprint({
				title: __("Over-allocation"),
				indicator: "red",
				message: __(
					"Row #{0}: Allocated Amount <b>{1}</b> cannot exceed Outstanding Amount <b>{2}</b>.",
					[row.idx, row.allocated_amount, row.outstanding_amount],
				),
			});
			frappe.model.set_value(cdt, cdn, "allocated_amount", flt(row.outstanding_amount));
			return;
		}

		const total_allocated = (frm.doc.references || []).reduce(
			(sum, r) => sum + flt(r.allocated_amount),
			0,
		);
		set_total_allocated_amount(frm);
	},

	references_remove: function (frm) {
		set_total_allocated_amount(frm);
		if (!(frm.doc.references || []).length) {
			const paid_amount = flt(frm.doc.paid_amount);

			// Clear deductions table
			frm.clear_table("deductions");

			frm.refresh_field("deductions");

			// Set all amount as unallocated
			frm.set_value("unallocated_amount", paid_amount);

			frm.set_value(
				"base_unallocated_amount",
				paid_amount * (flt(frm.doc.conversion_rate) || 1),
			);

			// Reset difference amount
			frm.set_value("difference_amount", 0);

			frm.set_value("base_difference_amount", 0);
		}
	},
});

frappe.ui.form.on("Payment Entry Deduction", {
	amount: function (frm) {
		set_unallocated_amount(frm);
	},
	deductions_remove: function (frm) {
		set_unallocated_amount(frm);
	},
});

frappe.ui.form.on("Advance Taxes and Charges", {
	rate: function (frm) {
		apply_taxes(frm);
		set_unallocated_amount(frm);
	},
	tax_amount: function (frm) {
		apply_taxes(frm);
		set_unallocated_amount(frm);
	},
	charge_type: function (frm) {
		apply_taxes(frm);
		set_unallocated_amount(frm);
	},
	row_id: function (frm) {
		apply_taxes(frm);
		set_unallocated_amount(frm);
	},
	included_in_paid_amount: function (frm) {
		apply_taxes(frm);
		set_unallocated_amount(frm);
	},
	add_deduct_tax: function (frm) {
		apply_taxes(frm);
		set_unallocated_amount(frm);
	},
	taxes_remove: function (frm) {
		apply_taxes(frm);
		set_unallocated_amount(frm);
	},
});

function validate_company(frm) {
	if (!frm.doc.company) {
		frappe.throw({ message: __("Please select a Company first."), title: __("Mandatory") });
	}
}

function update_exchange_description(frm) {
	const { currency, company_currency, conversion_rate } = frm.doc;
	if (!currency || !company_currency) {
		frm.set_df_property("conversion_rate", "description", "");
		return;
	}
	if (currency === company_currency) {
		frm.set_df_property("conversion_rate", "description", __("Same currency — rate = 1"));
		return;
	}
	let text = `1 ${currency} = ${conversion_rate || "?"} ${company_currency}`;
	if (conversion_rate) {
		text += ` | 1 ${company_currency} = ${(1 / conversion_rate).toFixed(6)} ${currency}`;
	}
	frm.set_df_property("conversion_rate", "description", text);
}

function recalculate_base_amounts(frm) {
	const rate = flt(frm.doc.conversion_rate) || 1;
	if (frm.doc.paid_amount) frm.set_value("base_paid_amount", flt(frm.doc.paid_amount) * rate);
	apply_taxes(frm);
	set_total_allocated_amount(frm);
}

function on_paid_from_currency_change(frm) {
	if (!frm.doc.paid_from_account_currency || !frm.doc.company) return;
	set_currency_labels(frm);
}

function on_paid_to_currency_change(frm) {
	set_currency_labels(frm);
}

function on_paid_amount_change(frm) {
	if (!frm.doc.paid_from_account_currency || !frm.doc.paid_to_account_currency) return;
	const rate = flt(frm.doc.conversion_rate) || 1;
	frm.set_value("base_paid_amount", flt(frm.doc.paid_amount) * rate);

	apply_taxes(frm);
	set_total_allocated_amount(frm);
	hide_unhide_fields(frm);
}

function on_party_change(frm) {
	if (!(frm.doc.payment_type && frm.doc.party_type && frm.doc.party && frm.doc.company)) return;

	if (!frm.doc.posting_date) {
		frappe.msgprint(__("Please select Posting Date before selecting Party"));
		frm.set_value("party", "");
		return;
	}

	frappe.db.exists("Party Type", frm.doc.party_type).then((exists) => {
		if (!exists) {
			frappe.msgprint(__("Party Type '{0}' is not valid.", [frm.doc.party_type]));
			frm.set_value("party", "");
			return;
		}

		frm.set_party_account_based_on_party = true;

		frappe.call({
			method: "verp_staffing.accounts.doctype.payment_entry.payment_entry.get_party_details",
			args: {
				company: frm.doc.company,
				party_type: frm.doc.party_type,
				party: frm.doc.party,
				date: frm.doc.posting_date,
			},
			callback: function (r) {
				if (!r.message) return;
				frappe.run_serially([
					() => {
						if (frm.doc.payment_type === "Receive") {
							frm.set_value("paid_from", r.message.party_account);
							frm.set_value(
								"paid_from_account_currency",
								r.message.party_account_currency,
							);
						} else if (frm.doc.payment_type === "Pay") {
							frm.set_value("paid_to", r.message.party_account);
							frm.set_value(
								"paid_to_account_currency",
								r.message.party_account_currency,
							);
						}
					},
					() => frm.set_value("party_name", r.message.party_name),
					() => {
						frm.clear_table("references");
						frm.refresh_field("references");
					},
					() => hide_unhide_fields(frm),
					() => set_currency_labels(frm),
					() => {
						frm.set_party_account_based_on_party = false;
						if (r.message.party_bank_account)
							frm.set_value("party_bank_account", r.message.party_bank_account);
						if (r.message.bank_account)
							frm.set_value("bank_account", r.message.bank_account);
					},
				]);
			},
		});
	});
}

function set_write_off_deduction(frm) {
	const difference_amount = flt(frm.doc.difference_amount);

	if (!difference_amount) return;

	frappe.call({
		method: "verp_staffing.accounts.doctype.payment_entry.payment_entry.get_company_defaults",

		args: {
			company: frm.doc.company,
		},

		callback: function (response) {
			const write_off_account = response.message?.write_off_account;

			if (!write_off_account) {
				frappe.msgprint(__("Please set Write Off Account in Company master."));

				return;
			}

			let row = (frm.doc.deductions || []).find((t) => t.account === write_off_account);

			if (!row) {
				row = frm.add_child("deductions");

				row.account = write_off_account;
			}

			row.amount = flt(row.amount) + difference_amount;

			frm.refresh_field("deductions");

			set_unallocated_amount(frm);
		},
	});
}

function set_account_currency_and_balance(frm, account, currency_field, callback) {
	if (!frm.doc.posting_date || !account) return;
	frappe.call({
		method: "verp_staffing.accounts.doctype.payment_entry.payment_entry.get_account_details",
		args: { account, date: frm.doc.posting_date },
		callback: function (r) {
			if (!r.message) return;
			frappe.run_serially([
				() => frm.set_value(currency_field, r.message["account_currency"]),
				() => {
					if (callback) callback(frm);
					set_currency_labels(frm);
					hide_unhide_fields(frm);
				},
			]);
		},
	});
}

function get_outstanding_documents(frm, get_invoices, get_orders) {
	if (!frm.doc.party) {
		frappe.msgprint(__("Please select Party first."));
		return;
	}
	check_mandatory_to_fetch(frm);

	const today = frappe.datetime.get_today();
	const fields = [
		{ fieldtype: "Section Break", label: __("Posting Date") },
		{
			fieldtype: "Date",
			label: __("From Date"),
			fieldname: "from_posting_date",
			default: frappe.datetime.add_days(today, -30),
		},
		{ fieldtype: "Column Break" },
		{ fieldtype: "Date", label: __("To Date"), fieldname: "to_posting_date", default: today },
		{ fieldtype: "Section Break", label: __("Outstanding Amount") },
		{
			fieldtype: "Float",
			label: __("Greater Than Amount"),
			fieldname: "outstanding_amt_greater_than",
			default: 0,
		},
		{ fieldtype: "Column Break" },
		{
			fieldtype: "Float",
			label: __("Less Than Amount"),
			fieldname: "outstanding_amt_less_than",
		},
		{ fieldtype: "Section Break" },
		{
			fieldtype: "Check",
			label: __("Allocate Payment Amount"),
			fieldname: "allocate_payment_amount",
			default: 1,
		},
	];

	const btn_text = get_invoices ? "Get Outstanding Invoices" : "Get Outstanding Orders";

	frappe.prompt(
		fields,
		function (filters) {
			frm.clear_table("references");

			const args = {
				posting_date: frm.doc.posting_date,
				company: frm.doc.company,
				party_type: frm.doc.party_type,
				payment_type: frm.doc.payment_type,
				party: frm.doc.party,
				party_account:
					frm.doc.payment_type === "Receive" ? frm.doc.paid_from : frm.doc.paid_to,
				...filters,
			};

			if (get_invoices) args["get_outstanding_invoices"] = true;
			else args["get_orders_to_be_billed"] = true;

			frappe.call({
				method: "verp_staffing.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents",
				args: { args },
				callback: function (r) {
					if (!r.message) return;
					r.message.forEach(function (d) {
						const row = frm.add_child("references");
						row.reference_doctype = d.voucher_type;
						row.reference_name = d.voucher_no;
						row.invoice_currency = d.currency;
						row.due_date = d.due_date;
						row.total_amount = d.invoice_amount;
						row.outstanding_amount = d.outstanding_amount;
						row.allocated_amount = filters.allocate_payment_amount
							? d.allocated_amount
							: 0;
						row.exchange_rate = d.exchange_rate || 1;
					});
					frm.refresh_field("references");
					if (filters.allocate_payment_amount) set_total_allocated_amount(frm);
				},
			});
		},
		__("Filters"),
		__(btn_text),
	);
}

function render_verification_banner(frm) {
	if (frm.is_new()) return;
	const status = frm.doc.verification_status;
	if (!status) return;

	const config = {
		"Pending Verification": { color: "orange", msg: "Awaiting accountant review." },
		Verified: { color: "green", msg: "Payment verified and submitted." },
		Rejected: { color: "red", msg: frm.doc.rejection_remarks || "Payment rejected." },
	};

	const c = config[status];
	if (!c) return;

	frm.dashboard.set_headline_alert(
		`<div class="alert alert-${c.color === "green" ? "success" : c.color === "red" ? "danger" : "warning"}" 
              style="margin:0">
            <b>${status}</b> — ${c.msg}
        </div>`,
	);
}

function check_mandatory_to_fetch(frm) {
	["company", "party_type", "party", "payment_type"].forEach(function (field) {
		if (!frm.doc[field]) {
			frappe.msgprint(__("Please select {0} first", [field.replace(/_/g, " ")]));
		}
	});
}

function apply_taxes(frm) {
	initialize_taxes(frm);
	determine_exclusive_rate(frm);
	calculate_taxes(frm);
}

function initialize_taxes(frm) {
	$.each(frm.doc.taxes || [], function (i, tax) {
		validate_taxes_and_charges(frm, tax);
		validate_inclusive_tax(frm, tax);
		const reset = [
			"total",
			"tax_fraction_for_current_item",
			"grand_total_fraction_for_current_item",
		];
		if (tax.charge_type !== "Actual") reset.push("tax_amount");
		$.each(reset, function (j, f) {
			tax[f] = 0.0;
		});
	});
	frm.doc.paid_amount_after_tax = flt(frm.doc.base_paid_amount);
}

function determine_exclusive_rate(frm) {
	const has_inclusive = (frm.doc.taxes || []).some((t) => cint(t.included_in_paid_amount));
	if (!has_inclusive) return;

	let cumulated = 0.0;
	$.each(frm.doc.taxes || [], function (i, tax) {
		tax.tax_fraction_for_current_item = get_current_tax_fraction(frm, tax);
		tax.grand_total_fraction_for_current_item =
			i === 0
				? 1 + tax.tax_fraction_for_current_item
				: frm.doc.taxes[i - 1].grand_total_fraction_for_current_item +
					tax.tax_fraction_for_current_item;
		cumulated += tax.tax_fraction_for_current_item;
	});
	if (cumulated) {
		frm.doc.paid_amount_after_tax = flt(frm.doc.base_paid_amount / (1 + cumulated));
	}
}

async function calculate_taxes(frm) {
	frm.doc.total_taxes_and_charges = 0.0;
	frm.doc.base_total_taxes_and_charges = 0.0;

	const rate = flt(frm.doc.conversion_rate) || 1;
	const r = await frappe.db.get_value("Company", frm.doc.company, "default_currency");

	const company_currency = r.message.default_currency;

	let actual_tax_dict = {};
	$.each(frm.doc.taxes || [], function (i, tax) {
		if (tax.charge_type === "Actual") actual_tax_dict[tax.idx] = flt(tax.tax_amount);
	});

	$.each(frm.doc.taxes || [], function (i, tax) {
		let current = get_current_tax_amount(frm, tax);

		if (tax.charge_type === "Actual") {
			actual_tax_dict[tax.idx] -= current;
			if (i === (frm.doc.taxes || []).length - 1) current += actual_tax_dict[tax.idx];
		}

		tax.tax_amount = current;
		tax.base_tax_amount = current;

		const signed = tax.add_deduct_tax === "Deduct" ? -current : current;
		tax.total =
			i === 0
				? flt(frm.doc.paid_amount_after_tax + signed)
				: flt(frm.doc.taxes[i - 1].total + signed);
		tax.base_total = tax.total;

		if (frm.doc.payment_type === "Pay") {
			const curr = frm.doc.paid_to_account_currency || "";
			frm.doc.total_taxes_and_charges +=
				curr && curr !== company_currency ? flt(current / rate) : current;
		} else if (frm.doc.payment_type === "Receive") {
			const curr = frm.doc.paid_from_account_currency || "";
			frm.doc.total_taxes_and_charges +=
				curr && curr !== company_currency ? flt(current / rate) : current;
		}
		frm.doc.base_total_taxes_and_charges += current;
	});

	if (frm.doc.taxes && frm.doc.taxes.length) {
		frm.doc.paid_amount_after_tax = frm.doc.taxes[frm.doc.taxes.length - 1].base_total;
	}

	const applicable_tax = frm.doc.total_taxes_and_charges || 0;
	frm.set_value("paid_amount_after_tax", flt(frm.doc.paid_amount) + applicable_tax);
	frm.set_value(
		"base_paid_amount_after_tax",
		flt(flt(frm.doc.paid_amount) + applicable_tax) * rate,
	);
	frm.refresh_field("taxes");
	frm.refresh_field("total_taxes_and_charges");
	frm.refresh_field("base_total_taxes_and_charges");

	set_total_allocated_amount(frm);
}

function get_current_tax_fraction(frm, tax) {
	let fraction = 0.0;
	if (!cint(tax.included_in_paid_amount)) return fraction;
	if (tax.charge_type === "On Paid Amount") {
		fraction = tax.rate / 100.0;
	} else if (tax.charge_type === "On Previous Row Amount") {
		fraction =
			(tax.rate / 100.0) * frm.doc.taxes[cint(tax.row_id) - 1].tax_fraction_for_current_item;
	} else if (tax.charge_type === "On Previous Row Total") {
		fraction =
			(tax.rate / 100.0) *
			frm.doc.taxes[cint(tax.row_id) - 1].grand_total_fraction_for_current_item;
	}
	if (tax.add_deduct_tax === "Deduct") fraction *= -1;
	return fraction;
}

function get_current_tax_amount(frm, tax) {
	if (tax.charge_type === "Actual") return flt(tax.tax_amount);
	if (tax.charge_type === "On Paid Amount")
		return flt((tax.rate / 100.0) * frm.doc.paid_amount_after_tax);
	if (tax.charge_type === "On Previous Row Amount")
		return flt((tax.rate / 100.0) * frm.doc.taxes[cint(tax.row_id) - 1].tax_amount);
	if (tax.charge_type === "On Previous Row Total")
		return flt((tax.rate / 100.0) * frm.doc.taxes[cint(tax.row_id) - 1].total);
	return 0.0;
}

function validate_taxes_and_charges(frm, tax) {
	let msg = "";
	if (tax.account_head && !tax.description) {
		tax.description = tax.account_head.split(" - ")[0];
	}
	if (!tax.charge_type && (tax.row_id || tax.rate || tax.tax_amount)) {
		msg = __("Please select Charge Type first");
		tax.row_id = "";
		tax.rate = tax.tax_amount = 0.0;
	} else if (
		["Actual", "On Net Total", "On Paid Amount"].includes(tax.charge_type) &&
		tax.row_id
	) {
		msg = __(
			"Can refer row only if charge type is 'On Previous Row Amount' or 'On Previous Row Total'",
		);
		tax.row_id = "";
	} else if (["On Previous Row Amount", "On Previous Row Total"].includes(tax.charge_type)) {
		if (tax.idx === 1) {
			msg = __("Cannot select 'On Previous Row' charge type for the first row");
			tax.charge_type = "";
		} else if (!tax.row_id) {
			tax.row_id = tax.idx - 1;
		} else if (cint(tax.row_id) >= cint(tax.idx)) {
			msg = __("Row ID must be less than the current row number");
			tax.row_id = "";
		}
	}
	if (msg) {
		frappe.validated = false;
		frappe.throw(msg);
	}
}

function validate_inclusive_tax(frm, tax) {
	if (!cint(tax.included_in_paid_amount)) return;
	if (tax.charge_type === "Actual") {
		frappe.throw(
			__("Charge type 'Actual' in row {0} cannot be included in paid amount.", [tax.idx]),
		);
	}
}

function set_total_allocated_amount(frm) {
	const rate = flt(frm.doc.conversion_rate) || 1;

	let total_allocated = 0;
	let base_total_allocated = 0;

	$.each(frm.doc.references || [], function (i, row) {
		if (row.allocated_amount) {
			total_allocated += flt(row.allocated_amount);
			base_total_allocated += flt(row.allocated_amount) * rate;
		}
	});

	frm.set_value("total_allocated_amount", Math.abs(total_allocated));
	frm.set_value("base_total_allocated_amount", Math.abs(base_total_allocated));

	set_unallocated_amount(frm);
}

function set_unallocated_amount(frm) {
	let unallocated = 0;
	const rate = flt(frm.doc.conversion_rate) || 1;

	if (frm.doc.party) {
		const paid = flt(frm.doc.paid_amount);
		const total_allocated = flt(frm.doc.total_allocated_amount);
		const deductions = frappe.utils.sum($.map(frm.doc.deductions || [], (d) => flt(d.amount)));

		if (frm.doc.payment_type === "Receive") {
			unallocated = Math.max(0, paid - total_allocated - deductions);
		} else if (frm.doc.payment_type === "Pay") {
			unallocated = Math.max(0, total_allocated - deductions);
		}
	}

	frm.set_value("unallocated_amount", unallocated);
	frm.set_value("base_unallocated_amount", unallocated * rate);

	set_difference_amount(frm);
}
function set_difference_amount(frm) {
	const rate = flt(frm.doc.conversion_rate) || 1;
	const total_allocated = flt(frm.doc.total_allocated_amount);
	const paid = flt(frm.doc.paid_amount);
	const deductions = frappe.utils.sum($.map(frm.doc.deductions || [], (d) => flt(d.amount)));
	const included_taxes = get_included_taxes(frm);

	let difference = 0;
	if (paid === total_allocated) {
		difference = paid - total_allocated;
	} else if (paid < total_allocated) {
		difference = total_allocated - paid;
	} else {
		difference = 0;
	}

	const net_diff = difference - deductions + included_taxes;
	frm.set_value("difference_amount", flt(net_diff));
	frm.set_value("base_difference_amount", flt(net_diff) * rate);

	hide_unhide_fields(frm);
}

async function hide_unhide_fields(frm) {
	const r = await frappe.db.get_value("Company", frm.doc.company, "default_currency");
	const company_currency = r.message.default_currency;
	const is_multi = !!(frm.doc.currency && frm.doc.currency !== company_currency);

	[
		"base_paid_amount",
		"base_total_allocated_amount",
		"base_unallocated_amount",
		"base_difference_amount",
		"base_total_taxes_and_charges",
	].forEach((f) => frm.toggle_display(f, is_multi));

	const party_amount = frm.doc.payment_type === "Receive";
	flt(frm.doc.paid_amount);
	frm.toggle_display(
		"write_off_difference_amount",
		!!(
			frm.doc.difference_amount &&
			frm.doc.party &&
			flt(frm.doc.total_allocated_amount) > party_amount
		),
	);
}

function set_currency_labels(frm) {
	const currency = frm.doc.currency || "";
	const company_currency = frm.doc.company_currency || "";

	const label = (fieldname, curr) => {
		if (!frm.fields_dict[fieldname]) return;
		const base = frm.fields_dict[fieldname].df.label.split(" (")[0];
		frm.set_df_property(fieldname, "label", curr ? `${base} (${curr})` : base);
	};

	label("paid_amount", currency);
	label("difference_amount", currency);
	label("unallocated_amount", currency);
	label("total_allocated_amount", currency);
	label("total_taxes_and_charges", currency);

	label("base_paid_amount", company_currency);
	label("base_difference_amount", company_currency);
	label("base_unallocated_amount", company_currency);
	label("base_total_allocated_amount", company_currency);
	label("base_total_taxes_and_charges", company_currency);

	frm.refresh_fields();
}

function get_included_taxes(frm) {
	let total = 0;
	$.each(frm.doc.taxes || [], function (i, tax) {
		if (!cint(tax.included_in_paid_amount)) return;
		total +=
			tax.add_deduct_tax === "Add" ? flt(tax.base_tax_amount) : -flt(tax.base_tax_amount);
	});
	return total;
}
