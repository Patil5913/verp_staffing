import json
import os
from collections import defaultdict
import time
import frappe
from frappe.utils import cstr
from frappe.utils.nestedset import rebuild_tree
from unidecode import unidecode


ACCOUNT_FIELDS = {
    "account_name",
    "account_number",
    "account_type",
    "root_type",
    "is_group",
    "tax_rate",
    "account_currency",
}

BALANCE_SHEET_ROOT_TYPES = {"Asset", "Liability", "Equity"}


def create_charts(
    company,
    chart_template=None,
    existing_company=None,
    custom_chart=None,
    from_coa_importer=None,
):
    chart = custom_chart or get_chart(chart_template, existing_company)

    if not chart:
        return

    default_currency = frappe.get_cached_value(
        "Company",
        company,
        "default_currency",
    )

    allow_unverified = frappe.local.flags.allow_unverified_charts

    account_name_counts = defaultdict(int)

    insert_time = 0
    insert_count = 0

    def _import_accounts(children, parent, root_type, root_account=False):
        nonlocal insert_time, insert_count

        for account_name, child in children.items():

            # FIXED: correct root type handling (no mutation issues)
            current_root_type = (
                child.get("root_type") if root_account else root_type
            )

            # skip metadata keys
            if account_name in ACCOUNT_FIELDS:
                continue

            # normalize account number once
            account_number_raw = child.get("account_number")
            account_number = cstr(account_number_raw).strip() if account_number_raw else ""

            # duplicate-safe naming (O(1) logic)
            account_name, account_name_in_db = add_suffix_if_duplicate(
                account_name,
                account_number,
                account_name_counts,
            )

            is_group = identify_is_group(child)

            report_type = (
                "Balance Sheet"
                if current_root_type in BALANCE_SHEET_ROOT_TYPES
                else "Profit and Loss"
            )

            # local bindings (avoid repeated dict lookups)
            account_type = child.get("account_type")
            account_currency = child.get("account_currency") or default_currency
            tax_rate = child.get("tax_rate")

            account_data = {
                "doctype": "Account",
                "account_name": (
                    child.get("account_name")
                    if from_coa_importer
                    else account_name
                ),
                "company": company,
                "parent_account": parent,
                "is_group": is_group,
                "root_type": current_root_type,
                "report_type": report_type,
                "account_number": account_number,
                "account_type": account_type,
                "account_currency": account_currency,
                "tax_rate": tax_rate,
            }

            account = frappe.get_doc(account_data)

            if root_account or allow_unverified:
                account.flags.ignore_mandatory = True

            account.flags.ignore_permissions = True

            start = time.perf_counter()
            account.insert()
            insert_time += time.perf_counter() - start
            insert_count += 1

            _import_accounts(
                child,
                account.name,
                current_root_type,
            )

    # IMPORTANT: preserve original NSM behavior safely
    previous_flag = frappe.local.flags.ignore_update_nsm
    frappe.local.flags.ignore_update_nsm = True

    try:
        _import_accounts(chart, None, None, root_account=True)
        rebuild_tree("Account", "parent_account")

    finally:
        frappe.local.flags.ignore_update_nsm = previous_flag
            


def add_suffix_if_duplicate(
    account_name,
    account_number,
    account_name_counts,
):
    normalized_name = (
        f"{account_number} - {account_name.strip().lower()}"
        if account_number
        else account_name.strip().lower()
    )

    account_name_in_db = unidecode(normalized_name)

    count = account_name_counts.get(account_name_in_db, 0)

    if count:
        account_name = f"{account_name} {count}"

    account_name_counts[account_name_in_db] += 1

    return account_name, account_name_in_db


def identify_is_group(child):
    if child.get("is_group"):
        is_group = child.get("is_group")
    elif len(
        set(child.keys())
        - set(
            [
                "account_name",
                "account_type",
                "root_type",
                "is_group",
                "tax_rate",
                "account_number",
                "account_currency",
            ]
        )
    ):
        is_group = 1
    else:
        is_group = 0

    return is_group


@frappe.whitelist()
def get_chart(chart_template, existing_company=None):
    chart = {}
    if existing_company:
        return get_account_tree_from_existing_company(existing_company)

    elif chart_template == "Standard":
        from verp_staffing.accounts.doctype.account.charts_of_accounts.verified import (
            standard_chart_of_accounts,
        )

        return standard_chart_of_accounts.get()
    elif chart_template == "Standard with Numbers":
        from verp_staffing.accounts.doctype.account.charts_of_accounts.verified import (
            standard_chart_of_accounts_with_account_number,
        )

        return standard_chart_of_accounts_with_account_number.get()
    else:
        folders = ("verified",)
        if frappe.local.flags.allow_unverified_charts:
            folders = ("verified", "unverified")
        for folder in folders:
            path = os.path.join(os.path.dirname(__file__), folder)
            for fname in os.listdir(path):
                fname = frappe.as_unicode(fname)
                if fname.endswith(".json"):
                    with open(os.path.join(path, fname)) as f:
                        chart = f.read()
                        if chart and json.loads(chart).get("name") == chart_template:
                            return json.loads(chart).get("tree")


@frappe.whitelist()
def get_charts_for_country(country, with_standard=False):
    charts = []

    def _get_chart_name(content):
        if content:
            content = json.loads(content)
            if (
                content and content.get("disabled", "No") == "No"
            ) or frappe.local.flags.allow_unverified_charts:
                charts.append(content["name"])

    country_code = frappe.get_cached_value("Country", country, "code")
    if country_code:
        folders = ("verified",)
        if frappe.local.flags.allow_unverified_charts:
            folders = ("verified", "unverified")

        for folder in folders:
            path = os.path.join(os.path.dirname(__file__), folder)
            if not os.path.exists(path):
                continue

            for fname in os.listdir(path):
                fname = frappe.as_unicode(fname)
                if (
                    fname.startswith(country_code) or fname.startswith(country)
                ) and fname.endswith(".json"):
                    with open(os.path.join(path, fname)) as f:
                        _get_chart_name(f.read())

    # if more than one charts, returned then add the standard
    if len(charts) != 1 or with_standard:
        charts += ["Standard", "Standard with Numbers"]

    return charts


def get_account_tree_from_existing_company(existing_company):
    all_accounts = frappe.get_all(
        "Account",
        filters={"company": existing_company},
        fields=[
            "name",
            "account_name",
            "parent_account",
            "account_type",
            "is_group",
            "root_type",
            "tax_rate",
            "account_number",
            "account_currency",
        ],
        order_by="lft, rgt",
    )
    
    if not all_accounts:
        return {}
    
    children_map = defaultdict(list)

    for account in all_accounts:
        children_map[cstr(account.parent_account)].append(account)
        
    account_tree = {}

    build_account_tree(
        tree=account_tree,
        parent=None,
        children_map=children_map,
    )

    return account_tree


def build_account_tree(tree, parent, children_map):
    # find children
    parent_account = parent.name if parent else ""
    children = children_map.get(parent_account, [])

    # if no children, but a group account
    if parent and not children and parent.is_group:
        tree["is_group"] = 1
        tree["account_number"] = parent.account_number

    # build a subtree for each child
    for child in children:
        subtree = {}
        # start new subtree
        tree[child.account_name] = subtree

        # assign account_type and root_type
        if child.account_number:
            subtree["account_number"] = child.account_number
        if child.account_type:
            subtree["account_type"] = child.account_type
        if child.tax_rate:
            subtree["tax_rate"] = child.tax_rate
        if not parent:
            subtree["root_type"] = child.root_type

        # call recursively to build a subtree for current account
        build_account_tree(
            tree=subtree,
            parent=child,
            children_map=children_map,
        )


# @frappe.whitelist()
# def validate_bank_account(coa, bank_account):
# 	accounts = []
# 	chart = get_chart(coa)

# 	if chart:

# 		def _get_account_names(account_master):
# 			for account_name, child in account_master.items():
# 				if account_name not in [
# 					"account_number",
# 					"account_type",
# 					"root_type",
# 					"is_group",
# 					"tax_rate",
# 				]:
# 					accounts.append(account_name)

# 					_get_account_names(child)

# 		_get_account_names(chart)

# 	return bank_account in accounts


# @frappe.whitelist()
# def build_tree_from_json(chart_template, chart_data=None, from_coa_importer=False):
# 	"""get chart template from its folder and parse the json to be rendered as tree"""
# 	chart = chart_data or get_chart(chart_template)

# 	# if no template selected, return as it is
# 	if not chart:
# 		return

# 	accounts = []

# 	def _import_accounts(children, parent):
# 		"""recursively called to form a parent-child based list of dict from chart template"""
# 		for account_name, child in children.items():
# 			account = {}
# 			if account_name in [
# 				"account_name",
# 				"account_number",
# 				"account_type",
# 				"root_type",
# 				"is_group",
# 				"tax_rate",
# 				"account_currency",
# 			]:
# 				continue

# 			if from_coa_importer:
# 				account_name = child["account_name"]

# 			account["parent_account"] = parent
# 			account["expandable"] = True if identify_is_group(child) else False
# 			account["value"] = (
# 				(cstr(child.get("account_number")).strip() + " - " + account_name)
# 				if child.get("account_number")
# 				else account_name
# 			)
# 			accounts.append(account)
# 			_import_accounts(child, account["value"])

# 	_import_accounts(chart, None)
# 	return accounts
