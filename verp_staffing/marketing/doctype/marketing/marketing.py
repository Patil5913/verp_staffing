# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.model.document import Document
from verp_staffing.crm.api.customer import update_customer_stage
from verp_staffing.crm.api.naming import generate_name_series


class Marketing(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Marketing", customer_name)

    def validate(self):
        self._validate_job_application_rows()
        # validate() runs before Frappe casts Int fields, so `target` can still
        # be the raw string the client sent ("5", "5.0") — compare as a number.
        if self.target not in (None, ""):
            try:
                target = flt(self.target)
            except (TypeError, ValueError):
                frappe.throw(_("Target must be a number"))
            if target != int(target):
                frappe.throw(_("Target must be a whole number"))
            self.target = int(target)
        if self.start_date and (not self.target or self.target <= 0):
            frappe.throw(_("Target must be greater than 0 when Start Date is set"))

    def _validate_job_application_rows(self):
        """Same rules the forms apply, enforced here so an API call can't skip them. A row with no date is
        dated today (the company's day). Unless the user sits above the assignee, a new row must be today's,
        and an existing row's counts and date can only be changed by the user who created it, on its day."""
        rows = self.get("job_application_count") or []
        today = frappe.utils.getdate(frappe.utils.today())
        for row in rows:
            if not row.date:
                row.date = today

        before = self.get_doc_before_save()
        previous = {r.name: r for r in (before.get("job_application_count") if before else None) or []}
        changed = [r for r in rows if _job_row_changed(r, previous.get(r.name))]
        if not changed:
            return

        from verp_staffing.crm.api.helpers import _is_superior_in_department

        if _is_superior_in_department(self.assign_to, frappe.session.user, "Marketing").get("is_superior"):
            return

        for row in changed:
            old = previous.get(row.name)
            if old is None:
                if frappe.utils.getdate(row.date) != today:
                    frappe.throw(_("Row #{0}: a new job application count must be dated today ({1}).").format(row.idx, today))
            elif old.owner != frappe.session.user or frappe.utils.getdate(old.date) != today:
                frappe.throw(_("Row #{0}: only the user who added a job application count can change it, and only on its day.").format(row.idx))

    def after_insert(self):
        update_customer_stage(
            customer=self.customer,
            service="marketing",
        )


def _job_row_changed(row, old):
    if old is None:
        return True
    return (
        cint(row.small_application) != cint(old.small_application)
        or cint(row.large_application) != cint(old.large_application)
        or frappe.utils.getdate(row.date) != frappe.utils.getdate(old.date)
    )


@frappe.whitelist()
def get_interviews_by_marketing(marketing):
    if not marketing:
        return []
    interviews = frappe.get_all(
        "Interview",
        filters={"marketing_link": marketing},
        fields=["company", "name", "role", "status"],
        order_by="creation desc",
    )

    # `can_open` = whether the current user may read it (their own, or a visible team member's -
    # Interview's permission hook); every interview is still listed, the rest are just not linked
    return [
        {
            "name": i.name,
            "company": i.company,
            "role": i.role,
            "status": i.status,
            "can_open": bool(frappe.has_permission("Interview", "read", doc=i.name)),
        }
        for i in interviews
    ]
