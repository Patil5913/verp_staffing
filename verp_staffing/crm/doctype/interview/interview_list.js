let marketing_filter_initialized = false;

frappe.listview_settings["Interview"] = {
    refresh(listview) {
        const page = listview.page;
        if (!page) return;

        hide_list_controls(page);

        if (!page.customer_filter_btn_added) {
            page.customer_filter_btn_added = true;
            page.add_inner_button(__('Select Customer'), () => {
                open_marketing_customer_dialog(listview);
            });
        }

        if (!marketing_filter_initialized) {
            marketing_filter_initialized = true;
            frappe.after_ajax(() => {
                auto_apply_marketing_filter(listview);
            });
        }
    }
};

function hide_list_controls(page) {
    page.wrapper.find(
        '.filter-button, .filter-x-button, .menu-btn-group'
    ).hide();
}

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

    // filters may not be initialized yet
    const filters = Array.isArray(fa.filters) ? fa.filters : [];

    // Check if marketing_link filter already exists
    const already_applied = filters.some(f => {
        return f[1] === "marketing_link";
    });

    if (already_applied) return;

    frappe.call({
        method: "verp_staffing.crm.doctype.interview.interview.get_marketing_customer_options",
        callback(r) {
            const options = r.message || [];
            if (!options.length) return;

            const param = get_marketing_param();
            const value = param || options[0].value;

            if (!param) set_marketing_param(value);

            fa.add([
                ["Interview", "marketing_link", "=", value]
            ]);

            update_customer_label(listview.page, options, value);
        }
    });
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

    const selected = options.find(o => o.value === selected_value);

    if (!selected) {
        valueEl.text("—");
        pill.css("opacity", 0.6);
        return;
    }

    valueEl.text(selected.label);
    pill.css("opacity", 1);
}



function open_marketing_customer_dialog(listview) {
    const current_value = get_marketing_param();

    frappe.call({
        method: "verp_staffing.crm.doctype.interview.interview.get_marketing_customer_options",
        callback(r) {
            const options = r.message || [];
            if (!options.length) {
                frappe.msgprint("No customers assigned.");
                return;
            }

            const dialog = new frappe.ui.Dialog({
                title: "Filter Interviews by Customer",
                fields: [{
                    fieldtype: "Select",
                    fieldname: "marketing",
                    label: "Customer",
                    options: options.map(o => ({
                        label: o.label,
                        value: o.value
                    })),
                    default: current_value,
                    reqd: 1
                }],
                primary_action_label: "Apply",
                primary_action(values) {
                    dialog.hide();
                    set_marketing_param(values.marketing);
                    apply_marketing_filter(listview, values.marketing);
                    update_customer_label(listview.page, options, values.marketing);
                }
            });

            dialog.show();
        }
    });
}

function apply_marketing_filter(listview, value) {
    if (!value || !listview.filter_area) return;

    listview.filter_area.clear();
    listview.filter_area.add(
        "Interview",
        "marketing_link",
        "=",
        value
    );

}
