frappe.listview_settings["Onboardings"] = {
    onload(listview) {

        // Hide "Add" (New) button
        listview.page.btn_primary.hide();

        // Also hide sidebar "Add" button if present
        const interval = setInterval(() => {
            const btn = document.querySelector('.btn-new-doc');
            if (btn) {
                btn.style.display = "none";
                clearInterval(interval);
            }
        }, 300);

    }
};