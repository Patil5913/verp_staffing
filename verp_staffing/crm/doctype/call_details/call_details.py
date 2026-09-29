# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

from frappe.model.document import Document


def unit_for_seconds(seconds) -> str:
	"""Hours when the duration is a whole number of hours, else Minutes."""
	seconds = int(seconds or 0)
	return "Hours" if seconds and seconds % 3600 == 0 else "Minutes"


class CallDetails(Document):
	def validate(self):
		# duration is always stored in seconds; the unit is how it was entered and is shown
		if self.duration_unit not in ("Minutes", "Hours"):
			self.duration_unit = unit_for_seconds(self.duration)
