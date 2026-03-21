// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Department", {
	refresh(frm) {
        render_roles_multiselect(frm);
        init_roles_multiselect(frm);
        set_service_query(frm);
    },
    onload(frm){
        set_service_query(frm);
    }
});

function set_service_query(frm) {
    frm.set_query("services", function () {
        return {
            query: "verp_staffing.settings.doctype.department.department.get_department_service_query",
            filters: {
                department: frm.doc.name
            }
        };
    });
}
function render_roles_multiselect(frm) {
    const html = `
    <div class="custom-multiselect-wrapper">
        <label class="multiselect-label">
            Select Department Roles
        </label>

        <div class="custom-multiselect">
            <div class="multiselect-content">
                <div class="selected-items"></div>
                <input 
                    type="text" 
                    class="multiselect-input" 
                    placeholder="Choose Roles"
                >
            </div>
            <div class="multiselect-dropdown hidden"></div>
        </div>
    </div>
`;


    const wrapper = frm.get_field("roles_html").$wrapper;
    if (!wrapper.find(".custom-multiselect").length) {
        wrapper.html(html);
    }
}


function init_roles_multiselect(frm) {
    const wrapper = frm.get_field("roles_html").$wrapper;
    const multiselect = wrapper.find(".custom-multiselect");

    if (multiselect.data("initialized")) return;
    multiselect.data("initialized", true);

    const chips = multiselect.find(".selected-items");
    const input = multiselect.find(".multiselect-input");
    const dropdown = multiselect.find(".multiselect-dropdown");

    let selected_roles = [];

    if (frm.doc.roles_json) {
        try {
            const parsed = JSON.parse(frm.doc.roles_json);
            selected_roles = Array.isArray(parsed) ? parsed : [];
        } catch {
            selected_roles = [];
        }
    }

    function render_chips() {
        chips.empty();

        selected_roles.forEach(role => {
            chips.append(`
                <span class="chip">
                    ${frappe.utils.escape_html(role)}
                    <span class="remove" data-role="${frappe.utils.escape_html(role)}">×</span>
                </span>
            `);
        });
    }

    function render_dropdown(filter = "") {
        dropdown.empty();

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Role",
                label: "Select Department Roles",
                fields: ["name"],
                filters: {
                    name: ["like", `%${filter}%`]
                },
                limit_page_length: 20
            },
            callback: r => {
                const roles = (r.message || [])
                    .map(d => d.name)
                    .filter(r => !selected_roles.includes(r));

                if (!roles.length) {
                    dropdown.addClass("hidden");
                    return;
                }

                roles.forEach(role => {
                    dropdown.append(
                        `<div class="item">${frappe.utils.escape_html(role)}</div>`
                    );
                });

                dropdown.removeClass("hidden");
            }
        });
    }

     function sync_value() {
        frm.set_value("roles_json", JSON.stringify(selected_roles));
    }

    input.on("focus", () => render_dropdown(""));
    input.on("keyup", () => render_dropdown(input.val()));

    multiselect.on("click", ".item", function () {
        const role = $(this).text();

        if (!selected_roles.includes(role)) {
            selected_roles.push(role);
            render_chips();
            sync_value();
        }

        dropdown.addClass("hidden");
        input.val("");
    });

    multiselect.on("click", ".remove", function (e) {
         e.stopPropagation();
        const role = $(this).data("role");
        selected_roles = selected_roles.filter(r => r !== role);
        render_chips();
        sync_value();
    });

    render_chips();

    $(document).on("click", e => {
        if (!multiselect.is(e.target) && !multiselect.has(e.target).length) {
            dropdown.addClass("hidden");
        }
    });
}
