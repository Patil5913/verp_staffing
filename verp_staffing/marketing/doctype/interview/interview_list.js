let _marketing_applied_value = null;
let _marketing_is_setting = false;

frappe.listview_settings["Interview"] = {
	refresh(listview) {
		const page = listview.page;
		if (!page) return;

		setTimeout(() => {
			page.wrapper.find(".add-new-column").hide();

			// Hide "Select Kanban" button
			page.inner_toolbar.find("button").each(function () {
				if ($(this).text().includes("Select Kanban")) {
					$(this).parent().hide();
				}
			});
		}, 50);

		setTimeout(() => {
			page.wrapper.find(".add-new-column").hide();
		}, 50);

		if (!page.customer_filter_btn_added) {
			page.customer_filter_btn_added = true;
			page.add_inner_button(__("Select Customer"), () => {
				open_marketing_customer_dialog(listview);
			});
		}

		// ✅ Block if we ourselves triggered this refresh
		if (_marketing_is_setting) return;

		const param = get_marketing_param();

		// ✅ Block if this value was already applied — don't re-apply
		if (_marketing_applied_value === param && param) return;

		auto_apply_marketing_filter(listview);
	},
};

function get_marketing_param() {
	return new URLSearchParams(window.location.search).get("marketing_link");
}

function set_marketing_param(value) {
	const url = new URL(window.location.href);
	url.searchParams.set("marketing_link", value);
	window.history.replaceState({}, "", url);
}

function auto_apply_marketing_filter(listview) {
	const fa = listview.filter_area;
	if (!fa) return;

	frappe.call({
		method: "verp_staffing.marketing.doctype.interview.interview.get_marketing_customer_options",
		callback(r) {
			const options = r.message || [];
			if (!options.length) {
				const body = listview.page?.body;
				if (body) {
					body.html(`
                        <div class="text-muted text-center mt-5">
                            You are not assigned to any customer.
                        </div>
                    `);
				}
				return;
			}

			const param = get_marketing_param();
			const value = param || options[0].value;
			if (!param) set_marketing_param(value);

			// ✅ If already applied this exact value — skip entirely
			if (_marketing_applied_value === value) {
				update_customer_label(listview.page, options, value);
				return;
			}

			// ✅ Set guard so the refresh caused by filter change is ignored
			_marketing_is_setting = true;
			_marketing_applied_value = value;

			set_filter_without_loop(listview, value);
			update_customer_label(listview.page, options, value);

			// ✅ Release guard after Frappe settles
			setTimeout(() => {
				_marketing_is_setting = false;
			}, 1000);
		},
	});
}

function set_filter_without_loop(listview, value) {
	// ✅ Directly manipulate filter state without triggering refresh chain
	try {
		const existing = listview.filter_area.filter_list.filters || [];

		// Remove old marketing_link filter if present
		const without_marketing = existing.filter((f) => f.fieldname !== "marketing_link");

		// Use listview's internal method that doesn't fire refresh
		listview.filter_area.filter_list.filters = without_marketing;

		// Now add cleanly
		listview.filter_area.add([["Interview", "marketing_link", "=", value]]);
	} catch (e) {
		// Fallback
		listview.filter_area.clear();
		listview.filter_area.add([["Interview", "marketing_link", "=", value]]);
	}
}

function ensure_customer_label(page) {
	if (page.customer_label) return page.customer_label;

	const label = $(`
        <div class="marketing-customer-pill"
            style="
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 4px 10px;
                margin-right: 8px;
                border-radius: 10px;
                background: #ffffffff;
                border: 1px solid #9ea3acff;
                font-size: 15px;
                white-space: nowrap;
            ">
                <span style="color:#5d6472ff; font-weight:500;">
                    Customer:
                </span>
                <span class="marketing-customer-value"
                    style="color:#111827; font-weight:600;">
                    —
                </span>
        </div>
    `);

	page.inner_toolbar.prepend(label);
	page.customer_label = label;
	return label;
}

function update_customer_label(page, options, selected_value) {
	const pill = ensure_customer_label(page);
	const valueEl = pill.find(".marketing-customer-value");
	const selected = options.find((o) => o.value === selected_value);

	if (!selected) {
		valueEl.text("—");
		pill.css("opacity", 0.6);
		return;
	}

	valueEl.text(selected.label ? selected.label : selected.value);
	pill.css("opacity", 1);
}

function open_marketing_customer_dialog(listview) {
	const current_value = get_marketing_param();

	frappe.call({
		method: "verp_staffing.marketing.doctype.interview.interview.get_marketing_customer_options",
		callback(r) {
			const options = r.message || [];
			if (!options.length) {
				frappe.msgprint("No customers assigned.");
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: "Filter Interviews by Customer",
				fields: [
					{
						fieldtype: "Select",
						fieldname: "marketing",
						label: "Customer",
						options: options.map((o) => ({ label: o.label, value: o.value })),
						default: current_value,
						reqd: 1,
					},
				],
				primary_action_label: "Apply",
				primary_action(values) {
					dialog.hide();

					// ✅ Reset applied value so filter re-applies with new value
					_marketing_applied_value = null;

					set_marketing_param(values.marketing);
					apply_marketing_filter(listview, values.marketing);
					update_customer_label(listview.page, options, values.marketing);
				},
			});

			dialog.show();
		},
	});
}

function apply_marketing_filter(listview, value) {
	if (!value || !listview.filter_area) return;

	_marketing_is_setting = true;
	_marketing_applied_value = value;

	listview.filter_area.clear();
	listview.filter_area.add("Interview", "marketing_link", "=", value);

	setTimeout(() => {
		_marketing_is_setting = false;
	}, 1000);
}
