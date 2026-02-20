// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead Detail Form", {
    refresh(frm) {
        update_parent_skills(frm);
        frm.toggle_enable('reference_table', false);
    },

    additional_skills(frm) {
        // Ensure clean merge when user manually edits
        update_parent_skills(frm);
    },

    surname: function(frm) { frm.trigger('update_title'); },
    first_name: function(frm) { frm.trigger('update_title'); },
    father_name: function(frm) { frm.trigger('update_title'); },

    update_title: function(frm) {
        let full_name = [
            frm.doc.surname, 
            frm.doc.first_name, 
            frm.doc.father_name
        ].filter(Boolean).join(" ");
        
        // Update a 'title' field if it exists
        if (frm.fields_dict.title) {
            frm.set_value('title', full_name);
        }
    }
});

frappe.ui.form.on("Lead Past Experience", {
    skills(frm, cdt, cdn) {
        update_parent_skills(frm, cdt, cdn);
    },

    past_experience_table_add(frm) {
        setTimeout(() => update_parent_skills(frm), 0);
    },

    past_experience_table_remove(frm) {
        update_parent_skills(frm);
    }
});


function update_parent_skills(frm, cdt, cdn) {
    let manual_skills_raw = frm.doc.additional_skills || "";
    let manual_skills = manual_skills_raw
        .split(",")
        .map(s => s.trim())
        .filter(s => s.length > 0);

    // Collect skills from child table 
    let child_skills = [];

    (frm.doc.past_experience_table || []).forEach(row => {
        if (!row.skills) return;
        
        row.skills.split(",").forEach(s => {
            let clean = s.trim();
            if (clean) child_skills.push(clean);
        });
    });

    // Merge manual + child, remove duplicates
    let merged = [...new Set([...manual_skills, ...child_skills])];

    frm.set_value("additional_skills", merged.join(", "));
}
