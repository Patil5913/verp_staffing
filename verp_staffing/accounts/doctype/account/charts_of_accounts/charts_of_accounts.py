import json
import os
from collections import defaultdict
import time
import frappe
from frappe.utils import cstr
from frappe.utils.nestedset import rebuild_tree
from unidecode import unidecode
from pathlib import Path

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
    if existing_company:
        return get_account_tree_from_existing_company(existing_company)

    if chart_template == "Standard":
        from verp_staffing.accounts.doctype.account.charts_of_accounts.verified import (
            standard_chart_of_accounts,
        )

        return standard_chart_of_accounts.get()

    if chart_template == "Standard with Numbers":
        from verp_staffing.accounts.doctype.account.charts_of_accounts.verified import (
            standard_chart_of_accounts_with_account_number,
        )

        return standard_chart_of_accounts_with_account_number.get()

    folders = ("verified",)
    if frappe.local.flags.allow_unverified_charts:
        folders = ("verified", "unverified")

    base_dir = Path(__file__).resolve().parent

    for folder in folders:
        folder_path = (base_dir / folder).resolve()

        for file_path in folder_path.iterdir():
            if file_path.suffix != ".json":
                continue

            # Prevent path traversal / symlink escape
            if folder_path not in file_path.resolve().parents:
                continue

            with file_path.open(encoding="utf-8") as f:
                chart = json.load(f)

            if chart.get("name") == chart_template:
                return chart.get("tree")


@frappe.whitelist()
def get_charts_for_country(country, with_standard=False):
    charts = []

    def _get_chart_name(content):
        if not content:
            return

        if (
            content.get("disabled", "No") == "No"
            or frappe.local.flags.allow_unverified_charts
        ):
            charts.append(content["name"])

    country_code = frappe.get_cached_value("Country", country, "code")
    if country_code:
        folders = ("verified",)
        if frappe.local.flags.allow_unverified_charts:
            folders = ("verified", "unverified")
            
        base_dir = Path(__file__).resolve().parent

        for folder in folders:
            folder_path = (base_dir / folder).resolve()

            if not folder_path.exists():
                continue

            for file_path in folder_path.iterdir():
                if (
                    file_path.suffix != ".json"
                    or not (
                        file_path.name.startswith(country_code)
                        or file_path.name.startswith(country)
                    )
                ):
                    continue

                # Prevent path traversal / symlink escape
                if folder_path not in file_path.resolve().parents:
                    continue

                with file_path.open(encoding="utf-8") as f:
                    _get_chart_name(json.load(f))

    # if more than one chart is returned, then add the standard charts
    if len(charts) != 1 or with_standard:
        charts.extend(["Standard", "Standard with Numbers"])

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