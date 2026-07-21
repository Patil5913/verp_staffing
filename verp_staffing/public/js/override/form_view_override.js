(() => {
	if (frappe.__verp_form_override) return;
	frappe.__verp_form_override = true;
	const original_refresh = frappe.ui.form.Form.prototype.refresh;

	frappe.ui.form.Form.prototype.refresh = async function (...args) {
		const result = await original_refresh.apply(this, args);

		add_delete_button(this);

		return result;
	};

	function add_delete_button(frm) {
		if (frm.is_new()) return;
		if (frm.meta.issingle) return;
		if (!frm.has_perm("delete")) return;

		if (frm.page.wrapper.find(".verp-delete-btn").length) return;

		const btn = $(`
		<button class="btn btn-danger btn-sm verp-delete-btn">
			${__("Delete")}
		</button>
	`);

		btn.on("click", () => {
			frappe.model.delete_doc(frm.doctype, frm.doc.name);
		});

		const primary = frm.page.wrapper.find(".page-actions .btn-primary");

		if (primary.length) {
			primary.after(btn);
		} else {
			frm.page.wrapper.find(".page-actions").prepend(btn);
		}
	}
})();
