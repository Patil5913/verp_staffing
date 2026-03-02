frappe.ui.form.on("Lead Detail Form", {

    refresh(frm) {
        update_parent_skills(frm);
        // frm.toggle_enable('reference_table', false);
    },

    additional_skills(frm) {
        update_parent_skills(frm);
    },

    // lead_detail_form

    surname(frm) { frm.trigger('update_title'); },
    first_name(frm) { frm.trigger('update_title'); },
    father_name(frm) { frm.trigger('update_title'); },

    update_title(frm) {
        let full_name = [
            frm.doc.surname,
            frm.doc.first_name,
            frm.doc.father_name
        ].filter(Boolean).join(" ");

        if (frm.fields_dict.title) {
            frm.set_value('title', full_name);
        }
    }
});

frappe.ui.form.on("Lead Past Experience", {

    skills(frm) {
        update_parent_skills(frm);
    },

    past_experience_table_add(frm) {
        setTimeout(() => update_parent_skills(frm), 0);
    },

    past_experience_table_remove(frm) {
        update_parent_skills(frm);
    }
});


function update_parent_skills(frm) {

    let manual_skills_raw = frm.doc.additional_skills || "";

    let manual_skills = manual_skills_raw
        .split(",")
        .map(s => s.trim())
        .filter(s => s.length > 0);

    let child_skills = [];

    (frm.doc.past_experience_table || []).forEach(row => {
        if (!row.skills) return;

        row.skills.split(",").forEach(s => {
            let clean = s.trim();
            if (clean) child_skills.push(clean);
        });
    });

    let merged = [...new Set([...manual_skills, ...child_skills])];

    frm.set_value("additional_skills", merged.join(", "));
}