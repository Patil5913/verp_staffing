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