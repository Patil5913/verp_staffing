import frappe
from frappe import _
from frappe.utils import add_days, flt, get_datetime_str, nowdate
from frappe.desk.reportview import get_match_cond
from verp_staffing.accounts.doctype.company.company import get_company_currency

@frappe.whitelist()
def get_exchange_rate(from_currency, to_currency, transaction_date=None, args=None):
	if not (from_currency or to_currency):
		# manqala 19/09/2016: Should this be an empty return or should it throw and exception?
		return
	if from_currency == to_currency:
		return 1

	if not transaction_date:
		transaction_date = nowdate()

	currency_settings = frappe.get_cached_doc("Accounts Settings")

	filters = [
		["date", "<=", get_datetime_str(transaction_date)],
		["from_currency", "=", from_currency],
		["to_currency", "=", to_currency],
	]

	if args == "for_buying":
		filters.append(["for_buying", "=", "1"])
	elif args == "for_selling":
		filters.append(["for_selling", "=", "1"])


	# cksgb 19/09/2016: get last entry in Currency Exchange with from_currency and to_currency.
	entries = frappe.get_all(
		"Currency Exchange", fields=["exchange_rate"], filters=filters, order_by="date desc", limit=1
	)
	if entries:
		return flt(entries[0].exchange_rate)

	if frappe.get_cached_value("Currency Exchange Settings", "Currency Exchange Settings", "disabled"):
		return 0.00

	pegged_currencies = {}

	try:
		cache = frappe.cache()
		key = f"currency_exchange_rate_{transaction_date}:{from_currency}:{to_currency}"
		value = cache.get(key)

		if not value:
			import requests

			settings = frappe.get_cached_doc("Currency Exchange Settings")
			req_params = {
				"transaction_date": transaction_date,
				"from_currency": from_currency
				if from_currency not in pegged_currencies
				else pegged_currencies[from_currency]["pegged_against"],
				"to_currency": to_currency
				if to_currency not in pegged_currencies
				else pegged_currencies[to_currency]["pegged_against"],
			}
			params = {}
			for row in settings.req_params:
				params[row.key] = format_ces_api(row.value, req_params)
			response = requests.get(format_ces_api(settings.api_endpoint, req_params), params=params)
			# expire in 6 hours
			response.raise_for_status()
			value = response.json()
			for res_key in settings.result_key:
				value = value[format_ces_api(str(res_key.key), req_params)]
			cache.setex(name=key, time=21600, value=flt(value))

		# Support multiple pegged currencies
		value = flt(value)


		return flt(value)
	except Exception:
		frappe.log_error("Unable to fetch exchange rate")
		frappe.msgprint(
			_(
				"Unable to find exchange rate for {0} to {1} for key date {2}. Please create a Currency Exchange record manually"
			).format(from_currency, to_currency, transaction_date)
		)
		return 0.0


def format_ces_api(data, param):
	return data.format(
		transaction_date=param.get("transaction_date"),
		to_currency=param.get("to_currency"),
		from_currency=param.get("from_currency"),
	)
 

@frappe.whitelist()
def get_tax_rate(account_head):
	return frappe.get_cached_value("Account", account_head, ["tax_rate", "account_name"], as_dict=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def tax_account_query(doctype, txt, searchfield, start, page_len, filters):
	doctype = "Account"
	company_currency = get_company_currency(filters.get("company"))

	def get_accounts(with_account_type_filter):
		account_type_condition = ""
		if with_account_type_filter:
			account_type_condition = "AND account_type in %(account_types)s"

		accounts = frappe.db.sql(
			f"""
			SELECT name, parent_account
			FROM `tabAccount`
			WHERE `tabAccount`.docstatus!=2
				{account_type_condition}
				AND is_group = 0
				AND company = %(company)s
				AND disabled = %(disabled)s
				AND (account_currency = %(currency)s or ifnull(account_currency, '') = '')
				AND `{searchfield}` LIKE %(txt)s
				{get_match_cond(doctype)}
			ORDER BY idx DESC, name
			LIMIT %(limit)s offset %(offset)s
		""",
			dict(
				account_types=filters.get("account_type"),
				company=filters.get("company"),
				disabled=filters.get("disabled", 0),
				currency=company_currency,
				txt=f"%{txt}%",
				offset=start,
				limit=page_len,
			),
		)

		return accounts

	tax_accounts = get_accounts(True)

	if not tax_accounts:
		tax_accounts = get_accounts(False)

	return tax_accounts