frappe.ui.form.on("lead_course", {
    start_date(frm, cdt, cdn) {
        validate_mm_yyyy_format(cdt, cdn, "start_date");
    },
    end_date(frm, cdt, cdn) {
        validate_mm_yyyy_format(cdt, cdn, "end_date");
    },
    grade(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        validate_grade(row, frm);
    }
});


function validate_mm_yyyy_format(cdt, cdn, fieldname) {
    let row = locals[cdt][cdn];
    let value = row[fieldname];
    if (!value) return;

    let pattern = /^(0[1-9]|1[0-2])-\d{4}$/;

    if (!pattern.test(value)) {
        frappe.msgprint({
            title: __("Invalid Format"),
            message: __(fieldname.replace("_", " ") + " must be in MM-YYYY format (example: 02-2025)"),
            indicator: "red"
        });

        frappe.model.set_value(cdt, cdn, fieldname, "");
    }
}


function validate_grade(row, frm) {
    if (row.grade < 0 || row.grade > 10) {
        frappe.msgprint({
            title: __("Invalid Format"),
            message: __("Grade must be between 0 and 10 only."),
            indicator: "red"
        });
    }
}