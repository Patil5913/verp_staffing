# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class FiscalYear(Document):

    def validate(self):
        self.validate_dates()
        self.validate_company_overlap()

    def validate_dates(self):
        if self.year_start_date >= self.year_end_date:
            frappe.throw(
                _("Fiscal Year End Date must be after Start Date"),
                title=_("Invalid Date Range")
            )

    def validate_company_overlap(self):
        """
        A company cannot exist in more than one non-disabled fiscal year.
        Skip check if current fiscal year itself is disabled.
        """
        if self.disabled:
            return

        for row in self.get("included_companies", []):
            if not row.company:
                continue

            # Check if this company exists in any OTHER active fiscal year
            conflicting = frappe.db.get_value(
                "Fiscal Year Company",
                filters={
                    "company": row.company,
                    "parent": ("!=", self.name or ""),
                    "parentfield": "included_companies",
                },
                fieldname="parent",
            )

            if conflicting:
                # Make sure that conflicting FY is not disabled
                is_disabled = frappe.db.get_value("Fiscal Year", conflicting, "disabled")
                if not is_disabled:
                    frappe.throw(
                        _("Company {0} is already assigned to active Fiscal Year {1}. "
                          "A company cannot belong to more than one active Fiscal Year.").format(
                            frappe.bold(row.company),
                            frappe.bold(conflicting)
                        ),
                        title=_("Duplicate Fiscal Year Assignment")
                    )


@frappe.whitelist()
def get_available_companies(doctype, txt, searchfield, start, page_len, filters):
    """
    Returns companies eligible to be added to a Fiscal Year's included_companies.
 
    A company is eligible if ANY of the following is true:
      (a) It has no entry in any Fiscal Year's included_companies at all.
      (b) Every Fiscal Year it appears in is disabled (disabled = 1).
      (c) It is already present in the CURRENT fiscal year being edited
          (so existing rows remain valid and don't disappear from the list).
 
    Args passed by Frappe Link search:
        doctype   – "Company"
        txt       – search string typed by user
        filters   – dict with key "current_fiscal_year"
    """
    
    current_fiscal_year = (filters or {}).get("current_fiscal_year", "")
 
    results = frappe.db.sql("""
		SELECT c.name, c.abbr
		FROM `tabCompany` c
		WHERE c.name LIKE %(txt)s
			AND NOT EXISTS (
				SELECT 1
				FROM `tabFiscal Year Company` fyc
				INNER JOIN `tabFiscal Year` fy ON fy.name = fyc.parent
				WHERE fyc.company = c.name
				AND fy.disabled = 0
				AND fy.name != %(current_fiscal_year)s
			)
		ORDER BY c.name
		LIMIT %(start)s, %(page_len)s
	""", {
		"txt": "%%%s%%" % (txt or ""),
		"current_fiscal_year": current_fiscal_year,
		"start": int(start),
		"page_len": int(page_len)
	})
 
    return results
 

