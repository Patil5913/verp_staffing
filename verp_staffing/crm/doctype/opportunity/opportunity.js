// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Opportunity", {
    onload(frm) {
        if (frm.is_new()) {
            frm.set_value("sales_stage", "Prospecting")
        }

        const roles = frappe.user_roles;
        const user = frappe.session.user;
        if (user != "Administrator") {
            // Only apply to Lead Employee
            if (
                roles.includes("Lead Employee") ||
                roles.includes("Lead Manager") ||
                roles.includes("Lead Master Manager")
            ) {
                frappe.msgprint("You are not allowed to access Opportunity list.");
                frappe.set_route("desk");
            }
        }
    },

    refresh(frm) {
        frm.trigger("opportunity_from");

        frm.add_custom_button(__("Create Customer"), function () {
            open_create_customer_dialog(frm);
        }, __("Create"))

        if (!frm.doc.opportunity_owner) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Employee",
                    filters: { user: frappe.session.user },
                    fieldname: "name"
                },
                callback: function (r) {
                    if (r.message && r.message.name) {
                        frm.set_value("opportunity_owner", r.message.name);
                    }
                }
            });
        }

        const roles = frappe.user_roles

        if (roles.includes("Extra Menu Item Show")) {
            /* ----------------------------------------------------
               GENERIC REUSABLE HIDE FUNCTION
            ---------------------------------------------------- */
            const hideElements = ({ selectors = [], keywordSelectors = [], keywords = [] }) => {
                // Hide specific selectors
                selectors.forEach(sel => {
                    const el = document.querySelector(sel);
                    if (el) el.style.display = "none";
                });
                // Hide based on keywords
                keywordSelectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        const text = el.innerText?.trim();
                        if (text && keywords.some(k => text.includes(k))) {
                            el.style.display = "none";

                            // Hide li wrapper if exists (for dropdown)
                            const li = el.closest("li");
                            if (li) li.style.display = "none";
                        }
                    });
                });
            };

            /* ----------------------------------------------------
               MENU CLEANUP
            ---------------------------------------------------- */
            const MENU_HIDE = ["Links", "Duplicate", "Copy to Clipboard"];

            const cleanMenu = () => {
                // Frappe API removal
                MENU_HIDE.forEach(label => {
                    try { frm.page.remove_menu_item(label); } catch { }
                });
                // DOM cleanup using reusable function
                hideElements({
                    keywordSelectors: [".dropdown-menu .dropdown-item"],
                    keywords: MENU_HIDE
                });
            };

            // Re-clean when dropdown opens
            $(frm.page.wrapper).on("shown.bs.dropdown", cleanMenu);

            /* ----------------------------------------------------
               SIDEBAR CLEANUP
            ---------------------------------------------------- */
            const SIDEBAR_KEYWORDS = ["Assigned", "Share"];

            const cleanSidebar = () => {
                hideElements({
                    selectors: [
                        ".form-sidebar .assigned-to",
                        ".form-sidebar .btn-share",
                        ".form-sidebar .shared-with"
                    ],
                    keywordSelectors: [
                        ".form-sidebar *"
                    ],
                    keywords: SIDEBAR_KEYWORDS
                });
            };

            /* ----------------------------------------------------
               RUN CLEANUP ONCE + SINGLE RETRY TIMER
            ---------------------------------------------------- */
            const runCleanup = () => {
                cleanMenu();
                cleanSidebar();
            };

            // Run immediately
            runCleanup();

            // One timer for everything (menu + sidebar)
            let attempts = 0;
            const timer = setInterval(() => {
                runCleanup();
                if (attempts++ > 12) clearInterval(timer);
            }, 200);
        }
    },

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
    },
});

function open_create_customer_dialog(frm) {
    // check if document is saved
    if (frm.is_dirty()) {
        frappe.msgprint({
            title: __('Error'),
            message: __('Please save the Opportunity before creating a Customer.'),
            indicator: 'red'
        });
        return;
    }

    // check if opportunity already saved as Customer
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Customer",
            filters: { opportunity: frm.doc.name },
            limit_page_length: 1
        },
        callback: function (r) {
            if (r.message && r.message.length > 0) {
                frappe.msgprint({
                    title: __('Error'),
                    message: __('A Customer already exists for this Opportunity.'),
                    indicator: 'red'
                });
            } else {
                // Open a dialog to create Customer
                const dialog = new frappe.ui.Dialog({
                    title: __('Create Customer from Opportunity'),
                    primary_action_label: __('Create'),
                    primary_action() {
                        dialog.hide();
                        create_customer_from_opportunity(frm);
                    }
                });
                dialog.show();
            }
        }
    })
}

function create_customer_from_opportunity(frm) {
    const customer_doc = {
        doctype: 'Customer',
        opportunity: frm.doc.name,
    };

    frappe.call({
        method: 'frappe.client.insert',
        args: {
            doc: customer_doc
        },
        callback: function (r) {
            if (!r.exc && r.message) {
                frappe.msgprint({
                    title: __('Success'),
                    message: __('Customer {0} created successfully.', [r.message.name]),
                    indicator: 'green'
                });
                // redirect to customer form
                frappe.set_route('Form', 'Customer', r.message.name);
            }
        },
        error: function (err) {
            frappe.msgprint({
                title: __('Error'),
                message: err && err.exc ? err.exc : __('Failed to create Customer'),
                indicator: 'red'
            })
        }
    })
}

