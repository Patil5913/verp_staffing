frappe.listview_settings["Lead"] = {
    refresh(listview) {
        let sidebar = $("body .layout-side-section");
        if (!sidebar.length) {
            return;
        }

        // HIDE ALL ITEMS FIRST
        sidebar.find(".group-by-field").hide();
        sidebar.find(".add-group-by").hide();
        sidebar.find(".save-filter-section").hide();
    },
    get_indicator(doc) {
        const map = {
            "Won": "green",
            "Interested": "blue",
            "Lead": "gray",
            "Lost": "red"
        };

        let color = map[doc.status] || "gray";

        return [__(doc.status), color, `status,=,${doc.status}`];
    }
};