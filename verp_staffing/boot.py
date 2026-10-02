"""
Adds `is_sample_data_removed` to frappe.boot so the client-side guard
(sample_data_guard.js) can check it as a plain in-memory read on every
save, instead of calling the server every single time.
"""

from verp_staffing.utils.sample_data_tracking import is_sample_data_removed


def boot_session(bootinfo):
	try:
		bootinfo["is_sample_data_removed"] = is_sample_data_removed()
	except Exception:
		bootinfo["is_sample_data_removed"] = 0