frappe.listview_settings['Lead'] = {
    refresh: function (listview) {
        // Remove side section and menu button group in list view
        $(".layout-side-section").remove();
        $(".menu-btn-group").remove();
    },
};