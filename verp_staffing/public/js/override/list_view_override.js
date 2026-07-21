(() => {
	if (frappe.__verp_list_override) return;
	frappe.__verp_list_override = true;

	const original_refresh = frappe.views.ListView.prototype.refresh;

	frappe.views.ListView.prototype.refresh = async function (...args) {
		const result = await original_refresh.apply(this, args);

		add_delete_button(this);

		return result;
	};

	function add_delete_button(listview) {
		if (!frappe.model.can_delete(listview.doctype)) return;

		const page_actions = listview.page.wrapper.find(".page-actions");

		let btn = page_actions.find(".verp-delete-btn");

		if (!btn.length) {
			btn = $(`
			<button class="btn btn-danger btn-sm verp-delete-btn">
				${__("Delete")}
			</button>
		`);

			btn.on("click", () => delete_selected(listview));

			page_actions.prepend(btn);
		}
		btn.toggle(listview.get_checked_items().length > 0);
	}

	const original = frappe.views.ListView.prototype.toggle_actions_menu_button;
	frappe.views.ListView.prototype.toggle_actions_menu_button = function (...args) {
		// const result = original.apply(this, args);

		return show_delete_button(this);
	};

	function show_delete_button(listview) {
		const page_actions = listview.page.wrapper.find(".page-actions");

		let btn = page_actions.find(".verp-delete-btn");
		btn.toggle(listview.get_checked_items().length > 0);
	}

	function delete_selected(listview) {
		const docs = listview.get_checked_items();

		if (!docs.length) return;

		frappe.confirm(__("Delete {0} selected document(s)?", [docs.length]), () => {
			frappe.call({
				method: "frappe.desk.reportview.delete_items",
				args: {
					doctype: listview.doctype,
					items: docs.map((d) => d.name),
				},
				callback: () => listview.refresh(),
			});
		});
	}
})();
