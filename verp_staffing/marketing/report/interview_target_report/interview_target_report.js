frappe.query_reports["Interview Target Report"] = {
    filters: [
        {
            fieldname: "from_date",
            label: "Select Date",
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today(),
            on_change: function () {
                frappe.query_report.refresh();
            }
        }
    ]
};
