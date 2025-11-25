frappe.listview_settings["Lead"] = {
    refresh(listview) {
        let sidebar = $("body .layout-side-section");
        if (!sidebar.length) {
            console.log("Sidebar not found");
            return;
        }

        // HIDE ALL ITEMS FIRST
        sidebar.find(".group-by-field").hide();
        sidebar.find(".add-group-by").hide();
        sidebar.find(".save-filter-section").hide();
    }
};