// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Interview", {
    refresh(frm) {
        console.log('Interview');
        set_round_numbers(frm);
    },

    validate(frm){
        validate_interview_times(frm);
    }
});

frappe.ui.form.on("Interview Round", {
    interview_rounds_table_add(frm) {
        console.log("interview_rounds_table_add");
        
        set_round_numbers(frm);
    },
    interview_rounds_table_remove(frm) {
        console.log("interview_rounds_table_remove");

        set_round_numbers(frm);
    }
});

function set_round_numbers(frm) {
    console.log("set_round_numbers");

    (frm.doc.interview_rounds_table || []).forEach(row => {
        
        row.round = row.idx;
        console.log("row.round", row.round);
    });
    frm.refresh_field("interview_rounds_table");
}

function validate_interview_times(frm) {
    const rows = frm.doc.interview_rounds_table || [];

    const timeRegex = /^(0[1-9]|1[0-2]):[0-5][0-9]\s(AM|PM)\s-\s(0[1-9]|1[0-2]):[0-5][0-9]\s(AM|PM)\s\((EDT|EST)\)$/;

    rows.forEach((row, index) => {
        if (!row.time_of_interview) {
            frappe.throw(`Row ${index + 1}: Time of Interview is required`);
        }

        if (!timeRegex.test(row.time_of_interview)) {
            frappe.throw(
                `Row ${index + 1}: Invalid Time of Interview format.\n` +
                `Expected: HH:MM (AM/PM) - HH:MM (AM/PM) (EDT/EST)\n` +
                `Example: 01:00 PM - 03:00 PM (EST)`
            );
        }
    });
}