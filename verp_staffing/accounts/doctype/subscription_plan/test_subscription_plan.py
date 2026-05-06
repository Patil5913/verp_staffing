# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists


class TestSubscriptionPlan(FrappeTestCase):
	pass


def create_subscription_plan_if_not_exists(
    plan_name,
    item_name,
    rate,
    interval,
    interval_count,
    is_active=1,
    currency="INR",
):
    """Return an existing Subscription Plan or create and return a new one."""

    if not plan_name:
        frappe.throw("Plan name is required")

    if not item_name:
        frappe.throw("Item is required for Subscription Plan")

    # Ensure item exists
    item_name = create_item_if_not_exists(item_name)

    if frappe.db.exists("Subscription Plan", {"plan_name": plan_name}):
        return plan_name

    plan = frappe.get_doc(
        {
            "doctype": "Subscription Plan",
            "plan_name": plan_name,
            "item": item_name,
            "billing_interval": interval,
            "billing_interval_count": interval_count,
            "currency": currency,
            "rate": rate,
            "is_active": is_active,
        }
    )

    plan.insert(ignore_permissions=True)

    return plan.name