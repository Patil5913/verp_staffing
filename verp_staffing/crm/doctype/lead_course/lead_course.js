frappe.ui.form.on("lead_course", {
    start_date(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!window.LeadCourse.check_row(row)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("Start Date must be in MM-YYYY format (example: 02-2025)"),
                indicator: "red"
            });
            row.start_date = "";
        }
    },
    end_date(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!window.LeadCourse.check_row(row)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("End Date must be in MM-YYYY format (example: 02-2025)"),
                indicator: "red"
            });
            row.end_date = "";
        }
    },
    grade(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!window.LeadCourse.check_row(row)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("Grade must be between 0 and 10"),
                indicator: "red"
            });
            row.grade = "";
        }
    }
});