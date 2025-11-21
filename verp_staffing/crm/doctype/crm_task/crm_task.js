// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("CRM Task", {
    refresh(frm) {
        if (!frappe.user.has_role("System Manager")) {
            frm.set_df_property("date", "read_only", 1);
            frm.set_df_property("is_completed", "read_only", frm.doc.assigned_to !== frappe.session.user? 1 : 0);
            frm.set_df_property("assigned_to", "read_only", 1);
        }
    },
});
