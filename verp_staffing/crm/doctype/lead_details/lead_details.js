// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead Details", {
	refresh(frm) {
        frm.toggle_enable('reference_table', false);
	},

    surname: function(frm) { frm.trigger('update_title'); },
    first_name: function(frm) { frm.trigger('update_title'); },
    fathers_name: function(frm) { frm.trigger('update_title'); },

    update_title: function(frm) {
        let full_name = [
            frm.doc.surname, 
            frm.doc.first_name, 
            frm.doc.fathers_name
        ].filter(Boolean).join(" ");
        
        // Update a 'title' field if it exists
        if (frm.fields_dict.title) {
            frm.set_value('title', full_name);
        }
    }
});
