frappe.ui.form.on("CRM Task", {
    refresh(frm) {
        if (!frappe.user.has_role("System Manager") && frm.doc.assigned_to !== frappe.session.user && frm.doc.owner  !== frappe.session.user) {
            frm.set_df_property("date", "read_only", 1);
            frm.set_df_property("category", "read_only", 1);
            frm.set_df_property("summary", "read_only", 1);
            frm.set_df_property("description", "read_only", 1);
            frm.set_df_property("assigned_to", "read_only", 1);
        }
    },
});
