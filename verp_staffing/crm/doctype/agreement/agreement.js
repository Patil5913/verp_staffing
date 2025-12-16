// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Agreement", {
    refresh(frm) {
        frm.add_custom_button("Download Agreement", function () {
            frappe.call({
                method: "verp_staffing.crm.api.agreement.download_agreement",
                args: {
                    agreement: frm.doc.name
                },
                callback(r) {
                    if (!r.message) {
                        frappe.msgprint("No agreement file found.");
                        return;
                    }

                    // Trigger download
                    window.open(r.message.file_url);
                }
            });
        });

    },
});
