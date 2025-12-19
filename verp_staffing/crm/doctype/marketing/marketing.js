// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing", {
    refresh(frm) {
        window.render_customer_related_html({
            frm: frm,
            html_field: "customer_details_html",
            source_doctype: "Lead Detail Form",
            customer: frm.doc.customer,
            fields: [
                "number_for_marketing",
            ],
            label_map: {
                number_for_marketing: "Lead number for marketing",
            }
        });
    },

    customer(frm) {
        frm.trigger("refresh");
    }
});

