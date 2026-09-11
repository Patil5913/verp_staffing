// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Account", {
	setup: function (frm) {
		frm.add_fetch("parent_account", "report_type", "report_type");
		frm.add_fetch("parent_account", "root_type", "root_type");
	},
	onload: function (frm) {
		frm.set_query("parent_account", function (doc) {
			return {
				filters: {
					is_group: 1,
					company: doc.company,
				},
			};
		});
	},
	refresh(frm) {
		frappe.breadcrumbs.clear();

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Accounting",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();
		frm.toggle_display("account_name", frm.is_new());

		frm.toggle_enable(["is_group", "company"], frm.is_new());
		frm.toggle_enable("account_number", frm.is_new() && frm.doc.account_type === "Bank");

		if (!frm.is_new()) {
			if (!frm.doc.parent_account) {
				frm.set_read_only();
				frm.set_intro(__("This is a root account and cannot be edited."));
			} else {
				frm.set_intro(null);
				frm.trigger("account_type");
				frm.trigger("add_toolbar_buttons");
			}
			
		}
	},

	account_type: function (frm) {
		frm.toggle_enable("account_number", frm.is_new() && frm.doc.account_type === "Bank");
	},
	add_toolbar_buttons: function (frm) {
		frm.add_custom_button(
			__("Chart of Accounts"),
			() => {
				frappe.set_route("Tree", "Account");
			},
			__("View"),
		);

		if (frm.doc.is_group == 1) {
			frm.add_custom_button(
				__("Convert to Non-Group"),
				function () {
					return frappe.call({
						doc: frm.doc,
						method: "convert_group_to_ledger",
						callback: function () {
							frm.refresh();
						},
					});
				},
				__("Actions"),
			);
		} else if (
			cint(frm.doc.is_group) == 0 &&
			frappe.boot.user.can_read.indexOf("GL Entry") !== -1
		) {
			frm.add_custom_button(
				__("General Ledger"),
				function () {
					frappe.route_options = {
						account: frm.doc.name,
						company: frm.doc.company,
					};
					frappe.set_route("query-report", "General Ledger");
				},
				__("View"),
			);
		}
	},
});
