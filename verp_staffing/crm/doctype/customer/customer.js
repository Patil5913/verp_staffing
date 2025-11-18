// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer", {
	refresh(frm) {
        if(!frm.doc.__islocal){
            frm.add_custom_button("Add Todo",()=>{
                frappe.new_doc("Todo",{
                    description:`Task for customer ${frm.doc.customer_name || frm.doc.name}`,
                    reference_type:"Customer",
                    reference_name:frm.doc.name
                })
            },__("Activities"))

            frm.add_custom_button("Add Event",()=>{
                frappe.new_doc("Event",{
                    subject:`Event for customer ${frm.doc.customer_name || frm.doc.name}`,
                    event_type:"Private",
                    reference_type:"Customer",
                    reference_name:frm.doc.name
                })
            },__("Activities"))

             // Add Note
            frm.add_custom_button("Add Note", () => {
                frappe.new_doc("Note", {
                    title: `Note about ${frm.doc.customer_name || frm.doc.name}`,
                    public: 0,
                    references: [{
                        reference_doctype: "Customer",
                        reference_name: frm.doc.name
                    }]
                });
            }, __("Activities"));
        }
	},
});
