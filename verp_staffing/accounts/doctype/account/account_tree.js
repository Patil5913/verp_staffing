// Create namespace if not already present
frappe.provide("frappe.treeview_settings");

/**
 * Get available options for a tree filter (like company)
 * based on user permissions OR fallback to all available records.
 */
const get_tree_options = async function (option) {
	let unscrub_option = frappe.model.unscrub(option);
	let user_permission = frappe.defaults.get_user_permissions();

	// Use permissions if valid
	if (
		user_permission &&
		user_permission[unscrub_option] &&
		user_permission[unscrub_option].length
	) {
		return user_permission[unscrub_option].map((perm) => perm.doc);
	}

	// Fallback: fetch from server
	let data = await frappe.db.get_list(unscrub_option, {
		fields: ["name"],
		limit: 1000,
	});

	return data.map((d) => d.name);
};
/**
 * Get default value for a tree filter
 * Ensures default is valid according to allowed options
 */
const get_tree_default = async function (option) {
	let options = await get_tree_options(option);
	// If system default exists in allowed options → use it
	if (options.includes(frappe.defaults.get_default(option))) {
		return frappe.defaults.get_default(option);
	} else {
		// Otherwise fallback to first available option
		return options[0];
	}
};

frappe.treeview_settings["Account"] = {
	breadcrumb: "Accounts",
	title: __("Chart of Accounts"),
	// Don't fetch root explicitly
	get_tree_root: false,
	// Top filter section in UI
	filters: [
		{
			fieldname: "company",
			fieldtype: "Select",
			options: "",
			label: __("Company"),
			// Trigger when company changes
			on_change: function () {
				var me = frappe.treeview_settings["Account"].treeview;
				var company = me.page.fields_dict.company.get_value();
				if (!company) {
					frappe.throw(__("Please set a Company"));
				}
				// Fetch root company
				frappe.call({
					method: "verp_staffing.accounts.doctype.account.account.get_root_company",
					args: {
						company: company,
					},
					callback: function (r) {
						if (r.message) {
							let root_company = r.message.length ? r.message[0] : "";
							me.page.fields_dict.root_company.set_value(root_company);

							frappe.db.get_value(
								"Company",
								{ name: company },
								"allow_account_creation_against_child_company",
								(r) => {
									frappe.flags.ignore_root_company_validation =
										r.allow_account_creation_against_child_company;
								},
							);
						}
					},
				});
			},
		},
		// Hidden field to store root company
		{
			fieldname: "root_company",
			fieldtype: "Data",
			label: __("Root Company"),
			hidden: true,
			disable_onchange: true,
		},
	],
	root_label: "Accounts",
	/**
	 * Runs after nodes are fetched
	 * Used here to attach balances to each account node
	 */
	get_tree_nodes: "verp_staffing.accounts.utils.utils.get_children",
	on_get_node: function (nodes, deep = false) {
		// If user can't read GL Entry → don't show balances
		if (frappe.boot.user.can_read.indexOf("GL Entry") == -1) return;

		let accounts = [];
		// Flatten data if deep fetch
		if (deep) {
			// in case of `get_all_nodes`
			accounts = nodes.reduce((acc, node) => [...acc, ...node.data], []);
		} else {
			accounts = nodes;
		}
		// Check setting if balances should be shown
		frappe.db.get_single_value("Accounts Settings", "show_balance_in_coa").then((value) => {
			if (value) {
				const get_balances = frappe.call({
					method: "verp_staffing.accounts.utils.utils.get_account_balances",
					args: {
						accounts: accounts,
						company: cur_tree.args.company,
					},
				});

				get_balances.then((r) => {
					if (!r.message || r.message.length == 0) return;

					for (let account of r.message) {
						const node = cur_tree.nodes && cur_tree.nodes[account.value];
						if (!node || node.is_root) continue;

						// show Dr if positive since balance is calculated as debit - credit else show Cr
						const balance = account.balance_in_account_currency || account.balance;
						const dr_or_cr = balance > 0 ? "Dr" : "Cr";
						const format = (value, currency) =>
							format_currency(Math.abs(value), currency);

						if (account.balance !== undefined) {
							node.parent && node.parent.find(".balance-area").remove();
							$(
								'<span class="balance-area pull-right">' +
									(account.balance_in_account_currency
										? format(
												account.balance_in_account_currency,
												account.account_currency,
											) + " / "
										: "") +
									format(account.balance, account.company_currency) +
									" " +
									dr_or_cr +
									"</span>",
							).insertBefore(node.$ul);
						}
					}
				});
			}
		});
	},
	// Backend method for adding node
	add_tree_node: "verp_staffing.accounts.utils.utils.add_ac",
	// Top menu actions
	menu_items: [
		{
			label: __("New Company"),
			action: function () {
				frappe.new_doc("Company", true);
			},
			condition: 'frappe.boot.user.can_create.indexOf("Company") !== -1',
		},
	],
	// Fields shown when creating new account
	fields: [
		{
			fieldtype: "Data",
			fieldname: "account_name",
			label: __("New Account Name"),
			reqd: true,
			description: __(
				"Name of new Account. Note: Please don't create accounts for Customers and Suppliers",
			),
		},
		{
			fieldtype: "Data",
			fieldname: "account_number",
			label: __("Account Number"),
			description: __(
				"Number of new Account, it will be included in the account name as a prefix",
			),
		},
		{
			fieldtype: "Check",
			fieldname: "is_group",
			label: __("Is Group"),
			description: __(
				"Further accounts can be made under Groups, but entries can be made against non-Groups",
			),
			onchange: function () {
				if (!this.value) {
					this.layout.set_value("root_type", "");
				}
			},
		},
		{
			fieldtype: "Select",
			fieldname: "root_type",
			label: __("Root Type"),
			options: ["Asset", "Liability", "Equity", "Income", "Expense"].join("\n"),
			depends_on: "eval:doc.is_group && !doc.parent_account",
		},
		{
			fieldtype: "Select",
			fieldname: "account_type",
			label: __("Account Type"),
			options: frappe
				.get_meta("Account")
				.fields.filter((d) => d.fieldname == "account_type")[0].options,
			description: __(
				"Optional. This setting will be used to filter in various transactions.",
			),
		},
		{
			fieldtype: "Float",
			fieldname: "tax_rate",
			label: __("Tax Rate"),
			depends_on: 'eval:doc.is_group==0&&doc.account_type=="Tax"',
		},
		{
			fieldtype: "Link",
			fieldname: "account_currency",
			label: __("Currency"),
			options: "Currency",
			description: __("Optional. Sets company's default currency, if not specified."),
		},
	],
	ignore_fields: ["parent_account"],
	onload: async function (treeview) {
		frappe.treeview_settings["Account"].treeview = {};
		$.extend(frappe.treeview_settings["Account"].treeview, treeview);

		let field = treeview.page.fields_dict.company;

		// Fetch options
		let options = await get_tree_options("company");

		// Set options properly (newline format)
		field.df.options = options.join("\n");
		field.refresh();

		let route_company = frappe.route_options?.company;
		// Set default safely
		if (route_company && options.includes(route_company)) {
			field.set_value(route_company);
		} else {
			// fallback to default
			let default_company = frappe.defaults.get_default("company");
			field.set_value(options.includes(default_company) ? default_company : options[0]);
		}

		treeview.page.add_inner_button(
			__("Company"),
			function () {
				frappe.new_doc("Company");
			},
			__("Create"),
		);
	},
	post_render: function (treeview) {
		frappe.treeview_settings["Account"].treeview["tree"] = treeview.tree;
		if (treeview.can_create) {
			treeview.page.set_primary_action(
				__("New"),
				function () {
					let root_company = treeview.page.fields_dict.root_company.get_value();
					if (root_company) {
						frappe.throw(__("Please add the account to root level Company - {0}"), [
							root_company,
						]);
					} else {
						treeview.new_node();
					}
				},
				"add",
			);
		}
	},
	toolbar: [
		{
			label: __("Add Child"),
			condition: function (node) {
				return (
					frappe.boot.user.can_create.indexOf("Account") !== -1 &&
					(!frappe.treeview_settings[
						"Account"
					].treeview.page.fields_dict.root_company.get_value() ||
						frappe.flags.ignore_root_company_validation) &&
					node.expandable &&
					!node.hide_add
				);
			},
			click: function () {
				var me = frappe.views.trees["Account"];
				me.new_node();
			},
			btnClass: "hidden-xs",
		},
		{
			condition: function (node) {
				return !node.root && frappe.boot.user.can_read.indexOf("GL Entry") !== -1;
			},
			label: __("View Ledger"),
			click: function (node, btn) {
				const account_name = node.value || node.label;
				frappe.route_options = {
					from_date: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
					to_date: frappe.datetime.get_today(),
					company:
						frappe.treeview_settings[
							"Account"
						].treeview.page.fields_dict.company.get_value(),
					account: account_name,
				};
				frappe.set_route("query-report", "General Ledger");
			},
			btnClass: "hidden-xs",
		},
	],
	extend_toolbar: true,
};
