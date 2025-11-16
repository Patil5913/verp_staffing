// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Opportunity", {
    setup: function (frm) {
        frm.set_query("opportunity_from", function () {
            return {
                filters: {
                    name: ["in", ["Lead", "Customer"]]
                },
            };
        });
    },

    opportunity_from: function (frm) {
        if (frm.doc.opportunity_from) {
            frm.set_df_property("party_name", "label", frm.doc.opportunity_from);
        }
    },

    refresh: function (frm) {
        frm.trigger("opportunity_from");
    },

    party_name: function (frm) {
        frm.trigger("fetch_source_details");
    },

    fetch_source_details: function (frm) {
        if (frm.doc.party_name && frm.doc.opportunity_from) {
            let doctype = frm.doc.opportunity_from;
            let docname = frm.doc.party_name;

            // Define which fields we want to fetch
            let lead_fields = ["source"];
            let customer_fields = ["source"];

            let fields_to_fetch = doctype === "Lead" ? lead_fields : customer_fields;

            frappe.db.get_value(doctype, docname, fields_to_fetch, function (r) {
                if (r) {
                    if (r.source) {
                        frm.set_value("source", r.source);
                    }
                }
            });
        }
    },

    validate: function (frm) {
        if (frm.doc.opportunity_from === "Lead" && !frm.doc.party_name) {
            frappe.msgprint(__("Please select a Lead."));
            frappe.validated = false;
        } else if (frm.doc.opportunity_from === "Customer" && !frm.doc.party_name) {
            frappe.msgprint(__("Please select a Customer."));
            frappe.validated = false;
        }
    }

});
