// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.provide("verp_staffing.accounts");
frappe.provide("verp_staffing.journal_entry");

frappe.ui.form.on("Journal Entry", {
	refresh: function (frm) {
		if (frm.doc.docstatus > 0) {
			frm.add_custom_button(
				__("Ledger"),
				function () {
					frappe.route_options = {
						voucher_no: frm.doc.name,
						from_date: frm.doc.posting_date,
						to_date: moment(frm.doc.modified).format("YYYY-MM-DD"),
						company: frm.doc.company,
						finance_book: frm.doc.finance_book,
						categorize_by: "",
						show_cancelled_entries: frm.doc.docstatus === 2,
					};
					frappe.set_route("query-report", "General Ledger");
				},
				__("View"),
			);
		}

		if (frm.doc.docstatus == 1) {
			frm.add_custom_button(
				__("Reverse Journal Entry"),
				function () {
					return verp_staffing.journal_entry.reverse_journal_entry(frm);
				},
				__("Actions"),
			);
		}

		if (frm.doc.__islocal) {
			frm.add_custom_button(__("Quick Entry"), function () {
				return verp_staffing.journal_entry.quick_entry(frm);
			});
		}

		// hide /unhide fields based on currency
		verp_staffing.journal_entry.toggle_fields_based_on_currency(frm);
	},
	before_save: function (frm) {
		if (frm.doc.docstatus == 0 ) {
			let payment_entry_references = frm.doc.accounts.filter(
				(elem) => elem.reference_type == "Payment Entry",
			);
			if (payment_entry_references.length > 0) {
				let rows = payment_entry_references.map((x) => "#" + x.idx);
				frappe.throw(
					__(
						"Rows: {0} have 'Payment Entry' as reference_type. This should not be set manually.",
						[frappe.utils.comma_and(rows)],
					),
				);
			}
		}
	},

	get_outstanding_invoices: function (frm) {
		open_outstanding_dialog(frm);
	},

	multi_currency: function (frm) {
		verp_staffing.journal_entry.toggle_fields_based_on_currency(frm);
	},

	posting_date: function (frm) {
		if (!frm.doc.multi_currency || !frm.doc.posting_date) return;

		$.each(frm.doc.accounts || [], function (i, row) {
			verp_staffing.journal_entry.set_exchange_rate(frm, row.doctype, row.name);
		});
	},

	voucher_type: function (frm) {
		if (!frm.doc.company) return null;

		if (
			!(frm.doc.accounts || []).length ||
			((frm.doc.accounts || []).length === 1 && !frm.doc.accounts[0].account)
		) {
			if (["Bank Entry", "Cash Entry"].includes(frm.doc.voucher_type)) {
				return frappe.call({
					type: "GET",
					method: "verp_staffing.accounts.doctype.journal_entry.journal_entry.get_default_bank_cash_account",
					args: {
						account_type:
							frm.doc.voucher_type == "Bank Entry"
								? "Bank"
								: frm.doc.voucher_type == "Cash Entry"
									? "Cash"
									: null,
						company: frm.doc.company,
					},
					callback: function (r) {
						if (r.message) {

							if (!$.isEmptyObject(r.message)) {
								update_jv_details(frm.doc, [r.message]);
							}
						}
					},
				});
			}
		}
	},

	from_template: function (frm) {
		if (frm.doc.from_template) {
			frappe.db.get_doc("Journal Entry Template", frm.doc.from_template).then((doc) => {
				frappe.model.clear_table(frm.doc, "accounts");
				frm.set_value({
					company: doc.company,
					voucher_type: doc.voucher_type,
					naming_series: doc.naming_series,
					is_opening: doc.is_opening,
					multi_currency: doc.multi_currency,
				});
				update_jv_details(frm.doc, doc.accounting_entries);
			});
		}
	},
});

function update_jv_details(doc, r) {
	$.each(r, function (i, d) {
		let row = frappe.model.add_child(doc, "Journal Entry Account", "accounts");
		frappe.model.set_value(row.doctype, row.name, "account", d.account);
	});
	refresh_field("accounts");
};

verp_staffing.accounts.JournalEntry = class JournalEntry extends frappe.ui.form.Controller {
	onload() {
		this.load_defaults();
		this.setup_queries();
	}

	onload_post_render() {
		this.frm.get_field("accounts").grid.set_multiple_add("account");
	}

	load_defaults() {
		if (this.frm.doc.__islocal) {
			let posting_date = this.frm.doc.posting_date;
			if (!this.frm.doc.amended_from)
				this.frm.set_value("posting_date", posting_date || frappe.datetime.get_today());
		}
	}

	setup_queries() {
		let me = this;

		this.frm.set_query("account", "accounts", function (doc, cdt, cdn) {
			return verp_staffing.journal_entry.account_query(me.frm);
		});

		me.frm.set_query("party_type", "accounts", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];

			return {
				query: "verp_staffing.accounts.doctype.party_type.party_type.get_party_type",
				filters: {
					account: row.account,
				},
			};
		});

		me.frm.set_query("reference_name", "accounts", function (doc, cdt, cdn) {
			let jvd = frappe.get_doc(cdt, cdn);

			if (jvd.reference_type === "Journal Entry") {
				frappe.model.validate_missing(jvd, "account");
				return {
					query: "verp_staffing.accounts.doctype.journal_entry.journal_entry.get_against_jv",
					filters: {
						account: jvd.account,
						party: jvd.party,
					},
				};
			}

			let out = {
				filters: [[jvd.reference_type, "docstatus", "=", 1]],
			};

			if (["Sales Invoice", "Purchase Invoice"].includes(jvd.reference_type)) {
				out.filters.push([jvd.reference_type, "outstanding_amount", "!=", 0]);

				frappe.model.validate_missing(jvd, "account");
				let party_account_field =
					jvd.reference_type === "Sales Invoice" ? "debit_to" : "credit_to";
				out.filters.push([jvd.reference_type, party_account_field, "=", jvd.account]);
			}

			if (["Sales Order", "Purchase Order"].includes(jvd.reference_type)) {
				frappe.model.validate_missing(jvd, "party_type");
				frappe.model.validate_missing(jvd, "party");

				out.filters.push([jvd.reference_type, "per_billed", "<", 100]);
			}

			if (jvd.party_type && jvd.party) {
				let party_field = "";
				if (jvd.reference_type.indexOf("Sales") === 0) {
					party_field = "customer";
				} else if (jvd.reference_type.indexOf("Purchase") === 0) {
					party_field = "supplier";
				}

				if (party_field) {
					out.filters.push([jvd.reference_type, party_field, "=", jvd.party]);
				}
			}

			return out;
		});
	}

	reference_name(doc, cdt, cdn) {
		let d = frappe.get_doc(cdt, cdn);

		if (d.reference_name) {
			if (d.reference_type === "Purchase Invoice" && !flt(d.debit)) {
				this.get_outstanding("Purchase Invoice", d.reference_name, doc.company, d);
			} else if (d.reference_type === "Sales Invoice" && !flt(d.credit)) {
				this.get_outstanding("Sales Invoice", d.reference_name, doc.company, d);
			} else if (d.reference_type === "Journal Entry" && !flt(d.credit) && !flt(d.debit)) {
				this.get_outstanding("Journal Entry", d.reference_name, doc.company, d);
			}
		}
	}

	get_outstanding(doctype, docname, company, child) {
		let args = {
			doctype: doctype,
			docname: docname,
			party: child.party,
			account: child.account,
			account_currency: child.account_currency,
			company: company,
			company_currency: this.frm.doc.company_currency,
		};

		return frappe.call({
			method: "verp_staffing.accounts.doctype.journal_entry.journal_entry.get_outstanding",
			args: { args: args },
			callback: function (r) {
				if (r.message) {
					$.each(r.message, function (field, value) {
						frappe.model.set_value(child.doctype, child.name, field, value);
					});
				}
			},
		});
	}

	accounts_add(frm, cdt, cdn) {
		if (!frm.doc.company) {
			show_company_warning(frm);
			return;
		}

		auto_balance(frm);
		calculate_totals(frm);
	}
};

cur_frm.script_manager.make(verp_staffing.accounts.JournalEntry);

cur_frm.cscript.update_totals = function (doc) {
	let frm = cur_frm; // bridge old → new
	calculate_totals(frm);
};

cur_frm.cscript.get_balance = function (doc) {
	let frm = cur_frm;
	let accounts = frm.doc.accounts || [];

	if (!accounts.length) {
		frappe.throw("Entries cannot be empty");
		return;
	}

	let company_currency = frm.doc.company_currency;

	let total_debit = 0;
	let total_credit = 0;

	accounts.forEach((row) => {
		total_debit += flt(row.debit || 0);
		total_credit += flt(row.credit || 0);
	});

	let diff = flt(total_debit - total_credit);

	if (diff !== 0) {
		let blank_row = null;

		for (let row of accounts) {
			if (!flt(row.debit) && !flt(row.credit)) {
				blank_row = row;
				break;
			}
		}

		if (!blank_row) {
			blank_row = frm.add_child("accounts");
		}

		let rate = flt(blank_row.exchange_rate) || 1;
		let account_currency = blank_row.account_currency || company_currency;

		if (diff > 0) {
			frappe.model.set_value(blank_row.doctype, blank_row.name, "credit", diff);
			frappe.model.set_value(blank_row.doctype, blank_row.name, "debit", 0);

			frappe.model.set_value(
				blank_row.doctype,
				blank_row.name,
				"credit_in_account_currency",
				diff / rate,
			);
			frappe.model.set_value(
				blank_row.doctype,
				blank_row.name,
				"debit_in_account_currency",
				0,
			);
		} else {
			let abs_diff = Math.abs(diff);

			frappe.model.set_value(blank_row.doctype, blank_row.name, "debit", abs_diff);
			frappe.model.set_value(blank_row.doctype, blank_row.name, "credit", 0);

			frappe.model.set_value(
				blank_row.doctype,
				blank_row.name,
				"debit_in_account_currency",
				abs_diff / rate,
			);
			frappe.model.set_value(
				blank_row.doctype,
				blank_row.name,
				"credit_in_account_currency",
				0,
			);
		}
	}

	calculate_totals(frm);

	frm.refresh_fields(["accounts", "total_debit", "total_credit", "difference"]);
};
cur_frm.cscript.validate = function (doc, cdt, cdn) {
	cur_frm.cscript.update_totals(doc);
};

function calculate_totals(frm) {
	let total_debit = 0;
	let total_credit = 0;

	(frm.doc.accounts || []).forEach((row) => {
		total_debit += flt(row.debit);
		total_credit += flt(row.credit);
	});

	let difference = total_debit - total_credit;

	frm.set_value("total_debit", total_debit);
	frm.set_value("total_credit", total_credit);
	frm.set_value("difference", difference);
}

function show_company_warning(frm) {
	frappe.show_alert(
		{
			message: "Select Company first",
			indicator: "orange",
		},
		3,
	);

	frm.scroll_to_field("company");
}

function open_outstanding_dialog(frm) {
	let based_on = frm.doc.write_off_based_on;

	let doctype = "";
	let party_field = "";

	if (!frm.doc.company) {
		show_company_warning(frm);
		return;
	}

	if (based_on === "Accounts Receivable") {
		doctype = "Sales Invoice";
		party_field = "customer";
	} else if (based_on === "Accounts Payable") {
		doctype = "Purchase Invoice";
		party_field = "supplier";
	} else {
		frappe.msgprint("Please select Write Off Based On");
		return;
	}

	let account_field = based_on === "Accounts Receivable" ? "debit_to" : "credit_to";

	let dialog = new frappe.ui.Dialog({
		title: "Outstanding Invoices",
		size: "large",
		fields: [
			{
				fieldname: "invoices",
				fieldtype: "Table",
				label: "Invoices",
				cannot_add_rows: true,
				cannot_delete_rows: true, 
				in_place_edit: false,
				fields: [
					{ fieldname: "name", label: "Invoice", fieldtype: "Data", in_list_view: 1 },
					{ fieldname: party_field, label: "Party", fieldtype: "Data", in_list_view: 1 },
					{
						fieldname: account_field,
						label: "Account",
						fieldtype: "Data",
						in_list_view: 1,
					},
					{
						fieldname: "posting_date",
						label: "Date",
						fieldtype: "Date",
						in_list_view: 1,
					},
					{
						fieldname: "outstanding_amount",
						label: "Outstanding",
						fieldtype: "Currency",
						in_list_view: 1,
					},
				],
			},
		],

		primary_action_label: "Select",
		primary_action() {
			let selected = dialog.fields_dict.invoices.grid.get_selected_children();

			if (!selected.length) {
				frappe.msgprint("Please select at least one invoice");
				return;
			}

			add_invoices_to_jv(frm, selected, based_on);
			dialog.hide();
		},
	});

	dialog.show();

	setTimeout(() => {
		let grid = dialog.fields_dict.invoices.grid;

		grid.wrapper.find(".grid-footer").hide();
		grid.wrapper.find(".grid-remove-rows").hide(); 
		grid.wrapper.find(".row-actions").hide();
	}, 100);

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: doctype,
			fields: ["name", party_field, "posting_date", "outstanding_amount", account_field],
			filters: {
				docstatus: 1,
				outstanding_amount: [">", 0],
				company: frm.doc.company,
			},
		},
		callback: function (r) {
			if (r.message) {
				dialog.fields_dict.invoices.df.data = r.message;
				dialog.fields_dict.invoices.grid.refresh();
			}
		},
	});
}

function add_invoices_to_jv(frm, invoices, based_on) {
	let total = 0;


	frm.clear_table("accounts");

	invoices.forEach((inv) => {
		let row = frm.add_child("accounts");

		let amt = flt(inv.outstanding_amount);
		total += amt;

		frappe.model.set_value(row.doctype, row.name, "account", inv.debit_to || inv.credit_to);
		frappe.model.set_value(row.doctype, row.name, "party", inv.customer || inv.supplier);

		if (based_on === "Accounts Receivable") {
			frappe.model.set_value(row.doctype, row.name, "party_type", "Customer");

			frappe.model.set_value(row.doctype, row.name, "credit_in_account_currency", amt);

			frappe.model.set_value(row.doctype, row.name, "reference_type", "Sales Invoice");
			frappe.model.set_value(row.doctype, row.name, "reference_name", inv.name);
		} else {
			frappe.model.set_value(row.doctype, row.name, "party_type", "Supplier");

			frappe.model.set_value(row.doctype, row.name, "debit_in_account_currency", amt);

			frappe.model.set_value(row.doctype, row.name, "reference_type", "Purchase Invoice");
			frappe.model.set_value(row.doctype, row.name, "reference_name", inv.name);
		}
	});

	let balancing_row = frm.add_child("accounts");

	if (based_on === "Accounts Receivable") {
		frappe.model.set_value(
			balancing_row.doctype,
			balancing_row.name,
			"debit_in_account_currency",
			total,
		);
	} else {
		frappe.model.set_value(
			balancing_row.doctype,
			balancing_row.name,
			"credit_in_account_currency",
			total,
		);
	}

	frm.refresh_field("accounts");

	frm.trigger("multi_currency");
	cur_frm.cscript.get_balance(frm.doc);
}

function get_company_currency(frm, callback) {
	if (!frm.doc.company) {
		return;
	}

	frappe.db.get_value("Company", frm.doc.company, "default_currency").then((r) => {
		if (r && r.message) {
			callback(r.message.default_currency);
		}
	});
}
function auto_balance(frm) {
	let accounts = frm.doc.accounts || [];

	if (accounts.length < 2) return;

	let total = 0;

	for (let i = 0; i < accounts.length - 1; i++) {
		total += flt(accounts[i].debit) - flt(accounts[i].credit);
	}

	let last = accounts[accounts.length - 1];

	// only auto-fill if empty
	if (!last.debit && !last.credit) {
		if (total > 0) {
			last.credit = total;
		} else {
			last.debit = -total;
		}
	}

	refresh_field("accounts");
}

frappe.ui.form.on("Journal Entry Account", {
	party: function (frm, cdt, cdn) {
		let d = frappe.get_doc(cdt, cdn);

		if (!d.account && d.party_type && d.party) {
			if (!frm.doc.company) {
				frappe.throw(__("Please select Company"));
			}

			frm.call({
				method: "verp_staffing.accounts.doctype.journal_entry.journal_entry.get_party_account_and_currency",
				args: {
					company: frm.doc.company,
					party_type: d.party_type,
					party: d.party,
				},
				callback: function (r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, "account", r.message.account);
						frappe.model.set_value(
							cdt,
							cdn,
							"account_currency",
							r.message.account_currency,
						);
					}
				},
			});
		}
	},

	account: function (frm, dt, dn) {
		if (!frm.doc.company) {
			show_company_warning(frm);
			frappe.model.set_value(dt, dn, "account", "");
			return;
		}

		frappe.model.set_value(dt, dn, "party_type", "");
		frappe.model.set_value(dt, dn, "party", "");
		verp_staffing.journal_entry.set_account_details(frm, dt, dn);
	},

	debit_in_account_currency: function (frm, cdt, cdn) {
		if (!frm.doc.company) {
			show_company_warning(frm);
			frappe.model.set_value(cdt, cdn, "debit_in_account_currency", 0);
			return;
		}
		verp_staffing.journal_entry.set_exchange_rate(frm, cdt, cdn);
	},

	credit_in_account_currency: function (frm, cdt, cdn) {
		if (!frm.doc.company) {
			show_company_warning(frm);
			frappe.model.set_value(cdt, cdn, "credit_in_account_currency", 0);
			return;
		}

		verp_staffing.journal_entry.set_exchange_rate(frm, cdt, cdn);
	},
	debit: function (frm, cdt, cdn) {
		auto_balance(frm);
	},

	credit: function (frm, cdt, cdn) {
		auto_balance(frm);
	},
	exchange_rate: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (!frm.doc.company) {
			show_company_warning(frm);
			frappe.model.set_value(cdt, cdn, "exchange_rate", 1);
			return;
		}
		if (row.account_currency === frm.doc.company_currency && row.exchange_rate != 1) {
			frappe.model.set_value(cdt, cdn, "exchange_rate", 1);
		}

		if (!row.exchange_rate || row.exchange_rate <= 0) {
			frappe.model.set_value(cdt, cdn, "exchange_rate", 1);
		}

		verp_staffing.journal_entry.set_debit_credit_in_company_currency(frm, cdt, cdn);
		auto_balance(frm);
	},
});

frappe.ui.form.on("Journal Entry Account", "accounts_remove", function (frm) {
	cur_frm.cscript.update_totals(frm.doc);
});

$.extend(verp_staffing.journal_entry, {
	toggle_fields_based_on_currency: function (frm) {
		let fields = ["currency_section", "account_currency", "exchange_rate", "debit", "credit"];

		let grid = frm.get_field("accounts").grid;
		if (grid) grid.set_column_disp(fields, frm.doc.multi_currency);

		// dynamic label
		let field_label_map = {
			debit_in_account_currency: "Debit",
			credit_in_account_currency: "Credit",
		};

		$.each(field_label_map, function (fieldname, label) {
			frm.fields_dict.accounts.grid.update_docfield_property(
				fieldname,
				"label",
				frm.doc.multi_currency ? label + " in Account Currency" : label,
			);
		});
	},

	set_debit_credit_in_company_currency: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		let rate = flt(row.exchange_rate) || 1;

		frappe.model.set_value(cdt, cdn, "debit", flt(row.debit_in_account_currency || 0) * rate);

		frappe.model.set_value(
			cdt,
			cdn,
			"credit",
			flt(row.credit_in_account_currency || 0) * rate,
		);

		calculate_totals(frm);
	},

	set_exchange_rate: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (row.account_currency === frm.doc.company_currency && row.exchange_rate != 1) {
			frappe.model.set_value(cdt, cdn, "exchange_rate", 1);
		}

		if (!row.exchange_rate || row.exchange_rate <= 0) {
			row.exchange_rate = 1;
		}

		verp_staffing.journal_entry.set_debit_credit_in_company_currency(frm, cdt, cdn);
	},

	quick_entry: function (frm) {
		let naming_series_options = frm.fields_dict.naming_series.df.options;
		let naming_series_default =
			frm.fields_dict.naming_series.df.default || naming_series_options.split("\n")[0];

		let dialog = new frappe.ui.Dialog({
			title: __("Quick Journal Entry"),
			fields: [
				{ fieldtype: "Currency", fieldname: "debit", label: __("Amount"), reqd: 1 },
				{
					fieldtype: "Link",
					fieldname: "debit_account",
					label: __("Debit Account"),
					reqd: 1,
					options: "Account",
					get_query: function () {
						return verp_staffing.journal_entry.account_query(frm);
					},
				},
				{
					fieldtype: "Link",
					fieldname: "credit_account",
					label: __("Credit Account"),
					reqd: 1,
					options: "Account",
					get_query: function () {
						return verp_staffing.journal_entry.account_query(frm);
					},
				},
				{
					fieldtype: "Date",
					fieldname: "posting_date",
					label: __("Date"),
					reqd: 1,
					default: frm.doc.posting_date,
				},
				{ fieldtype: "Small Text", fieldname: "user_remark", label: __("User Remark") },
				{
					fieldtype: "Select",
					fieldname: "naming_series",
					label: __("Series"),
					reqd: 1,
					options: naming_series_options,
					default: naming_series_default,
				},
			],
		});

		dialog.set_primary_action(__("Save"), function () {
			let btn = this;
			let values = dialog.get_values();

			frm.set_value("posting_date", values.posting_date);
			frm.set_value("user_remark", values.user_remark);
			frm.set_value("naming_series", values.naming_series);

			frm.clear_table("accounts");

			let debit_row = frm.fields_dict.accounts.grid.add_new_row();
			frappe.model.set_value(
				debit_row.doctype,
				debit_row.name,
				"account",
				values.debit_account,
			);
			frappe.model.set_value(
				debit_row.doctype,
				debit_row.name,
				"debit_in_account_currency",
				values.debit,
			);

			let credit_row = frm.fields_dict.accounts.grid.add_new_row();
			frappe.model.set_value(
				credit_row.doctype,
				credit_row.name,
				"account",
				values.credit_account,
			);
			frappe.model.set_value(
				credit_row.doctype,
				credit_row.name,
				"credit_in_account_currency",
				values.debit,
			);

			frm.save();

			dialog.hide();
		});

		dialog.show();
	},

	account_query: function (frm) {
		let filters = {
			is_group: 0,
		};

		if (frm.doc.company) {
			filters.company = frm.doc.company;
		}

		let company_currency = get_company_currency(frm);

		if (!frm.doc.multi_currency && frm.doc.company) {
			let company = frappe.get_doc(":Company", frm.doc.company);

			if (company) {
				$.extend(filters, {
					account_currency: ["in", [company_currency, null]],
				});
			}
		}

		return { filters: filters };
	},

	reverse_journal_entry: function () {
		frappe.model.open_mapped_doc({
			method: "verp_staffing.accounts.doctype.journal_entry.journal_entry.make_reverse_journal_entry",
			frm: cur_frm,
		});
	},
});

$.extend(verp_staffing.journal_entry, {
	set_account_details: function (frm, dt, dn) {
		let d = locals[dt][dn];
		if (d.account) {
			if (!frm.doc.company) frappe.throw(__("Please select Company first"));
			if (!frm.doc.posting_date) frappe.throw(__("Please select Posting Date first"));

			return frappe.call({
				method: "verp_staffing.accounts.doctype.journal_entry.journal_entry.get_account_details_and_party_type",
				args: {
					account: d.account,
					company: frm.doc.company,
				},
				callback: function (r) {
					if (r.message) {
						Object.assign(d, r.message);

						verp_staffing.journal_entry.set_debit_credit_in_company_currency(
							frm,
							dt,
							dn,
						);
						refresh_field("accounts");
					}
				},
			});
		}
	},
});
