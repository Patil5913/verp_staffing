# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

def make_opportunity(lead: None, owner=None):
    opp = frappe.new_doc("Opportunity")
    opp.opportunity_from_lead = lead.name
    opp.opportunity_owner = owner
    opp.name1 = lead.name1
    opp.insert(ignore_permissions=True)
    return opp


class TestOpportunity(FrappeTestCase):
	pass
