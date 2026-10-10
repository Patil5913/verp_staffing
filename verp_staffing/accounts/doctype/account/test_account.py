# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase



ROOT_MAP = {
    "Asset": "Application of Funds (Assets)",
    "Liability": "Source of Funds (Liabilities)",
    "Income": "Income",
    "Expense": "Expenses",
    "Equity": "Equity",
}

PARENT_MAP = {
    "Asset": "Current Assets",
    "Liability": "Current Liabilities",
    "Income": "Direct Income",
    "Expense": "Direct Expenses",
    "Equity": "Capital Account",
}


def create_account_if_not_exists(
    account_name,
    company,
    parent_account=None,
    root_type="Asset",
    account_type=None,
    is_group=0,
    **overrides,
):

    abbr = frappe.db.get_value("Company", company, "abbr")
    clean_name = account_name.split(" - ")[0]

    # Check if already exists
    if existing := frappe.db.exists(
        "Account", {"account_name": clean_name, "company": company}
    ):
        return frappe.get_doc("Account", existing)

    # ─────────────────────────────
    # 1. Ensure ROOT exists
    # ─────────────────────────────
    root_label = ROOT_MAP[root_type]
    root_name = f"{root_label} - {abbr}"

    if not frappe.db.exists("Account", root_name):
        frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": root_label,
                "company": company,
                "is_group": 1,
                "root_type": root_type,
            }
        ).insert(ignore_permissions=True)

    # ─────────────────────────────
    # 2. Determine / validate parent
    # ─────────────────────────────
    if parent_account:
        parent_root = frappe.db.get_value("Account", parent_account, "root_type")
        if parent_root and parent_root != root_type:
            frappe.throw(
                f"Parent account root_type mismatch: {parent_root} != {root_type}"
            )
    else:
        parent_label = PARENT_MAP.get(root_type, "Current Assets")
        parent_account = f"{parent_label} - {abbr}"

        if not frappe.db.exists("Account", parent_account):
            frappe.get_doc(
                {
                    "doctype": "Account",
                    "account_name": parent_label,
                    "company": company,
                    "parent_account": root_name,
                    "is_group": 1,
                    "root_type": root_type,
                }
            ).insert(ignore_permissions=True)

    # ─────────────────────────────
    # 3. Create actual account
    # ─────────────────────────────
    defaults = {
        "doctype": "Account",
        "account_name": clean_name,
        "company": company,
        "parent_account": parent_account,
        "is_group": is_group,
        "root_type": root_type,
        "account_type": account_type,
        **overrides,
    }

    account = frappe.get_doc(defaults)
    account.insert(ignore_permissions=True)
    return account


from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.account import account as mod
from verp_staffing.accounts.doctype.account.account import Account, get_account_autoname


def acct(before=None, **kw):
	doc = Account({"doctype": "Account", "account_name": "Cash", "company": "C", "parent_account": "Assets - C", **kw})
	doc.get_doc_before_save = lambda: before
	return doc


class TestRules(FrappeTestCase):
	def test_roots_cannot_be_edited_and_must_be_groups(self):
		with self.assertRaises(mod.RootNotEditable):
			acct(before=frappe._dict(parent_account=None)).validate_root_details()
		with self.assertRaises(frappe.ValidationError):
			acct(parent_account=None, is_group=0).validate_root_details()
		acct(parent_account=None, is_group=1).validate_root_details()
		acct(before=frappe._dict(parent_account="X")).validate_root_details()

	def test_duplicate_account_numbers_in_a_company_are_refused(self):
		doc = acct(account_number="1000")
		doc.name = "1000 - Cash - C"
		with mock.patch.object(mod.frappe.db, "sql", return_value=[("Other",)]):
			with self.assertRaises(frappe.ValidationError):
				doc.validate_account_number()
		with mock.patch.object(mod.frappe.db, "sql", return_value=[]):
			doc.validate_account_number()
		with mock.patch.object(mod.frappe.db, "sql") as q:
			acct().validate_account_number()
			q.assert_not_called()

	def test_disabling_checks_company_defaults_only_on_change(self):
		with mock.patch.object(Account, "validate_default_accounts_in_company") as v:
			acct(before=None, disabled=1).validate_disabled()
			acct(before=frappe._dict(disabled=1), disabled=1).validate_disabled()
			acct(before=frappe._dict(disabled=1), disabled=0).validate_disabled()
			v.assert_not_called()
			acct(before=frappe._dict(disabled=0), disabled=1).validate_disabled()
			v.assert_called_once()

	def test_group_ledger_conversion(self):
		with mock.patch.object(Account, "validate_default_accounts_in_company"):
			with self.assertRaises(frappe.ValidationError):
				acct(before=frappe._dict(is_group=0), is_group=1, account_type="Bank").validate_group_or_ledger()
			doc = acct(before=frappe._dict(is_group=0), is_group=1)
			with mock.patch.object(Account, "check_gle_exists", return_value=True):
				with self.assertRaises(frappe.ValidationError):
					doc.validate_group_or_ledger()
			with mock.patch.object(Account, "check_gle_exists", return_value=False):
				doc.validate_group_or_ledger()
		doc = acct(before=frappe._dict(is_group=1), is_group=0)
		with mock.patch.object(Account, "check_if_child_exists", return_value=[(1,)]):
			with self.assertRaises(frappe.ValidationError):
				doc.validate_group_or_ledger()
		with mock.patch.object(Account, "check_if_child_exists", return_value=[]):
			doc.validate_group_or_ledger()
		acct(before=None, is_group=1).validate_group_or_ledger()

	def test_root_and_report_type_are_mandatory(self):
		with self.assertRaises(frappe.ValidationError):
			acct(root_type="", report_type="Balance Sheet").validate_mandatory()
		with self.assertRaises(frappe.ValidationError):
			acct(root_type="Asset", report_type="").validate_mandatory()
		acct(root_type="Asset", report_type="Balance Sheet").validate_mandatory()


class TestAutoname(FrappeTestCase):
	def company(self, v):
		return mock.patch.object(mod.frappe, "get_cached_value", return_value=v)

	def test_number_name_and_abbreviation(self):
		with self.company(frappe._dict(abbr="ACM", name="Acme")):
			self.assertEqual(get_account_autoname("1000", " Cash ", "Acme"), "1000 - Cash - ACM")
			self.assertEqual(get_account_autoname("", "Cash", "Acme"), "Cash - ACM")
			self.assertEqual(get_account_autoname(None, "Cash", "Acme"), "Cash - ACM")
			self.assertEqual(get_account_autoname("  ", "Cash", "Acme"), "Cash - ACM")

	def test_unknown_company(self):
		with self.company(None):
			with self.assertRaises(frappe.ValidationError):
				get_account_autoname("1", "Cash", "Nope")
