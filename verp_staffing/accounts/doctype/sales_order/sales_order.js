// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        console.log("frm.doc.agreement: ", frm.doc.agreement)
        if (frm.doc.agreement) {
            frm.add_custom_button("Download Agreement", function () {
                frappe.call({
                    method: "verp_staffing.crm.api.agreement.download_agreement",
                    args: {
                        agreement: frm.doc.agreement
                    },
                    callback(r) {
                        if (!r.message) {
                            frappe.msgprint("No agreement file found.");
                            return;
                        }

                        // Trigger download
                        window.open(r.message.file_url);
                    }
                });
            });
        } else {
            render_agreement_ui(frm);
        }
    }
});

//load agreement tab
function render_agreement_ui(frm) {
    const wrapper = frm.get_field("agreement_html").$wrapper;
    wrapper.empty();

    // Stop if Agreement already exists
    if (frm.doc.agreement) {
        wrapper.html(`<p style="color:red;">Agreement already created.</p>`);
        return;
    }

    wrapper.append(`
            <div id="agreement_container">
                <h3>Agreement Builder</h3>

                <label>Choose Template</label>
                <select id="ag_template" class="form-control"></select>

                <div id="ag_dynamic_form" style="margin-top: 20px;"></div>

                <button class="btn btn-primary" id="ag_preview" style="margin-top: 15px;">
                    Preview
                </button>

                <button class="btn btn-success" id="ag_submit" style="margin-left: 10px; margin-top: 15px;">
                    Save & Send
                </button>
            </div>
        `);
    load_templates(frm);
    bind_events(frm);
}

function load_templates(frm) {
    const select = frm.get_field("agreement_html").$wrapper.find("#ag_template");

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Pdf Agreement Template",
            filters: { is_active: 1 },
            fields: ["name", "title"]
        },
        callback(r) {
            select.append(`<option value="">Select</option>`);
            (r.message || []).forEach(t => {
                select.append(`<option value="${t.name}">${t.title || t.name}</option>`);
            });
        }
    });
}

function bind_events(frm) {
    const wrap = frm.get_field("agreement_html").$wrapper;

    // When template changes → load dynamic fields
    wrap.on("change", "#ag_template", function () {
        load_form_fields(frm);
    });

    // Preview Button
    wrap.on("click", "#ag_preview", function () {
        preview_inline(frm);
    });

    // Submit Button
    wrap.on("click", "#ag_submit", function () {
        submit_inline(frm);
    });
}

function load_form_fields(frm) {
    const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
    const form_div = frm.get_field("agreement_html").$wrapper.find("#ag_dynamic_form");

    if (!template) {
        form_div.empty();
        return;
    }

    frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Pdf Agreement Template", name: template },
        callback(r) {
            const tpl = r.message;
            console.log("tpl: ", tpl);

            const blocks = JSON.parse(tpl.fields_json || "[]");
            console.log("blocks: ", blocks);

            form_div.empty();

            blocks.forEach(b => {
                if (b.type == "Text" || b.type == "Number") {

                    form_div.append(`
                        <div style="margin-bottom: 10px;">
                                <label>${b.label || b.name}</label>
                                <input type="${b.type ?? "text"}" class="form-control ag-field"
                                data-field="${b.name}"
                                >
                                </div>
                                `);
                }
            });
        }
    });
}

function preview_inline(frm) {
    const wrap = frm.get_field("agreement_html").$wrapper;
    const template = wrap.find("#ag_template").val();

    if (!template) {
        frappe.msgprint("Choose a template first");
        return;
    }

    const values = {};
    wrap.find(".ag-field").each(function () {
        values[$(this).data("field")] = $(this).val();
    });

    frappe.call({
        method: "verp_staffing.crm.api.agreement.preview_agreement",
        args: {
            template_name: template,
            data: values
        },
        callback(r) {
            if (r.message && r.message.file_url) {
                window.open(r.message.file_url);
            }
        }
    });
}

function submit_inline(frm) {
    const wrap = frm.get_field("agreement_html").$wrapper;
    const template = wrap.find("#ag_template").val();

    if (!template) {
        frappe.msgprint("Choose a template first");
        return;
    }

    const values = {};
    wrap.find(".ag-field").each(function () {
        values[$(this).data("field")] = $(this).val();
    });

    frappe.call({
        method: "verp_staffing.crm.api.agreement.submit_and_generate",
        args: {
            sales_order: frm.doc.name,
            template,
            data: values
        },
        callback(r) {
            frappe.msgprint("Agreement saved & sent.");
            frm.reload_doc();
        }
    });
}