# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPartyType(FrappeTestCase):
    pass


def create_party_types_if_not_exists(
    party_type_map=None,
    return_names=False,
    **overrides,
):
    """
    Ensure Party Types exist with correct account types.

    Flow:
    1. Create missing Party Types using overrides
    2. Fix mismatched account_type for existing Party Types
    """

    if party_type_map is None:
        party_type_map = {
            "Customer": "Receivable",
            "Supplier": "Payable",
        }

    created_or_fixed = []

    for party_type, account_type in party_type_map.items():

        existing = frappe.db.exists(
            "Party Type",
            party_type,
        )

        if not existing:
            party_type_data = {
                "doctype": "Party Type",
                "party_type": party_type,
                "account_type": account_type,
                **overrides,
            }

            doc = frappe.get_doc(party_type_data)
            doc.insert(ignore_permissions=True)

            created_or_fixed.append(party_type)

            continue

        existing_account_type = frappe.db.get_value(
            "Party Type",
            party_type,
            "account_type",
        )

        if existing_account_type != account_type:
            frappe.db.set_value(
                "Party Type",
                party_type,
                "account_type",
                account_type,
            )

            created_or_fixed.append(party_type)

    return created_or_fixed if return_names else None