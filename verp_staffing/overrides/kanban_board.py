# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

"""Resilience wrapper around Frappe's native Kanban Board order-save
endpoints.

Frappe's built-in Kanban board can dispatch `update_order_for_single_card`
and `update_order` back-to-back for a single drag action. Both write to
the same Kanban Board document, and the second save can lose the
optimistic-lock race against the first, raising a QueryDeadlockError
("Record has changed since last read").

This is a transient condition, not a data-integrity problem — retrying
the save against the now-current document version resolves it safely.
"""

import time

import frappe
from frappe.desk.doctype.kanban_board import kanban_board as _core

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 0.3


def _retry_on_deadlock(fn, *args, **kwargs):
	last_exc = None

	for attempt in range(1, MAX_RETRIES + 1):
		try:
			return fn(*args, **kwargs)
		except frappe.QueryDeadlockError as e:
			last_exc = e
			frappe.db.rollback()

			if attempt == MAX_RETRIES:
				break

			frappe.log_error(
				title="Kanban Board save deadlock — retrying",
				message=f"Attempt {attempt}/{MAX_RETRIES} for {fn.__name__}. {e}",
			)
			time.sleep(RETRY_BACKOFF_SECONDS * attempt)  # small linear backoff

	raise last_exc


def _strip_dispatch_only_kwargs(kwargs):
	"""`frappe.call(method, **frappe.form_dict)` passes the ENTIRE request
	payload as kwargs, which includes framework/dispatch-only keys (e.g.
	`cmd` — the dotted method path itself) that the real, narrowly-typed
	core function was never meant to receive. Because this wrapper's
	signature is `*args, **kwargs` (intentionally permissive, so it works
	regardless of what params the installed Frappe version's core function
	declares), those keys pass straight through unless we remove them here.
	"""
	kwargs.pop("cmd", None)
	return kwargs


@frappe.whitelist()
def update_order_for_single_card(*args, **kwargs):
	kwargs = _strip_dispatch_only_kwargs(kwargs)
	return _retry_on_deadlock(_core.update_order_for_single_card, *args, **kwargs)


@frappe.whitelist()
def update_order(*args, **kwargs):
	kwargs = _strip_dispatch_only_kwargs(kwargs)
	return _retry_on_deadlock(_core.update_order, *args, **kwargs)