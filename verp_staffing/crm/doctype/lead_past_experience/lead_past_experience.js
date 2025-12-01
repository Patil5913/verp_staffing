// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("lead_past_experience", {
    start_date(frm, cdt, cdn) {
        validate_mm_yyyy_format(cdt, cdn, "start_date");
    },
    end_date(frm, cdt, cdn) {
        validate_mm_yyyy_format(cdt, cdn, "end_date");
    },
    description(frm) {
        validate_live_description(frm);
    }
});

function validate_mm_yyyy_format(cdt, cdn, fieldname) {
    let row = locals[cdt][cdn];
    let value = row[fieldname];
    if (!value) return;

    let pattern = /^(0[1-9]|1[0-2])-\d{4}$/;

    if (!pattern.test(value)) {
        frappe.msgprint({
            title: __("Invalid Format"),
            message: __(fieldname.replace("_", " ") + " must be in MM-YYYY format (example: 02-2025)"),
            indicator: "red"
        });

        frappe.model.set_value(cdt, cdn, fieldname, "");
    }
}

function validate_live_description(frm) {
    let desc = frm.doc.description || "";

    // Remove all whitespace
    let text_without_spaces = desc.replace(/\s+/g, '');

    // Show live message below the field
    let message = `Characters (excluding spaces): ${text_without_spaces.length} / 800`;

    frm.fields_dict["description"].$wrapper
        .find(".description-counter")
        .remove(); // remove old counter

    frm.fields_dict["description"].$wrapper
        .append(`<div class="description-counter" style="margin-top:5px; color:${
            text_without_spaces.length < 800 ? "red" : "green"
        };">${message}</div>`);
}