console.log("jjsssss");


frappe.listview_settings['interview'] = {
    onload: function(listview) {
        // Check if the current route is NOT already the 'interview' Kanban board
        const route = frappe.get_route();
        console.log("route", route);
        
        if (route[2] !== 'kanban' || route[3] !== 'interview') {
            frappe.set_route('List', 'interview', 'kanban', 'interview');
        }
    },
    
};
