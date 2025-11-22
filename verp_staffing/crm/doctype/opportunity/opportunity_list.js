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
        // Remove side section and menu button group in list view
        $(".layout-side-section").remove();
        $(".menu-btn-group").remove();
    }
};
