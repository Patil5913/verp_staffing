# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	add_months,
	add_years,
	cint,
	flt,
	getdate,
	today,
)


# ====================================================================
# Constants
# ====================================================================

STATUS_ACTIVE = "Active"
STATUS_TRIAL = "Trialing"
STATUS_PAUSED = "Paused"
STATUS_CANCELLED = "Cancelled"
STATUS_COMPLETED = "Completed"

GENERATE_AT_END = "End of the current subscription period"
GENERATE_AT_BEGIN = "Beginning of the current subscription period"
GENERATE_AT_DAYS_BEFORE = "Days before the current subscription period"

DISCOUNT_TYPE_PERCENT = "Percentage"
DISCOUNT_TYPE_FIXED = "Fixed Amount"

APPLIES_ON_NET = "Net Amount"
APPLIES_ON_PLAN_RATE = "Plan Rate"

SUBSCRIPTION_TYPE_SALES = "Sales"
SUBSCRIPTION_TYPE_PURCHASE = "Purchase"

# Hard cap to prevent runaway loops on bad data
HARD_CAP_INVOICES = 1000


# ====================================================================
# Controller
# ====================================================================


class Subscription(Document):
	# ----------------------------------------------------------------
	# Lifecycle hooks
	# ----------------------------------------------------------------

	def validate(self) -> None:
		self._validate_party()
		self._validate_currency()
		self._validate_plan_and_qty()
		self._validate_dates()
		self._validate_end_date_alignment()
		self._validate_discount_schedule()
		self._validate_one_time_charges()
		self._validate_taxes()
		self._validate_pause()

		self._compute_net_total()

	def before_submit(self) -> None:
		# Status should only resolve after submit; if user is just saving a draft,
		# leave status as-is.
		if not self.status or self.status not in (
			STATUS_ACTIVE,
			STATUS_TRIAL,
			STATUS_PAUSED,
		):
			self.status = STATUS_TRIAL if self._has_trial() else STATUS_ACTIVE

	def on_cancel(self) -> None:
		# Frappe's built-in cancel via docstatus=2. Mirror to our business status.
		self.db_set("status", STATUS_CANCELLED, update_modified=False)
		if not self.cancelation_date:
			self.db_set("cancelation_date", today(), update_modified=False)

	# ----------------------------------------------------------------
	# Validation helpers
	# ----------------------------------------------------------------

	def _validate_party(self) -> None:
		if self.subscription_type == SUBSCRIPTION_TYPE_SALES and self.party_type != "Customer":
			frappe.throw(_("For Sales subscriptions, Party Type must be Customer."))
		if self.subscription_type == SUBSCRIPTION_TYPE_PURCHASE and self.party_type != "Supplier":
			frappe.throw(
				_("For Purchase subscriptions, Party Type must be Supplier.")
			)
		if not self.party:
			frappe.throw(_("Party is required."))
		if not frappe.db.exists(self.party_type, self.party):
			frappe.throw(_("{0} {1} does not exist.").format(self.party_type, self.party))

	def _validate_currency(self) -> None:
		if not self.get("billing_currency"):
			frappe.throw(_("Billing Currency is required."))

		# Plan currency must match billing currency
		if self.plan:
			plan_currency = frappe.db.get_value("Subscription Plan", self.plan, "currency")
			if plan_currency and plan_currency != self.billing_currency:
				frappe.throw(
					_("Plan currency ({0}) does not match billing currency ({1}).").format(
						plan_currency, self.billing_currency
					)
				)

	def _validate_plan_and_qty(self) -> None:
		if not self.plan:
			frappe.throw(_("Plan is required."))

		plan = frappe.get_cached_doc("Subscription Plan", self.plan)
		if not plan.is_active:
			frappe.throw(_("Plan {0} is inactive and cannot be used.").format(self.plan))

		if flt(self.qty) <= 0:
			frappe.throw(_("Quantity must be greater than zero."))

		if not plan.billing_interval or cint(plan.billing_interval_count) <= 0:
			frappe.throw(
				_("Plan {0} has an invalid billing interval configuration.").format(self.plan)
			)

	def _validate_dates(self) -> None:
		if not self.start_date:
			frappe.throw(_("Start Date is required."))

		if self.end_date and getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("End Date cannot be before Start Date."))

		if self.end_date and self.trial_period_end:
			if getdate(self.end_date) < getdate(self.trial_period_end):
				frappe.throw(_("End Date cannot be before Trial Period End."))
    
		if self.trial_period_end and getdate(self.trial_period_end) < getdate(self.start_date):
			frappe.throw(_("Trial Period End cannot be before Start Date."))

		if self.generate_invoice_at == GENERATE_AT_DAYS_BEFORE:
			if cint(self.number_of_days) <= 0:
				frappe.throw(
					_("Number of Days must be greater than zero when generating invoices before the period.")
				)

		if self.days_until_due and cint(self.days_until_due) < 0:
			frappe.throw(_("Days Until Due cannot be negative."))

	def _validate_end_date_alignment(self) -> None:
		"""End date must align with a billing-cycle boundary."""
		if not self.end_date or not self.plan:
			return

		plan = frappe.get_cached_doc("Subscription Plan", self.plan)
		billing_start = self._billing_start_date()
		end = getdate(self.end_date)

		min_valid = add_days(billing_start, -1)
		if end < min_valid:
			frappe.throw(
				_("End Date must be on or after {0}.").format(min_valid)
			)

		# Walk boundaries forward
		cursor = billing_start
		for _i in range(HARD_CAP_INVOICES):
			next_period_start = _add_interval(
				cursor, plan.billing_interval, cint(plan.billing_interval_count)
			)
			period_end = add_days(next_period_start, -1)

			if period_end == end:
				return
			if period_end > end:
				break
			cursor = next_period_start

		frappe.throw(
			_(
				"End Date must align with the billing cycle ({0} × {1}). "
				"It should fall on the last day of a billing period."
			).format(plan.billing_interval_count, plan.billing_interval)
		)

	def _validate_discount_schedule(self) -> None:
		if self.discount_schedule and not self.additional_discount_account:
			frappe.throw("Discount Account is required when Discount is applied.")
 
		seen_ranges: list[tuple[int, int]] = []
		for row in self.discount_schedule or []:
			from_n = cint(row.from_invoice_number)
			to_n = cint(row.to_invoice_number) if row.to_invoice_number else None

			if from_n <= 0:
				frappe.throw(
					_("Discount row {0}: From Invoice # must be at least 1.").format(row.idx)
				)
			if to_n is not None and to_n < from_n:
				frappe.throw(
					_("Discount row {0}: To Invoice # cannot be before From Invoice #.").format(row.idx)
				)
			if row.discount_type == DISCOUNT_TYPE_PERCENT:
				if flt(row.discount_value) < 0 or flt(row.discount_value) > 100:
					frappe.throw(
						_("Discount row {0}: percentage must be between 0 and 100.").format(row.idx)
					)
			else:
				if flt(row.discount_value) < 0:
					frappe.throw(
						_("Discount row {0}: discount value cannot be negative.").format(row.idx)
					)

			# Detect overlapping ranges (same range covering same invoice number
			# can be intentional for stacking, so we only warn on exact dupes).
			rng = (from_n, to_n if to_n is not None else -1)
			if rng in seen_ranges:
				frappe.msgprint(
					_("Discount row {0}: duplicate invoice range — discounts will stack.").format(
						row.idx
					),
					alert=True,
					indicator="orange",
				)
			seen_ranges.append(rng)

	def _validate_one_time_charges(self) -> None:
		for row in self.one_time_charges or []:
			if flt(row.qty) <= 0:
				frappe.throw(
					_("One-Time Charge row {0}: Qty must be greater than zero.").format(row.idx)
				)
			if flt(row.rate) < 0:
				frappe.throw(
					_("One-Time Charge row {0}: Rate cannot be negative.").format(row.idx)
				)
			if not row.account:
				frappe.throw(
					_("One-Time Charge row {0}: Account is required.").format(row.idx)
				)
			row.amount = flt(row.qty) * flt(row.rate)

	def _validate_taxes(self) -> None:
		for i, row in enumerate(self.taxes or []):
			if not row.charge_type:
				frappe.throw(_("Tax row {0}: Charge Type is required.").format(row.idx))
			if not row.account_head:
				frappe.throw(_("Tax row {0}: Account Head is required.").format(row.idx))

			if row.charge_type in ("On Previous Row Amount", "On Previous Row Total") and i == 0:
				frappe.throw(
					_("Tax row {0}: cannot reference previous row — this is the first row.").format(
						row.idx
					)
				)

			if row.charge_type == "Actual" and flt(row.tax_amount) < 0:
				frappe.throw(_("Tax row {0}: Tax Amount cannot be negative.").format(row.idx))

	def _validate_pause(self) -> None:
		if self.is_paused:
			if not self.pause_resume_date:
				frappe.throw(_("Resume Date is required when subscription is paused."))
			if getdate(self.pause_resume_date) <= getdate(today()):
				frappe.throw(_("Resume Date must be in the future."))

	def _compute_net_total(self) -> None:
		plan_rate = flt(frappe.db.get_value("Subscription Plan", self.plan, "rate")) if self.plan else 0
		self.net_total = flt(self.qty) * plan_rate

	# ----------------------------------------------------------------
	# Whitelisted actions (called from JS)
	# ----------------------------------------------------------------

	@frappe.whitelist()
	def cancel_subscription(self) -> None:
		"""Cancel immediately, or at period end if cancel_at_period_end is set."""
		if self.docstatus != 1:
			frappe.throw(_("Only submitted subscriptions can be cancelled."))
		if self.status == STATUS_CANCELLED:
			frappe.throw(_("Subscription is already cancelled."))

		if self.cancel_at_period_end:
			return

		self.db_set("status", STATUS_CANCELLED, update_modified=True)
		self.db_set("cancelation_date", today(), update_modified=True)
		self.add_comment("Info", _("Subscription cancelled."))

	@frappe.whitelist()
	def pause_subscription(self, resume_date: str) -> None:
		if self.docstatus != 1:
			frappe.throw(_("Only submitted subscriptions can be paused."))
		if self.status in (STATUS_CANCELLED, STATUS_COMPLETED, STATUS_TRIAL):
			frappe.throw(_("Cannot pause a {0} subscription.").format(self.status))
		if resume_date and getdate(resume_date) <= getdate(today()):
			frappe.throw(_("Resume Date must be in the future."))

		self.db_set("is_paused", 1, update_modified=True)
		if resume_date:
			self.db_set("pause_resume_date", resume_date, update_modified=True)
		self.db_set("status", STATUS_PAUSED, update_modified=True)
		if resume_date:
			self.add_comment("Info", _("Subscription paused until {0}.").format(resume_date))
		else:
			self.add_comment("Info", _("Subscription paused"))

	@frappe.whitelist()
	def resume_subscription(self) -> None:
		if self.docstatus != 1:
			frappe.throw(_("Only submitted subscriptions can be resumed."))
		if not self.is_paused:
			frappe.throw(_("Only paused Subscription can resume."))

		self.db_set("is_paused", 0, update_modified=True)
		self.db_set("pause_resume_date", None, update_modified=True)
		self.db_set("status", STATUS_TRIAL if self._has_trial_active() else STATUS_ACTIVE, update_modified=True)
		self.add_comment("Info", _("Subscription resumed."))

	# ----------------------------------------------------------------
	# Date helpers
	# ----------------------------------------------------------------

	def _has_trial(self) -> bool:
		return bool(self.trial_period_end)

	def _has_trial_active(self) -> bool:
		return bool(self.trial_period_end and getdate(self.trial_period_end) >= getdate(today()))

	def _billing_start_date(self) -> date:
		"""Date the first regular invoice's period begins."""
		if self.trial_period_end:
			return add_days(getdate(self.trial_period_end), 1)
		return getdate(self.start_date)

	# ----------------------------------------------------------------
	# Invoice generation engine
	# ----------------------------------------------------------------
 
	def get_next_invoice_schedule_entry(self) -> Optional[dict]:
		
		if not self.start_date or not self.plan:
			return None

		plan = frappe.get_cached_doc("Subscription Plan", self.plan)

		billing_start = self._billing_start_date()
		last_date = self.last_invoice_date

		# -----------------------------
		# STEP 1: determine current cycle start
		# -----------------------------
		if not last_date:
			# FIRST invoice cycle
			period_start = billing_start
			invoice_number = 1
		else:
			period_start = _add_interval(
				last_date,
				plan.billing_interval,
				cint(plan.billing_interval_count),
			)

			# derive invoice number from last date
			invoice_number = self._compute_invoice_index(billing_start, last_date, plan) + 1

		# -----------------------------
		# STEP 2: compute period end
		# -----------------------------
		next_period_start = _add_interval(
			period_start,
			plan.billing_interval,
			cint(plan.billing_interval_count),
		)

		period_end = add_days(next_period_start, -1)

		# -----------------------------
		# STEP 3: enforce subscription end
		# -----------------------------
		if self.end_date and period_start > getdate(self.end_date):
			return None

		if self.end_date and period_end > getdate(self.end_date):
			period_end = getdate(self.end_date)

		# -----------------------------
		# STEP 4: invoice date logic
		# -----------------------------
		generate_at = self.generate_invoice_at or GENERATE_AT_END

		if generate_at == GENERATE_AT_BEGIN:
			invoice_date = period_start
		elif generate_at == GENERATE_AT_DAYS_BEFORE:
			invoice_date = add_days(period_start, -cint(self.number_of_days))
		else:
			invoice_date = period_end

		due_date = add_days(invoice_date, cint(self.days_until_due))

		return {
			"invoice_number": invoice_number,
			"period_start": period_start,
			"period_end": period_end,
			"invoice_date": invoice_date,
			"due_date": due_date,
			"is_final": bool(self.end_date and period_end >= getdate(self.end_date)),
		}
  
	def _compute_invoice_index(self, billing_start, cursor, plan):
		"""Derive invoice number from cursor position (no stored state)."""

		if cursor <= billing_start:
			return 1

		step = _add_interval(
			billing_start,
			plan.billing_interval,
			cint(plan.billing_interval_count),
		)

		index = 1

		while step <= cursor:
			step = _add_interval(step, plan.billing_interval, cint(plan.billing_interval_count))
			index += 1

		return index

	def is_due_for_invoicing(self, as_of: Optional[date] = None) -> bool:
		"""True if the next invoice's invoice_date is exactly today (per spec:
		only generate when scheduled invoice_date is today or future, and we
		only fire on today; future scheduled invoices wait until their day)."""
		if self.docstatus != 1:
			return False
		if self.status in (STATUS_CANCELLED, STATUS_COMPLETED):
			return False
		if self.is_paused:
			return False

		as_of = as_of or getdate(today())
		entry = self.get_next_invoice_schedule_entry()
		if not entry:
			return False
		return getdate(entry["invoice_date"]) <= as_of

	def generate_next_invoice(self) -> Optional[str]:
		"""Generate the next due invoice. Returns the invoice name or None."""
		entry = self.get_next_invoice_schedule_entry()
  		
		if not entry:
			return None

		today_date = getdate(today())
		invoice_date = getdate(entry["invoice_date"])

		# If future → do nothing
		if invoice_date > today_date:
			return None

		# If past → generate today (catch-up logic)
		if invoice_date < today_date:
			entry["invoice_date"] = today_date

		if getdate(entry["invoice_date"]) > getdate(today()):
			# Not due yet
			return None

		invoice_doctype = (
			"Sales Invoice"
			if self.subscription_type == SUBSCRIPTION_TYPE_SALES
			else "Purchase Invoice"
		)
  
		invoice = self._build_invoice_doc(invoice_doctype, entry)
		invoice.insert(ignore_permissions=True)

		if cint(self.auto_submit_invoice_check):
			invoice.submit()

		# Bump counter atomically
		frappe.db.set_value(
			"Subscription",
			self.name,
			"last_invoice_date",
			entry["invoice_date"],
			update_modified=False,
		)

		# Handle deferred cancellation / completion
		if entry["is_final"]:
			frappe.db.set_value(
				"Subscription", self.name, "status", STATUS_COMPLETED, update_modified=False
			)
		elif self.cancel_at_period_end:
			frappe.db.set_value(
				"Subscription",
				self.name,
				{"status": STATUS_CANCELLED, "cancelation_date": today()},
				update_modified=False,
			)

		self.add_comment(
			"Info",
			_("Generated invoice {0} for period {1} → {2}.").format(
				invoice.name, entry["period_start"], entry["period_end"]
			),
		)
		return invoice.name

	# ----------------------------------------------------------------
	# Invoice building
	# ----------------------------------------------------------------

	def _build_invoice_doc(self, invoice_doctype: str, entry: dict) -> Document:
		"""Build a Sales Invoice or Purchase Invoice document (unsaved)."""
		is_sales = invoice_doctype == "Sales Invoice"
  
		invoice = frappe.new_doc(invoice_doctype)
		invoice.posting_date = entry["invoice_date"]
		invoice.due_date = entry["due_date"]
		invoice.company = self.company
		invoice.currency = self.billing_currency

		# ---- Plan line item ----
		plan = frappe.get_cached_doc("Subscription Plan", self.plan)
		item_doc = frappe.get_cached_doc("Item", plan.item)
  
		if is_sales:
			invoice.customer = self.party
		else:
			invoice.supplier = self.party
			invoice.credit_to = self._resolve_account(item_doc, is_sales, True)
  
		invoice.append(
			"items",
			{
				"item": plan.item,
				"qty": flt(self.qty),
				"uom": item_doc.stock_uom,
				"rate": flt(plan.rate),
				"amount": flt(self.qty) * flt(plan.rate),
				"type": SUBSCRIPTION_TYPE_SALES if is_sales else SUBSCRIPTION_TYPE_PURCHASE,
				"income_account": self._resolve_account(item_doc, is_sales, False) if is_sales else None,
				"expense_account": (
					None if is_sales else self._resolve_account(item_doc, is_sales, False)
				),
			},
		)

		# ---- One-time charges (only on FIRST regular invoice, #1) ----
		if entry.get("invoice_number") == 1 and self.one_time_charges:
			for otc in self.one_time_charges or []:
				invoice.append(
					"taxes",
					{
						"charge_type": "Actual",
						"account_head": otc.account,
						"rate": 0,
						"tax_amount": flt(otc.amount),
					},
				)
    
		# ---- Taxes (copied as-is; same child doctype on both sides) ----
		for tax in self.taxes or []:
			invoice.append(
				"taxes",
				{
					"charge_type": tax.charge_type,
					"account_head": tax.account_head,
					"rate": flt(tax.rate),
					"tax_amount": flt(tax.tax_amount),
					"total": flt(tax.total),
					"base_tax_amount": flt(tax.base_tax_amount),
					"base_total": flt(tax.base_total),
				},
			)

		# ---- Discount for THIS invoice number ----
		discount_row = self._resolve_discount_for_invoice(entry.get("invoice_number"))

		if discount_row:
			qty = flt(self.qty)
			plan_rate = flt(plan.rate)
			net_total = qty * plan_rate

			discount_value = flt(discount_row.discount_value)

			if discount_row.discount_type == DISCOUNT_TYPE_PERCENT:

				if discount_row.applies_on == APPLIES_ON_PLAN_RATE:
					# qty * (plan.rate * value%)
					invoice.discount_amount = qty * (plan_rate * discount_value / 100)

				else:
					# net_total * value%
					invoice.discount_amount = net_total * discount_value / 100

				invoice.additional_discount_percentage = discount_value

			else:
				# FIXED AMOUNT
				invoice.additional_discount_percentage = 0

				if discount_row.applies_on == APPLIES_ON_PLAN_RATE:
					# qty * value
					invoice.discount_amount = qty * discount_value

					# optional safety cap (same idea as JS comment, but safer in backend)
					if invoice.discount_amount > net_total:
						invoice.discount_amount = net_total

				else:
					# value (capped at net_total)
					invoice.discount_amount = discount_value
					if invoice.discount_amount > net_total:
						invoice.discount_amount = net_total

		# Optional discount account (only meaningful for Sales Invoice in
		if self.additional_discount_account:
			invoice.additional_discount_account = self.additional_discount_account
   
		# Stash a reference back to the subscription for traceability
		# if invoice.meta.has_field("subscription"):
		# 	invoice.subscription = self.name
		# invoice.set_missing_values() if hasattr(invoice, "set_missing_values") else None

		return invoice

	def _resolve_account(self, item_doc, is_sales, is_credit_to) -> Optional[str]:
		"""Pick an default income or expense account from company for the line item based on type."""
		if not item_doc:
			return None

		if is_sales:
			return frappe.get_cached_value("Company", self.company, "default_income_account")
		elif is_credit_to:
			return frappe.get_cached_value("Company", self.company, "default_payable_account")
		else:
			return frappe.get_cached_value("Company", self.company, "default_expense_account")

	def _resolve_discount_for_invoice(self, invoice_number: int):
		"""Return the most-specific discount schedule row covering this invoice.

		If multiple rows match, the one defined LAST in the table wins (allowing
		users to override earlier rules with later, more-specific ones). This
		mirrors how spec-style overrides usually behave; if you want stacking
		discounts at the invoice level, the schema would need to express that
		explicitly (e.g. via a 'stack' flag).
		"""
		match = None
		for row in self.discount_schedule or []:
			from_n = cint(row.from_invoice_number) or 1
			to_n = cint(row.to_invoice_number) if row.to_invoice_number else None
			if invoice_number >= from_n and (to_n is None or invoice_number <= to_n):
				match = row
		return match


# ====================================================================
# Module-level helpers
# ====================================================================


def _add_interval(d: date, interval: str, count: int) -> date:
	"""Add (interval × count) to a date. Mirrors the JS calculate_end_date."""
	count = cint(count)
	d = getdate(d)
	if interval == "Day":
		return add_days(d, count)
	if interval == "Week":
		return add_days(d, count * 7)
	if interval == "Month":
		return add_months(d, count)
	if interval == "Year":
		return add_years(d, count)
	return d


# ====================================================================
# Cron entry points (wire these in hooks.py)
# ====================================================================

from frappe.utils import now_datetime, escape_html


def process_due_subscriptions() -> None:
	"""Daily cron: generate today's due invoices for all eligible subscriptions.

	Points:
	  * Each subscription runs in its OWN transaction. A failure on one
	    subscription will NOT prevent later subscriptions from being processed,
	    nor will it roll back already-committed invoices.
	  * Every failure is captured (per-subscription error log + aggregated for
	    the admin report) so nothing fails silently.
	  * A single summary email is sent to administrators at the end of the run
	    whenever something noteworthy happened (failures, abort, generations,
	    or auto-resumes). Quiet days stay silent.
	"""
 
	today_dt = getdate(today())
	run_id = frappe.generate_hash(length=8)
	started_at = now_datetime()

	stats = {
		"run_id": run_id,
		"started_at": started_at,
		"today": today_dt,
		"auto_resumed": 0,
		"auto_resume_failures": [],     # [{"subscription": str, "error": str}]
		"subscriptions": 0,
		"generated": 0,
		"skipped": 0,
		"failed": 0,
		"generation_failures": [],      # [{"subscription": str, "error": str}]
		"generated_invoices": [],       # [{"subscription": str, "invoice": str}]
		"aborted": False,
		"abort_traceback": None,
	}

	try:
		# 1. Auto-resume any paused subscriptions whose resume date has arrived.
		_auto_resume_paused(today_dt, stats)

		# 2. Find Subscriptions: submitted, not cancelled/completed/trial, not paused, started.
		Subscriptions = frappe.get_all(
			"Subscription",
			filters={
				"docstatus": 1,
				"status": ["not in", [STATUS_CANCELLED, STATUS_COMPLETED, STATUS_TRIAL]],
				"is_paused": 0,
				"start_date": ["<=", today_dt],
			},
			pluck="name",
			order_by="creation asc",
		)
		stats["subscriptions"] = len(Subscriptions)

		# 3. Process each in isolation.
		for name in Subscriptions:
			_process_one_subscription(name, today_dt, stats)

	except Exception:
		# A top-level failure (DB blip, unexpected error in the loop scaffolding,
		# etc.) — record it but DO NOT swallow the report. We still want to
		# tell the admin what happened up to this point.
		stats["aborted"] = True
		stats["abort_traceback"] = frappe.get_traceback()
		frappe.db.rollback()
		frappe.log_error(
			title=f"[Subscription cron] aborted run {run_id}",
			message=stats["abort_traceback"],
		)

	finally:
		stats["finished_at"] = now_datetime()
		stats["duration_seconds"] = (
			stats["finished_at"] - stats["started_at"]
		).total_seconds()

		frappe.logger().info(
			f"[Subscription cron {run_id}] "
			f"resumed={stats['auto_resumed']} "
			f"resume_fail={len(stats['auto_resume_failures'])} "
			f"subscriptions={stats['subscriptions']} "
			f"generated={stats['generated']} "
			f"skipped={stats['skipped']} "
			f"failed={stats['failed']} "
			f"duration={stats['duration_seconds']:.1f}s "
			f"aborted={stats['aborted']}"
		)

		# Notification is best-effort; never let it crash the cron.
		try:
			_send_admin_report(stats)
		except Exception:
			frappe.log_error(
				title=f"[Subscription cron] failed to send admin report ({run_id})",
				message=frappe.get_traceback(),
			)


def _process_one_subscription(name: str, today_dt: date, stats: dict) -> None:
	"""Process a single subscription with isolated transaction boundaries."""
	try:
		sub = frappe.get_doc("Subscription", name)

		if not sub.is_due_for_invoicing(today_dt):
			stats["skipped"] += 1
			return

		invoice_name = sub.generate_next_invoice()

		if invoice_name:
			# Commit per-success so one downstream failure cannot roll back
			# already-generated invoices.
			frappe.db.commit()
			stats["generated"] += 1
			stats["generated_invoices"].append({
				"subscription": name,
				"invoice": invoice_name,
			})
		else:
			# generate_next_invoice returned None (e.g. nothing scheduled,
			# already in future, etc.) — nothing to commit, count as skipped.
			stats["skipped"] += 1

	except Exception as e:
		# Roll back this subscription's partial work so the next iteration
		# starts clean.
		frappe.db.rollback()
		stats["failed"] += 1
		traceback_str = frappe.get_traceback()
		stats["generation_failures"].append({
			"subscription": name,
			"error": (str(e) or e.__class__.__name__)[:500],
		})
		frappe.log_error(
			title=f"Subscription invoice generation failed: {name}",
			message=traceback_str,
		)


def _auto_resume_paused(today_dt: date, stats: dict | None = None) -> None:
	"""Flip is_paused → 0 for subscriptions whose pause_resume_date has arrived.
	Each resume is its own transaction so a single failure cannot block others.
	"""
	due_to_resume = frappe.get_all(
		"Subscription",
		filters={
			"docstatus": 1,
			"is_paused": 1,
			"pause_resume_date": ["<=", today_dt],
		},
		pluck="name",
	)

	for name in due_to_resume:
		try:
			sub = frappe.get_doc("Subscription", name)
			sub.resume_subscription()
			frappe.db.commit()
			if stats is not None:
				stats["auto_resumed"] += 1
		except Exception as e:
			frappe.db.rollback()
			if stats is not None:
				stats["auto_resume_failures"].append({
					"subscription": name,
					"error": (str(e) or e.__class__.__name__)[:500],
				})
			frappe.log_error(
				title=f"Subscription auto-resume failed: {name}",
				message=frappe.get_traceback(),
			)


# --------------------------------------------------------------------
# Admin notifications
# --------------------------------------------------------------------

def _send_admin_report(stats: dict) -> None:
	"""Email a summary of the cron run to administrators.
	Sends only when something noteworthy happened.
	"""
	has_failures = stats["failed"] > 0 or len(stats["auto_resume_failures"]) > 0
	has_abort = stats["aborted"]
	has_activity = stats["generated"] > 0 or stats["auto_resumed"] > 0

	if not (has_failures or has_abort or has_activity):
		return

	recipient = _get_admin_recipient()
	if not recipient:
		frappe.logger().warning(
			f"[Subscription cron {stats['run_id']}] no admin recipient "
			f"configured; report not sent"
		)
		return

	subject, message = _build_admin_email(stats, has_failures, has_abort)

	frappe.sendmail(
		recipients=recipient,
		subject=subject,
		message=message,
		header=[
			"Subscription Cron Report",
			"red" if has_abort else ("orange" if has_failures else "green"),
		],
		now=True,
	)


def _get_admin_recipient() -> str | None:
	"""Get recipient from Administrator's first linked Email Account."""

	try:
		admin_doc = frappe.get_doc("User", "Administrator")

		if not admin_doc.user_emails:
			return None

		first_row = admin_doc.user_emails[0]

		if not first_row.email_account:
			return None

		return frappe.db.get_value(
			"Email Account",
			first_row.email_account,
			"email_id",
		)

	except Exception:
		return None

def _build_admin_email(stats: dict, has_failures: bool, has_abort: bool):
	"""Compose subject + HTML body for the admin report."""
	today_str = stats["today"].strftime("%Y-%m-%d")

	if has_abort:
		prefix = "[ABORTED]"
	elif has_failures:
		prefix = "[Failures]"
	else:
		prefix = "[Success]"

	subject = (
		f"{prefix} Subscription Cron — {today_str} "
		f"(generated={stats['generated']}, failed={stats['failed']})"
	)

	# --- Summary table ---
	summary_rows = [
		("Run ID", stats["run_id"]),
		("Date", today_str),
		("Duration", f"{stats['duration_seconds']:.2f}s"),
		("Auto-resumed", stats["auto_resumed"]),
		("Auto-resume failures", len(stats["auto_resume_failures"])),
		("Subscriptions", stats["subscriptions"]),
		("Invoices generated", stats["generated"]),
		("Skipped (not due)", stats["skipped"]),
		("Failed", stats["failed"]),
		("Aborted top-level", "Yes" if has_abort else "No"),
	]
	summary_html = (
		"<table border='1' cellpadding='6' cellspacing='0' "
		"style='border-collapse:collapse;font-family:sans-serif'>"
		+ "".join(
			f"<tr><td><b>{escape_html(str(label))}</b></td>"
			f"<td>{escape_html(str(value))}</td></tr>"
			for label, value in summary_rows
		)
		+ "</table>"
	)

	parts = [
		"<h2 style='font-family:sans-serif'>Subscription Cron Run Summary</h2>",
		summary_html,
	]

	# --- Top-level abort ---
	if has_abort:
		parts.append("<h3 style='color:#b91c1c'>Top-level Abort</h3>")
		parts.append(
			"<p>The cron run terminated early due to an unhandled exception. "
			"Subscriptions processed before this point were committed; the "
			"remaining Subscriptions were NOT processed and will be retried "
			"on the next run.</p>"
			f"<pre style='background:#f5f5f5;padding:10px;overflow:auto;"
			f"font-size:12px'>{escape_html(stats.get('abort_traceback') or '')}</pre>"
		)

	# --- Generation failures ---
	if stats["generation_failures"]:
		parts.append(
			f"<h3 style='color:#b91c1c'>Invoice Generation Failures "
			f"({len(stats['generation_failures'])})</h3>"
		)
		parts.append(_failure_table(stats["generation_failures"]))

	# --- Auto-resume failures ---
	if stats["auto_resume_failures"]:
		parts.append(
			f"<h3 style='color:#b91c1c'>Auto-Resume Failures "
			f"({len(stats['auto_resume_failures'])})</h3>"
		)
		parts.append(_failure_table(stats["auto_resume_failures"]))

	# --- Successful generations (compact) ---
	if stats["generated_invoices"] and len(stats["generated_invoices"]) <= 50:
		parts.append(
			f"<h3 style='color:#166534'>Generated Invoices "
			f"({len(stats['generated_invoices'])})</h3>"
		)
		rows = "<table border='1' cellpadding='6' cellspacing='0' " \
		       "style='border-collapse:collapse;font-family:sans-serif'>" \
		       "<tr><th>Subscription</th><th>Invoice</th></tr>"
		for g in stats["generated_invoices"]:
			rows += (
				f"<tr><td>{escape_html(g['subscription'])}</td>"
				f"<td>{escape_html(g['invoice'])}</td></tr>"
			)
		rows += "</table>"
		parts.append(rows)
	elif len(stats["generated_invoices"]) > 50:
		parts.append(
			f"<p><i>{len(stats['generated_invoices'])} invoices generated "
			f"(list omitted to keep the email compact).</i></p>"
		)

	parts.append(
		"<hr><p style='color:#888;font-size:11px;font-family:sans-serif'>"
		"Full tracebacks are recorded in the Frappe Error Log. "
		"Filter by 'Subscription invoice generation failed' or "
		"'Subscription auto-resume failed' to drill down."
		"</p>"
	)

	return subject, "\n".join(parts)


def _failure_table(failures: list, cap: int = 50) -> str:
	"""Render a list of {subscription, error} dicts as an HTML table."""
	html = (
		"<table border='1' cellpadding='6' cellspacing='0' "
		"style='border-collapse:collapse;font-family:sans-serif'>"
		"<tr><th>Subscription</th><th>Error</th></tr>"
	)
	for f in failures[:cap]:
		html += (
			f"<tr><td>{escape_html(f['subscription'])}</td>"
			f"<td><code>{escape_html(f['error'])}</code></td></tr>"
		)
	html += "</table>"
	if len(failures) > cap:
		html += (
			f"<p><i>Showing first {cap} of {len(failures)} failures. "
			f"See Error Log for the rest.</i></p>"
		)
	return html


# ====================================================================
# Manual trigger 
# ====================================================================

@frappe.whitelist()
def generate_invoice_now(subscription: str):
	"""Manually trigger generation of the next invoice for a subscription.

	Useful for admin actions and debugging. Same safety semantics as the cron
	(per-call commit on success, rollback on failure).
	"""
	try:
		sub = frappe.get_doc("Subscription", subscription)
		invoice_name = sub.generate_next_invoice()
		if invoice_name:
			frappe.db.commit()
		return invoice_name
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title=f"Manual invoice generation failed: {subscription}",
			message=frappe.get_traceback(),
		)
		raise