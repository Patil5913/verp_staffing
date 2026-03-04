// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Future Interviews Per Customer"] = {
  filters: [
    {
      fieldname: "to_date",
      label: "Up To Date",
      fieldtype: "Date"
    }
  ]
};
