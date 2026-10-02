"""Interview rounds used to be typed in US Eastern and labelled EDT / EST (the Select field `edt_est`).
Move every such round into the company time zone, the zone all other dates and times are stored in,
and keep what was typed in `entered_as`. EDT and EST are fixed UTC-4 / UTC-5, so the exact moment each
round was typed for is preserved. Safe to re-run: only rounds still carrying a label and no Time Zone move."""

import frappe

from verp_staffing.utils.timezone import company_time_zone, convert_round

ETC_ZONE = {"EDT": "Etc/GMT+4", "EST": "Etc/GMT+5"}


def execute():
	frappe.reload_doc("marketing", "doctype", "interview_round")
	if not frappe.db.has_column("Interview Round", "edt_est"):
		return

	company = company_time_zone()
	rows = frappe.db.sql(
		"""SELECT name, date_of_interview, from_time, to_time, edt_est FROM `tabInterview Round`
		WHERE IFNULL(edt_est, '') != '' AND IFNULL(time_zone, '') = ''""",
		as_dict=True,
	)
	for r in rows:
		zone = ETC_ZONE.get(r.edt_est)
		values = {"time_zone": company}
		if zone and r.date_of_interview and r.from_time:
			local = convert_round(r.date_of_interview, r.from_time, r.to_time, zone, company)
			values.update(
				date_of_interview=local["date"],
				from_time=local["from_time"],
				to_time=local["to_time"],
				entered_as=f"{r.from_time} {r.edt_est}"[:140],
			)
		frappe.db.set_value("Interview Round", r.name, values, update_modified=False)
