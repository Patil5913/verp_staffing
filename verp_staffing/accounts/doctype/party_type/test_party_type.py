# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase


class TestPartyType(FrappeTestCase):
	pass


def create_party_types_if_not_exists(return_names=False):
    """
    Ensure Party Types exist with correct account types.

    Returns:
        list | None
    """

    party_type_map = {
        "Customer": "Receivable",
        "Supplier": "Payable",
    }

    created_or_fixed = []

    for party_type, account_type in party_type_map.items():

        if not frappe.db.exists("Party Type", party_type):
            doc = frappe.get_doc({
                "doctype": "Party Type",
                "party_type": party_type,
                "account_type": account_type,
            })
            doc.insert(ignore_permissions=True)
            created_or_fixed.append(party_type)

        else:
            existing = frappe.db.get_value(
                "Party Type", party_type, "account_type"
            )

            if existing != account_type:
                frappe.db.set_value(
                    "Party Type",
                    party_type,
                    "account_type",
                    account_type
                )
                created_or_fixed.append(party_type)

    return created_or_fixed if return_names else None