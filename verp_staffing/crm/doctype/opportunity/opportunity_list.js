frappe.listview_settings['Opportunity'] = {
    onload(listview) {
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

    refresh: function (listview) {
        let sidebar = $("body .layout-side-section");
        if (!sidebar.length) {
            console.log("Sidebar not found");
            return;
        }

        // HIDE ALL ITEMS FIRST
        sidebar.find(".group-by-field").hide();
        sidebar.find(".add-group-by").hide();
        sidebar.find(".save-filter-section").hide();

        setTimeout(() => {

            let primary_btn = listview.page.wrapper
                .find('.page-actions .btn-primary');

            if (primary_btn.length) {

                primary_btn.text("+ Add Opportunity");

                primary_btn.off("click").on("click", function (e) {
                    e.preventDefault();
                    e.stopPropagation();

                    open_custom_dialog();
                });
            }

        }, 50);
    },

    get_indicator: function (doc) {
        if (doc.status === "Converted") {
            return [__("Converted"), "green", "status,=,Converted"];
        }
        if (doc.status === "Lost") {
            return [__("Lost"), "red", "status,=,Lost"];
        }
        if (doc.status === "Replied") {
            return [__("Replied"), "blue", "status,=,Replied"];
        }
        if (doc.status === "Open") {
            return [__("Open"), "orange", "status,=,Open"];
        }

        // default
        return [__(doc.status), "gray", `status,=,${doc.status}`];
    }
};

function open_custom_dialog() {

    let dialog = new frappe.ui.Dialog({
        title: "Create Opportunity",

        fields: [
            {
                fieldname: "name1",
                fieldtype: "Data",
                label: "Opportunity Name",
                reqd: 1
            },
            {
                fieldname: "opportunity_from",
                fieldtype: "Link",
                label: "Opportunity From",
                options: "DocType",
                get_query: function () {
                    return {
                        filters: {
                            name: ["in", ["Lead", "Customer"]]
                        }
                    };
                },
                onchange: function () {

                    let source = dialog.get_value("opportunity_from");

                    if (source) {
                        // 🔥 Update Party label dynamically
                        dialog.set_df_property("party_name", "label", source);

                        // Refresh field UI
                        dialog.refresh_field("party_name");

                        // Clear party_name when source changes
                        dialog.set_value("party_name", "");
                    }
                }
            },
            {
                fieldname: "party_name",
                fieldtype: "Dynamic Link",
                label: "Party",
                options: "opportunity_from",
                onchange: function () {

                    let source_doctype = dialog.get_value("opportunity_from");
                    let source_name = dialog.get_value("party_name");

                    if (source_doctype && source_name) {

                        let fetch_field =
                            source_doctype === "Lead" ? "name1" : "title";

                        frappe.db.get_value(
                            source_doctype,
                            source_name,
                            fetch_field
                        ).then((r) => {

                            if (r && r.message) {
                                let base_name = r.message[fetch_field];
                                dialog.set_value(
                                    "name1",
                                    base_name ? base_name.trim() : ""
                                );
                            }
                        });
                    }
                }
            }
        ],

        primary_action_label: "Save",

        primary_action(values) {
            frappe.call({
                method: "frappe.client.insert",
                args: {
                    doc: {
                        doctype: "Opportunity",
                        name1: values.name1,
                        opportunity_from: values.opportunity_from,
                        party_name: values.party_name
                    }
                },
                callback: function (r) {
                    if (!r.exc) {
                        dialog.hide();
                        frappe.set_route("Form", "Opportunity", r.message.name);
                    }
                }
            });
        },

        secondary_action_label: "Edit Full Form",
        secondary_action: function () {
            dialog.hide();
            frappe.new_doc("Opportunity");
        }
    });

    dialog.show();

    // 🔥 Move "Edit Full Form" to left side
    setTimeout(() => {
        let footer = dialog.$wrapper.find('.modal-footer');

        let secondary_btn = footer.find('.btn-secondary');
        secondary_btn.prependTo(footer);   // move to beginning

        footer.css({
            display: "flex",
            justifyContent: "space-between"
        });

    }, 10);
}
