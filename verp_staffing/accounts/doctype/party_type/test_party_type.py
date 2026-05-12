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

    if party_type_map is None:
        party_type_map = {
            "Customer": "Receivable",
            "Supplier": "Payable",
        }

    overrides.pop("party_type", None)
    overrides.pop("account_type", None)

    created_or_fixed = []

    for party_type, account_type in party_type_map.items():
        if not frappe.db.exists("Party Type", party_type):
            doc = frappe.get_doc(
                {
                    "doctype": "Party Type",
                    "party_type": party_type,
                    "account_type": account_type,
                    **overrides,
                }
            )
            doc.insert(ignore_permissions=True)
            created_or_fixed.append(party_type)

        else:
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
