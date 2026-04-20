// verp_staffing/public/js/utils.js

window.verp_staffing = window.verp_staffing || {};
verp_staffing.purchase = verp_staffing.purchase || {};

verp_staffing.purchase.make_bank_account = function (doctype, docname) {
	return frappe.call({
		method: "verp_staffing.accounts.doctype.bank_account.bank_account.make_bank_account",
		args: {
			doctype: doctype,
			docname: docname,
		},
		callback: function (r) {
			if (r.message) {
				let doc = frappe.model.sync(r.message)[0];
				frappe.set_route("Form", doc.doctype, doc.name);
			}
		},
	});
};