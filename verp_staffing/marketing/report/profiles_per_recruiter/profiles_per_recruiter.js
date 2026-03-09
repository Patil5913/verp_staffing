// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Profiles Per Recruiter"] = {
  filters: [
    {
      fieldname: "from_date",
      label: "From Date",
      fieldtype: "Date"
    },
    {
      fieldname: "to_date",
      label: "To Date",
      fieldtype: "Date"
    },
    {
    fieldname: "recruiter",
    label: "Recruiter",
    fieldtype: "Link",
    options: "Employee",
    get_query: function () {
        return {
            query: "verp_staffing.marketing.report.profiles_per_recruiter.profiles_per_recruiter.get_marketing_hierarchy_employees"
        };
    }
}
  ]
};
