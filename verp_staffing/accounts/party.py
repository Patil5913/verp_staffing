import frappe

def validate_party_frozen_disabled(party_type, party_name):
	if frappe.flags.ignore_party_validation:
		return

	if party_type and party_name:
		if party_type in ("Customer", "Supplier"):
			party = frappe.get_cached_value(party_type, party_name, ["is_frozen", "disabled"], as_dict=True)
			if party.disabled:
				frappe.throw(_("{0} {1} is disabled").format(party_type, party_name))
			elif party.get("is_frozen"):
				frozen_accounts_modifier = frappe.db.get_single_value(
					"Accounts Settings", "frozen_accounts_modifier"
				)
				if frozen_accounts_modifier not in frappe.get_roles():
					frappe.throw(_("{0} {1} is frozen").format(party_type, party_name))

		elif party_type == "Employee":
			if frappe.db.get_value("Employee", party_name, "status") != "Active":
				frappe.msgprint(_("{0} {1} is not active").format(party_type, party_name), alert=True)

def validate_account_party_type(self):
	if self.is_cancelled:
		return

	if self.party_type and self.party:
		account_type = frappe.get_cached_value("Account", self.account, "account_type")
		if account_type and (account_type not in ["Receivable", "Payable", "Equity"]):
			frappe.throw(
				_("Party Type and Party can only be set for Receivable / Payable account<br><br>{0}").format(
					self.account
				)
			)
