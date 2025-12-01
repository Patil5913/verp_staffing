// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead Detail Form", {
    refresh(frm) {
        update_parent_skills(frm);
    }
});

frappe.ui.form.on("Lead Past Experience", {
    skills: function(frm, cdt, cdn) {
        update_parent_skills(frm);
    },
});


function update_parent_skills(frm) {
    let rows = frm.doc.past_experience_table || [];
    let collected = [];

    rows.forEach(row => {
        if (row.skills) {
            // split by comma, trim spaces, push into array
            row.skills.split(",").forEach(s => {
                let clean = s.trim();
                if (clean) collected.push(clean);
            });
        }
    });

    // remove duplicates + join back with comma
    let unique_skills = [...new Set(collected)];

    frm.set_value("additional_skills", unique_skills.join(","));
}