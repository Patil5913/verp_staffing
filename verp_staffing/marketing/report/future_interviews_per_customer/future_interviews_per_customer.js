// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.query_reports["Future Interviews Per Customer"] = {
  filters: [
    {
      fieldname: "to_date",
      label: "Up To Date",
      fieldtype: "Date"
    },
     { "fieldname": "customer",
            "label": "Customer",
            "fieldtype": "Link",
            "options": "Customer",
            "get_query": function() {
                return {
					            query: "verp_staffing.marketing.report.future_interviews_per_customer.future_interviews_per_customer.get_customers_with_interviews",
                };
            }
        }
  ]
};
