// verp_staffing/public/js/utils.js

window.verp_staffing = window.verp_staffing || {};
verp_staffing.purchase = verp_staffing.purchase || {};

// Short name of an IANA time zone ("EDT", "IST"); the zone itself when the browser has none.
verp_staffing.zone_abbr = function (zone) {
	if (!zone) return "";
	try {
		const part = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "short" })
			.formatToParts(new Date())
			.find((p) => p.type === "timeZoneName");
		return part ? part.value : zone;
	} catch (e) {
		return zone;
	}
};

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