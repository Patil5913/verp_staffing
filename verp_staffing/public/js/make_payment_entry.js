frappe.provide("verp_staffing.payment_utils");


verp_staffing.payment_utils.open_payment_entry = function (frm) {
	if (flt(frm.doc.outstanding_amount) <= 0) {
		frappe.msgprint(__("Outstanding amount is already zero."));
		return;
	}

	frappe.model.open_mapped_doc({
		method:
			"verp_staffing.accounts.doctype.payment_entry.payment_entry.make_payment_entry",
		frm: frm,
	});
};


verp_staffing.payment_utils.add_payment_button = function (frm) {
	if (frm.doc.docstatus !== 1) return;
	if (flt(frm.doc.outstanding_amount) <= 0) return;

	frm.add_custom_button(
		__("Payment Entry"),
		function () {
			verp_staffing.payment_utils.open_payment_entry(frm);
		},
		__("Create"),
	);
};