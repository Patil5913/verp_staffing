import frappe
@frappe.whitelist()
def get_party_account(party_type, party=None, company=None, include_advance=False):
	"""Returns the account for the given `party`.
	Will first search in party (Customer / Supplier) record, if not found,
	will search in group (Customer Group / Supplier Group),
	finally will return default."""
	if not party_type:
		frappe.throw(_("Party Type is mandatory"))
	if not company:
		frappe.throw(_("Please select a Company"))

	if not party and party_type in ["Customer", "Supplier"]:
		default_account_name = (
			"default_receivable_account" if party_type == "Customer" else "default_payable_account"
		)

		return frappe.get_cached_value("Company", company, default_account_name)

	account = frappe.db.get_value(
		"Party Account", {"parenttype": party_type, "parent": party, "company": company}, "account"
	)

	if not account and party_type in ["Customer", "Supplier"]:
		party_group_doctype = "Customer Group" if party_type == "Customer" else "Supplier Group"
		group = frappe.get_cached_value(party_type, party, scrub(party_group_doctype))
		account = frappe.db.get_value(
			"Party Account",
			{"parenttype": party_group_doctype, "parent": group, "company": company},
			"account",
		)

	if not account and party_type in ["Customer", "Supplier"]:
		default_account_name = (
			"default_receivable_account" if party_type == "Customer" else "default_payable_account"
		)
		account = frappe.get_cached_value("Company", company, default_account_name)

	existing_gle_currency = get_party_gle_currency(party_type, party, company)
	if existing_gle_currency:
		if account:
			account_currency = frappe.get_cached_value("Account", account, "account_currency")
		if (account and account_currency != existing_gle_currency) or not account:
			account = get_party_gle_account(party_type, party, company)

	# get default account on the basis of party type
	if not account:
		account_type = frappe.get_cached_value("Party Type", party_type, "account_type")
		default_account_name = "default_" + account_type.lower() + "_account"
		account = frappe.get_cached_value("Company", company, default_account_name)

	if include_advance and party_type in ["Customer", "Supplier", "Student"]:
		advance_account = get_party_advance_account(party_type, party, company)
		if advance_account:
			return [account, advance_account]
		else:
			return [account]

	return account