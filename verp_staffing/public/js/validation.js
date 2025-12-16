window.LeadCourse = {
    validate_mm_yyyy(value) {
        return /^(0[1-9]|1[0-2])-[0-9]{4}$/.test(value);
    },

    validate_grade(value) {
        value = Number(value || 0);
        return value >= 0 && value <= 10;
    },

    check_row(row) {
        if (row.start_date && !this.validate_mm_yyyy(row.start_date)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("Start Date must be in MM-YYYY format (example: 02-2025)"),
                indicator: "red"
            });
            row.start_date = "";
        }

        if (row.end_date && !this.validate_mm_yyyy(row.end_date)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("End Date must be in MM-YYYY format (example: 02-2025)"),
                indicator: "red"
            });
            row.end_date = "";
        }

        if (row.grade && !this.validate_grade(row.grade)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("Grade must be between 0 and 10"),
                indicator: "red"
            });
            row.grade = "";
        }
    }
};