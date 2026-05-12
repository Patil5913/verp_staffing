import re

import frappe
from frappe.utils import (
	add_days,
	cint,
	create_batch,
	cstr,
	flt,
	formatdate,
	get_datetime,
	get_number_format_info,
	getdate,
	now,
	nowdate,
)
from frappe import _
import functools
from frappe.query_builder.utils import DocType
from json import loads
from pypika import Order
from pypika.terms import ExistsCriterion

class FiscalYearNotFoundError(frappe.ValidationError):
    """Raised when no active Fiscal Year matches the given date/company"""
    pass

def get_autoname_with_number(number_value, doc_title, company):
	"""append title with prefix as number and suffix as company's abbreviation separated by '-'"""
	company_abbr = frappe.get_cached_value("Company", company, "abbr")
	parts = [doc_title.strip(), company_abbr]

	if cstr(number_value).strip():
		parts.insert(0, cstr(number_value).strip())

	return " - ".join(parts)

@frappe.whitelist()
def get_children(doctype, parent, company, is_root=False):

	parent_fieldname = "parent_" + frappe.scrub(doctype)
	fields = ["name as value", "is_group as expandable"]
	filters = [["docstatus", "<", 2]]

	filters.append([f'ifnull(`{parent_fieldname}`,"")', "=", "" if is_root else parent])

	if is_root:
		fields += ["root_type", "report_type", "account_currency"] if doctype == "Account" else []
		filters.append(["company", "=", company])

	else:
		fields += ["root_type", "account_currency"] if doctype == "Account" else []
		fields += [parent_fieldname + " as parent"]

	acc = frappe.get_list(doctype, fields=fields, filters=filters)

	if doctype == "Account":
		sort_accounts(acc, is_root, key="value")

	return acc


def sort_accounts(accounts, is_root=False, key="name"):
	"""Sort root types as Asset, Liability, Equity, Income, Expense"""

	def compare_accounts(a, b):
		if re.split(r"\W+", a[key])[0].isdigit():
			# if chart of accounts is numbered, then sort by number
			return int(a[key] > b[key]) - int(a[key] < b[key])
		elif is_root:
			if a.report_type != b.report_type and a.report_type == "Balance Sheet":
				return -1
			if a.root_type != b.root_type and a.root_type == "Asset":
				return -1
			if a.root_type == "Liability" and b.root_type == "Equity":
				return -1
			if a.root_type == "Income" and b.root_type == "Expense":
				return -1
		else:
			# sort by key (number) or name
			return int(a[key] > b[key]) - int(a[key] < b[key])
		return 1

	accounts.sort(key=functools.cmp_to_key(compare_accounts))


@frappe.whitelist()
def get_fiscal_year(
    date=None, fiscal_year=None, label="Date", verbose=1, company=None, as_dict=False, boolean=False
):
    if isinstance(boolean, str):
        boolean = loads(boolean)
    fiscal_years = get_fiscal_years(
        date, fiscal_year, label, verbose, company, as_dict=as_dict, boolean=boolean
    )
    if boolean:
        return fiscal_years
    else:
        return fiscal_years[0]

@frappe.whitelist()
def get_fiscal_years(
    transaction_date=None,
    fiscal_year=None,
    label="Date",
    verbose=1,
    company=None,
    as_dict=False,
    boolean=False,
):
    fiscal_years = frappe.cache().hget("fiscal_years", company) or []

    if not fiscal_years:
        FY = DocType("Fiscal Year")
        query = (
            frappe.qb.from_(FY)
            .select(FY.name, FY.year_start_date, FY.year_end_date)
            .where(FY.disabled == 0)
        )

        if fiscal_year:
            query = query.where(FY.name == fiscal_year)

        if company:
            FYC = DocType("Fiscal Year Company")
            # Include fiscal year if:
            # - No companies are linked to it (global fiscal year)
            # - OR this specific company is linked to it
            query = query.where(
                ExistsCriterion(
                    frappe.qb.from_(FYC)
                    .select(FYC.name)
                    .where(FYC.parent == FY.name)
                    .where(FYC.parentfield == "included_companies")  # ← your fieldname
                ).negate()
                | ExistsCriterion(
                    frappe.qb.from_(FYC)
                    .select(FYC.company)
                    .where(FYC.parent == FY.name)
                    .where(FYC.parentfield == "included_companies")  # ← your fieldname
                    .where(FYC.company == company)
                )
            )

        query = query.orderby(FY.year_start_date, order=Order.desc)
        fiscal_years = query.run(as_dict=True)
        frappe.cache().hset("fiscal_years", company, fiscal_years)

    if not transaction_date and not fiscal_year:
        return fiscal_years

    if transaction_date:
        transaction_date = getdate(transaction_date)

    for fy in fiscal_years:
        matched = False
        if fiscal_year and fy.name == fiscal_year:
            matched = True
        if (
            transaction_date
            and getdate(fy.year_start_date) <= transaction_date
            and getdate(fy.year_end_date) >= transaction_date
        ):
            matched = True

        if matched:
            if as_dict:
                return (fy,)
            else:
                return ((fy.name, fy.year_start_date, fy.year_end_date),)

    # Build error message
    error_msg = _("{0} {1} is not in any active Fiscal Year").format(
        _(label), formatdate(transaction_date)
    )
    if company:
        error_msg = _("{0} for company {1}").format(error_msg, frappe.bold(company))

    if boolean:
        return False

    if verbose == 1:
        frappe.msgprint(error_msg, title=_("Fiscal Year Not Found"), indicator="orange")

    raise FiscalYearNotFoundError(error_msg)

def get_currency_precision():
	precision = cint(frappe.db.get_default("currency_precision"))
	if not precision:
		number_format = frappe.db.get_default("number_format") or "#,###.##"
		precision = get_number_format_info(number_format)[2]

	return precision


@frappe.whitelist()
def get_balance_on(
	account=None,
	date=None,
	party_type=None,
	party=None,
	company=None,
	ignore_account_permission=False,
	account_type=None,
	start_date=None,
	currency_mode="company"
):
	if not account and frappe.form_dict.get("account"):
		account = frappe.form_dict.get("account")
	if not date and frappe.form_dict.get("date"):
		date = frappe.form_dict.get("date")
	if not party_type and frappe.form_dict.get("party_type"):
		party_type = frappe.form_dict.get("party_type")
	if not party and frappe.form_dict.get("party"):
		party = frappe.form_dict.get("party")

	cond = []
	if start_date:
		cond.append("posting_date >= %s" % frappe.db.escape(cstr(start_date)))
	if date:
		cond.append("posting_date <= %s" % frappe.db.escape(cstr(date)))
	else:
		# get balance of all entries that exist
		date = nowdate()

	if account:
		acc = frappe.get_doc("Account", account)

	try:
		get_fiscal_year(date, company=company, verbose=0)[1]
	except FiscalYearNotFoundError:
		if getdate(date) > getdate(nowdate()):
			# if fiscal year not found and the date is greater than today
			# get fiscal year for today's date and its corresponding year start date
			get_fiscal_year(nowdate(), verbose=1)[1]
		else:
			# this indicates that it is a date older than any existing fiscal year.
			# hence, assuming balance as 0.0
			return 0.0

	if account:
		if not (frappe.flags.ignore_account_permission or ignore_account_permission):
			acc.check_permission("read")

		# different filter for group and ledger - improved performance
		if acc.is_group:
			cond.append(
				f"""exists (
				select name from `tabAccount` ac where ac.name = gle.account
				and ac.lft >= {acc.lft} and ac.rgt <= {acc.rgt}
			)"""
			)
		else:
			cond.append(f"""gle.account = {frappe.db.escape(account)} """)

	if account_type:
		accounts = frappe.db.get_all(
			"Account",
			filters={"company": company, "account_type": account_type, "is_group": 0},
			pluck="name",
			order_by="lft",
		)

		cond.append(
			"""
			gle.account in (%s)
		"""
			% (", ".join([frappe.db.escape(account) for account in accounts]))
		)

	if party_type and party:
		cond.append(
			f"""gle.party_type = {frappe.db.escape(party_type)} and gle.party = {frappe.db.escape(party)} """
		)

	if company:
		cond.append("""gle.company = %s """ % (frappe.db.escape(company)))

	if account or (party_type and party) or account_type:
		precision = get_currency_precision()
		company_currency = frappe.get_cached_value("Company", company, "default_currency")

		acc_currency = None
		if account:
			acc_currency = acc.account_currency

		if currency_mode == "account" and acc_currency and acc_currency != company_currency:
			# transaction currency
			select_field = "sum(round(debit, %s)) - sum(round(credit, %s))"
		else:
			# company currency
			select_field = "sum(round(debit_in_company_currency, %s)) - sum(round(credit_in_company_currency, %s))"

		bal = frappe.db.sql(
			"""
			SELECT {}
			FROM `tabGL Entry` gle
			WHERE {}""".format(select_field, " and ".join(cond)),
			(precision, precision),
		)[0][0]
		# if bal is None, return 0
		return flt(bal)



@frappe.whitelist()
def get_account_balances(accounts, company):
	if isinstance(accounts, str):
		accounts = loads(accounts)

	if not accounts:
		return []

	company_currency = frappe.get_cached_value("Company", company, "default_currency")

	for account in accounts:
		account["company_currency"] = company_currency
		account["balance"] = flt(get_balance_on(account["value"], company=company,currency_mode="company"))
		# Foreign currency account balance
		if account["account_currency"] and account["account_currency"] != company_currency:
			account["balance_in_account_currency"] = flt(get_balance_on(account["value"], company=company,currency_mode="account"))

	return accounts

# Add account directly from tree view

@frappe.whitelist()
def add_ac(args=None):
	from frappe.desk.treeview import make_tree_args

	if not args:
		args = frappe.local.form_dict

	args.doctype = "Account"
	args = make_tree_args(**args)

	ac = frappe.new_doc("Account")

	if args.get("ignore_permissions"):
		ac.flags.ignore_permissions = True
		args.pop("ignore_permissions")

	ac.update(args)

	if not ac.parent_account:
		ac.parent_account = args.get("parent")

	ac.old_parent = ""
	ac.freeze_account = "No"
	if cint(ac.get("is_root")):
		ac.parent_account = None
		ac.flags.ignore_mandatory = True

	ac.insert()

	return ac.name