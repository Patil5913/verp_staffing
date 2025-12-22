// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Interview", {
    refresh(frm) {
        set_round_numbers(frm);

        const grid = frm.fields_dict.interview_rounds_table?.grid;
        if (!grid) return;

        grid.update_docfield_property("date", "read_only", 1);
        grid.update_docfield_property("round", "read_only", 1);

        if (!frm.is_new()) {
            frm.set_df_property("marketing_link", "read_only", 1);
            frm.set_df_property("role", "read_only", 1);
        }
    },

    validate(frm){
        validate_interview_times(frm);
    }
});

frappe.ui.form.on("Interview Round", {
    interview_rounds_table_add(frm, cdt, cdn) {
        console.log("interview_rounds_table_add");
        
        set_round_numbers(frm);

        const row = locals[cdt][cdn];
        
        // set default today's date
         if (!row.date) {
            row.date = frappe.datetime.get_today();
        }

        // adding previos follow up value in state
        row.__prev_follow_up = row.follow_up || 0;
    },

    interview_rounds_table_remove(frm) {
        console.log("interview_rounds_table_remove");

        set_round_numbers(frm);
    },

    follow_up(frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        const prev = row.__prev_follow_up ?? 0;
        const curr = row.follow_up;

        if (curr !== prev + 1) {
            frappe.msgprint(
                `Invalid Follow Up value. Only allowed value is ${prev + 1}`
            );

            row.follow_up = prev;
            frm.refresh_field("interview_rounds_table");
            return;
        }

        row.__prev_follow_up = curr;
    }
});

function set_round_numbers(frm) {
    (frm.doc.interview_rounds_table || []).forEach(row => {
        row.round = row.idx;
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