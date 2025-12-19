frappe.provide("frappe.listview_settings");

console.log("hyyy");


frappe.listview_settings["Interview"] = {
    onload(listview) {
        // Force Kanban view
        if (listview.view_name !== "Kanban") {
            console.log("fasfas");
            
            listview.switch_view("Kanban");
        }

        // Hide view switcher completely
        setTimeout(() => {
            const viewSwitcher = document.querySelector(".view-switcher");
            console.log("viewSwitcher",viewSwitcher);

            if (viewSwitcher) {
                viewSwitcher.style.display = "none";
            }
        }, 300);
    }
};
