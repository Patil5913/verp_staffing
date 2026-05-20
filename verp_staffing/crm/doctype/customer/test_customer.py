# Copyright (c) 2026, Vrugle and contributors
# See license.txt

import base64
import json
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.model.document import Document
from verp_staffing.crm.doctype.customer.customer import (
    generate_token,
    get_customer_email,
    get_forwardable_departments,
    update_company_percentage,
)
from verp_staffing.employee.doctype.employee.test_employee import (
    _ensure_hierarchies,
)

_resolved: dict = {}


def _uid(prefix: str) -> str:
    """Return a unique, human-readable identifier safe for use as a Frappe name."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _doctype_exists(doctype: str) -> bool:
    return bool(frappe.db.exists("DocType", doctype))


def make_customer(
    name1: str = None,
    customer_from: str = None,
    party_name: str = None,
    stage: str = None,
    customer_owner: str = None,
    skip_insert: bool = False,
    **overrides,
) -> Document:
    existing_customer = frappe.db.get_list(
        "Customer", filters=[["name1", "=", name1]], fields=["name"], limit=1
    )
    if existing_customer:
        return frappe.get_doc("Customer", existing_customer[0].name)

    doc = frappe.new_doc("Customer")
    doc.name1 = name1

    if customer_from is not None:
        doc.customer_from = customer_from
    if party_name is not None:
        doc.party_name = party_name
    if stage is not None:
        doc.stage = stage
    if customer_owner is not None:
        doc.customer_owner = customer_owner

    doc.update(overrides)
    if skip_insert:
        return doc

    doc.insert(ignore_permissions=True)
    return doc


def make_lead_with_lead_detail(
    name_prefix: str = "Lead",
    email: str = None,
    **overrides,
) -> tuple:

    if not _doctype_exists("Lead"):
        return None, None

    lead = frappe.new_doc("Lead")
    lead.name1 = _uid(name_prefix)

    if email:
        lead.email = email

    for key, value in overrides.items():
        lead.set(key, value)

    lead.insert(ignore_permissions=True)

    # Lead.after_insert() already created this
    ldf = frappe.get_doc("Lead Detail Form", lead.lead_details)

    return lead, ldf


def seed_all():
    _ensure_hierarchies()


class CustomerTestBase(FrappeTestCase):
    """Shared setup / teardown for all Customer test classes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        seed_all()


class TestCustomerAutoname(CustomerTestBase):
    """
    autoname() must derive a unique, deterministic, human-readable key from
    name1 and raise frappe.ValidationError when name1 is absent.
    """

    def test_name_contains_slugified_customer_name(self):
        customer = make_customer(_uid("Autoname Alpha"))
        self.assertIn("Customer_Autoname_Alpha", customer.name)

    def test_name_is_non_empty_string(self):
        customer = make_customer(_uid("Name Type Check"))
        self.assertIsInstance(customer.name, str)
        self.assertGreater(len(customer.name), 0)

    def test_none_name1_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_customer(name1=None)

    def test_empty_string_name1_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_customer(name1="")

    def test_whitespace_only_name1_raises_validation_error(self):
        """Whitespace-only strings are falsy after strip; autoname should reject them."""
        with self.assertRaises(frappe.ValidationError):
            make_customer(name1="   ")

    def test_same_name_same_day_raises_duplicate_entry_error(self):
        """
        generate_name_series is date-keyed; inserting the same name1 twice on
        the same day must raise DuplicateEntryError (a subclass of ValidationError).
        """
        same_name = _uid("Dup Customer")
        make_customer(same_name)
        doc = frappe.new_doc("Customer")
        doc.name1 = same_name
        with self.assertRaises(frappe.DuplicateEntryError):
            # cannot use helper as it will return existing customer
            doc.insert(ignore_permissions=True)

    def test_different_names_produce_different_doc_names(self):
        c1 = make_customer(_uid("Unique Name A"))
        c2 = make_customer(_uid("Unique Name B"))
        self.assertNotEqual(c1.name, c2.name)


# ===========================================================================
# 2.  validate() – stage JSON
# ===========================================================================


class TestCustomerValidateStage(CustomerTestBase):
    """
    validate() must silently accept absent / falsy stage values and raise
    frappe.ValidationError for any stage text that is not valid JSON.
    """

    def test_valid_json_object_stage_passes(self):
        customer = make_customer(
            _uid("Valid JSON Object"),
            stage=json.dumps({"status": "active", "step": 1}),
        )
        self.assertTrue(customer.name)

    def test_valid_json_array_stage_passes(self):
        customer = make_customer(
            _uid("Valid JSON Array"),
            stage=json.dumps([{"key": "value"}, {"key2": "value2"}]),
        )
        self.assertTrue(customer.name)

    def test_json_null_string_stage_passes(self):
        """'null' is valid JSON; the validator must not reject it."""
        customer = make_customer(_uid("Null Stage"), stage="null")
        self.assertTrue(customer.name)

    def test_empty_string_stage_passes(self):
        """Empty string is falsy – the if-guard should skip validation entirely."""
        customer = make_customer(_uid("Empty Stage"), stage="")
        self.assertTrue(customer.name)

    def test_none_stage_passes(self):
        """None stage must not trigger the JSON validator."""
        customer = make_customer(_uid("None Stage"), stage=None)
        self.assertTrue(customer.name)

    def test_plain_string_stage_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_customer(_uid("Plain String Stage"), stage="hello world")

    def test_malformed_json_stage_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_customer(_uid("Malformed JSON"), stage="{key: value}")

    def test_partial_json_stage_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_customer(_uid("Partial JSON"), stage='{"status": "active"')

    def test_error_message_mentions_invalid_json(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            make_customer(_uid("Error Msg Check"), stage="not-json")
        self.assertIn("invalid json", str(ctx.exception).lower())

    def test_validate_can_be_called_directly_on_doc(self):
        """validate() must be callable directly on a transient doc."""
        doc = make_customer(_uid("Direct Validate"), skip_insert=True)
        doc.stage = json.dumps({"direct": True})
        try:
            doc.validate()
        except frappe.ValidationError:
            self.fail("validate() raised unexpectedly for valid JSON")


# ===========================================================================
# 3.  after_insert() – CASE 2: no party selected
# ===========================================================================


class TestCustomerAfterInsertNoParty(CustomerTestBase):
    """
    When no party_name / customer_from is supplied, after_insert() must create
    a fresh Lead Detail Form and link it to the Customer via the lead_details
    field (persisted through db_update).
    """

    def test_lead_details_field_is_populated_after_insert(self):
        customer = make_customer(_uid("Standalone Cust"))
        self.assertTrue(customer.lead_details)

    def test_lead_details_doc_exists_in_db(self):
        customer = make_customer(_uid("LDF Exists"))
        self.assertTrue(frappe.db.exists("Lead Detail Form", customer.lead_details))

    def test_lead_details_field_is_persisted_via_db_update(self):
        """db_update() must have saved lead_details to the database row."""
        customer = make_customer(_uid("DB Persist Check"))
        db_value = frappe.db.get_value("Customer", customer.name, "lead_details")
        self.assertEqual(db_value, customer.lead_details)

    def test_lead_detail_form_contains_customer_reference_row(self):
        """The newly created LDF must already have a reference row for the Customer."""
        customer = make_customer(_uid("Ref Row Check"))
        ldf = frappe.get_doc("Lead Detail Form", customer.lead_details)
        customer_refs = [
            row
            for row in ldf.reference_table
            if row.reference_doctype == "Customer"
            and row.reference_person == customer.name
        ]
        self.assertEqual(len(customer_refs), 1)

    def test_two_customers_receive_separate_lead_detail_forms(self):
        c1 = make_customer(_uid("Sep LDF A"))
        c2 = make_customer(_uid("Sep LDF B"))
        self.assertNotEqual(c1.lead_details, c2.lead_details)

    def test_lead_details_field_is_non_empty_string(self):
        customer = make_customer(_uid("LDF Type Check"))
        self.assertIsInstance(customer.lead_details, str)
        self.assertGreater(len(customer.lead_details), 0)


# ===========================================================================
# 4.  after_insert() – CASE 1: party selected
# ===========================================================================


class TestCustomerAfterInsertWithParty(CustomerTestBase):
    """
    When party_name + customer_from are both supplied, after_insert() must
    locate the existing Lead Detail Form via Doctype Reference, append a
    Customer reference row (idempotently), and link lead_details.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _doctype_exists("Lead"):
            return
        cls.lead, cls.ldf = make_lead_with_lead_detail(
            "Party Lead", email="party@test.com"
        )

    def _skip_if_no_lead(self):
        if not _doctype_exists("Lead"):
            self.skipTest("Lead DocType is not available in this environment")
        if not getattr(self, "lead", None):
            self.skipTest("Lead / Lead Detail Form setup failed")

    def test_customer_with_valid_party_links_to_existing_ldf(self):
        self._skip_if_no_lead()
        customer = make_customer(
            _uid("Party Customer"),
            customer_from="Lead",
            party_name=self.lead.name,
        )
        self.assertEqual(customer.lead_details, self.ldf.name)

    def test_customer_reference_row_appended_to_existing_ldf(self):
        self._skip_if_no_lead()
        customer = make_customer(
            _uid("Ref Append Check"),
            customer_from="Lead",
            party_name=self.lead.name,
        )
        ldf = frappe.get_doc("Lead Detail Form", self.ldf.name)
        refs = [
            row
            for row in ldf.reference_table
            if row.reference_doctype == "Customer"
            and row.reference_person == customer.name
        ]
        self.assertEqual(len(refs), 1)

    def test_duplicate_customer_reference_is_not_appended_twice(self):
        """
        If the same Customer name somehow appears twice, after_insert's
        duplicate-check must prevent a second identical row.
        """
        self._skip_if_no_lead()
        customer = make_customer(
            _uid("Idempotent Ref"),
            customer_from="Lead",
            party_name=self.lead.name,
        )
        # Manually call after_insert again (simulate a re-run)
        customer.after_insert()

        ldf = frappe.get_doc("Lead Detail Form", self.ldf.name)
        refs = [
            row
            for row in ldf.reference_table
            if row.reference_doctype == "Customer"
            and row.reference_person == customer.name
        ]
        self.assertEqual(len(refs), 1)

    def test_nonexistent_party_raises_validation_error(self):
        """A party_name that has no Doctype Reference row must raise."""
        if not _doctype_exists("Lead"):
            self.skipTest("Lead DocType is not available")
        with self.assertRaises(frappe.ValidationError):
            make_customer(
                _uid("Bad Party"),
                customer_from="Lead",
                party_name="DoesNotExist-99999",
            )

    def test_error_message_mentions_lead_details_not_found(self):
        if not _doctype_exists("Lead"):
            self.skipTest("Lead DocType is not available")
        with self.assertRaises(frappe.ValidationError) as ctx:
            make_customer(
                _uid("Error Msg Party"),
                customer_from="Lead",
                party_name="DoesNotExist-88888",
            )
        self.assertIn("Could not find Party", str(ctx.exception))


# ===========================================================================
# 5.  on_trash()
# ===========================================================================


class TestCustomerOnTrash(CustomerTestBase):
    """
    on_trash() delegates to unlink_and_clean_lead_detail.
    After deletion the Customer reference row in the LDF must be gone.
    """

    def test_deleting_customer_does_not_raise(self):
        customer = make_customer(_uid("Trash Safe"))
        try:
            frappe.delete_doc(
                "Customer", customer.name, ignore_permissions=True, force=True
            )
        except Exception as exc:
            self.fail(f"on_trash raised unexpectedly: {exc}")

    def test_deleting_customer_removes_reference_from_ldf(self):
        customer = make_customer(_uid("Trash Unlink"))
        ldf_name = customer.lead_details

        frappe.delete_doc(
            "Customer", customer.name, ignore_permissions=True, force=True
        )

        if not frappe.db.exists("Lead Detail Form", ldf_name):
            return  # LDF itself was deleted – reference is clearly gone

        ldf = frappe.get_doc("Lead Detail Form", ldf_name)
        refs = [
            row
            for row in ldf.reference_table
            if row.reference_doctype == "Customer"
            and row.reference_person == customer.name
        ]
        self.assertEqual(len(refs), 0)

    def test_customer_record_no_longer_exists_after_deletion(self):
        customer = make_customer(_uid("Trash Gone"))
        name = customer.name
        frappe.delete_doc("Customer", name, ignore_permissions=True, force=True)
        self.assertFalse(frappe.db.exists("Customer", name))


# ===========================================================================
# 6.  get_forwardable_departments()
# ===========================================================================


class TestGetForwardableDepartments(CustomerTestBase):
    """
    Tests for the get_forwardable_departments() whitelist function.
    Logic summary:
      - Active CR or Onboarding → blocked=True response dict
      - No active Sales Order   → only "CR" is forwardable
      - Services present, all completed + user in Marketing → Onboarding added
    """

    def _skip_if_no_cr(self):
        if not _doctype_exists("CR"):
            self.skipTest("CR DocType is not available in this environment")

    def _skip_if_no_onboarding(self):
        if not _doctype_exists("Onboardings"):
            self.skipTest("Onboardings DocType is not available in this environment")

    def test_fresh_customer_without_sales_order_returns_cr_option(self):
        customer = make_customer(_uid("No SO Cust"))
        result = get_forwardable_departments(customer.name)
        if isinstance(result, list):
            self.assertIn("CR", result)
        else:
            # May return dict with options key
            self.assertIn("CR", result.get("options", result))

    def test_result_type_is_list_or_dict(self):
        customer = make_customer(_uid("Type Check Fwd"))
        result = get_forwardable_departments(customer.name)
        self.assertIsInstance(result, (list, dict))

    def test_customer_with_active_cr_returns_blocked_true(self):
        self._skip_if_no_cr()
        customer = make_customer(_uid("Active CR Cust"))
        cr = frappe.new_doc("CR")
        cr.customer = customer.name
        cr.status = "Active"
        cr.insert(ignore_permissions=True)

        result = get_forwardable_departments(customer.name)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("blocked"))

    def test_customer_with_active_cr_blocked_response_includes_cr_in_active_in(self):
        self._skip_if_no_cr()
        customer = make_customer(_uid("Active CR Active In"))
        cr = frappe.new_doc("CR")
        cr.customer = customer.name
        cr.status = "Active"
        cr.insert(ignore_permissions=True)

        result = get_forwardable_departments(customer.name)
        self.assertIn("CR", result.get("active_in", []))

    def test_customer_with_active_onboarding_returns_blocked_true(self):
        self._skip_if_no_onboarding()
        customer = make_customer(_uid("Active Onboard Cust"))
        onboarding = frappe.new_doc("Onboardings")
        onboarding.customer = customer.name
        onboarding.status = "Active"
        onboarding.insert(ignore_permissions=True)

        result = get_forwardable_departments(customer.name)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("blocked"))

    def test_blocked_result_contains_active_in_list(self):
        self._skip_if_no_cr()
        customer = make_customer(_uid("Active In List Check"))
        cr = frappe.new_doc("CR")
        cr.customer = customer.name
        cr.status = "Active"
        cr.insert(ignore_permissions=True)

        result = get_forwardable_departments(customer.name)
        if result.get("blocked"):
            self.assertIn("active_in", result)
            self.assertIsInstance(result["active_in"], list)

    def test_active_in_contains_both_when_cr_and_onboarding_active(self):
        self._skip_if_no_cr()
        self._skip_if_no_onboarding()
        customer = make_customer(_uid("Both Active Cust"))
        cr = frappe.new_doc("CR")
        cr.customer = customer.name
        cr.status = "Active"
        cr.insert(ignore_permissions=True)

        onboarding = frappe.new_doc("Onboardings")
        onboarding.customer = customer.name
        onboarding.status = "Active"
        onboarding.insert(ignore_permissions=True)

        result = get_forwardable_departments(customer.name)
        active_in = result.get("active_in", [])
        self.assertIn("CR", active_in)
        self.assertIn("Onboarding", active_in)


# ===========================================================================
# 9.  get_customer_email()
# ===========================================================================


class TestGetCustomerEmail(CustomerTestBase):
    """
    get_customer_email() executes a JOIN between Lead Detail Form and
    Doctype Reference to fetch an email for a Customer.
    """

    def _attach_email_to_ldf(self, customer: Document, email: str):
        """Helper: set the email on a customer's linked Lead Detail Form."""
        ldf = frappe.get_doc("Lead Detail Form", customer.lead_details)
        ldf.email = email
        ldf.save(ignore_permissions=True)

    def test_returns_correct_email_for_customer_with_email(self):
        customer = make_customer(_uid("Email Cust"))
        self._attach_email_to_ldf(customer, "cust@example.com")
        email = get_customer_email(customer.name)
        self.assertEqual(email, "cust@example.com")

    def test_return_type_is_string(self):
        customer = make_customer(_uid("Email Type Cust"))
        self._attach_email_to_ldf(customer, "type@example.com")
        self.assertIsInstance(get_customer_email(customer.name), str)

    def test_different_customers_return_different_emails(self):
        c1 = make_customer(_uid("Email Diff A"))
        c2 = make_customer(_uid("Email Diff B"))
        self._attach_email_to_ldf(c1, "a@example.com")
        self._attach_email_to_ldf(c2, "b@example.com")
        self.assertNotEqual(get_customer_email(c1.name), get_customer_email(c2.name))

    def test_nonexistent_customer_raises(self):
        with self.assertRaises(Exception):
            get_customer_email("NonExistent-Customer-99999")

    def test_customer_without_email_in_ldf_raises_or_returns_none(self):
        """
        If the LDF row exists but the email column is NULL / empty the function
        either returns None or raises.  Neither outcome silently returns a value.
        """
        customer = make_customer(_uid("No Email Cust"))
        ldf = frappe.get_doc("Lead Detail Form", customer.lead_details)
        ldf.email = ""
        ldf.save(ignore_permissions=True)

        try:
            result = get_customer_email(customer.name)
            # Acceptable only if the SQL returned no rows (empty string ≠ match)
            self.assertIsNone(result)
        except (frappe.ValidationError, frappe.DoesNotExistError):
            pass  # Also acceptable – function chose to raise

    def test_email_with_special_characters_is_returned_intact(self):
        customer = make_customer(_uid("Special Email Cust"))
        special_email = "user+tag@sub.example.com"
        self._attach_email_to_ldf(customer, special_email)
        self.assertEqual(get_customer_email(customer.name), special_email)


class TestGenerateToken(CustomerTestBase):
    """
    generate_token() must produce a deterministic, base64url-encoded token
    that embeds the email payload, is HMAC-signed, and strips leading /
    trailing whitespace from the input.
    """

    def _encryption_key_available(self) -> bool:
        return bool(frappe.conf.get("encryption_key"))

    def test_token_is_non_empty_string(self):
        if not self._encryption_key_available():
            self.skipTest("encryption_key not configured")
        token = generate_token("test@example.com")
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)

    def test_same_email_produces_identical_tokens(self):
        if not self._encryption_key_available():
            self.skipTest("encryption_key not configured")
        email = "stable@example.com"
        self.assertEqual(generate_token(email), generate_token(email))

    def test_different_emails_produce_different_tokens(self):
        if not self._encryption_key_available():
            self.skipTest("encryption_key not configured")
        self.assertNotEqual(
            generate_token("user1@example.com"),
            generate_token("user2@example.com"),
        )

    def test_decoded_token_contains_original_email(self):
        """The token must decode to a string that includes the email."""
        if not self._encryption_key_available():
            self.skipTest("encryption_key not configured")
        email = "decode@example.com"
        token = generate_token(email)
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        self.assertIn(email, decoded)

    def test_decoded_token_contains_pipe_separator(self):
        """Token format is '<payload>|<signature>' before base64 encoding."""
        if not self._encryption_key_available():
            self.skipTest("encryption_key not configured")
        token = generate_token("pipe@example.com")
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        self.assertIn("|", decoded)

    def test_whitespace_email_is_stripped_before_signing(self):
        """Leading/trailing whitespace must be normalised: tokens must match."""
        if not self._encryption_key_available():
            self.skipTest("encryption_key not configured")
        t1 = generate_token("stripped@example.com")
        t2 = generate_token("  stripped@example.com  ")
        self.assertEqual(t1, t2)

    def test_token_is_valid_base64url(self):
        """The token must survive a round-trip through base64 urlsafe decoding."""
        if not self._encryption_key_available():
            self.skipTest("encryption_key not configured")
        token = generate_token("b64@example.com")
        try:
            base64.urlsafe_b64decode(token.encode())
        except Exception:
            self.fail("generate_token() did not return valid base64url-encoded data")


class TestUpdateCompanyPercentage(CustomerTestBase):
    """
    update_company_percentage() must persist the supplied value to the
    Lead Detail Form and return the string 'updated'.
    """

    def _get_ldf_for(self, customer: Document) -> Document:
        return frappe.get_doc("Lead Detail Form", customer.lead_details)

    def test_returns_updated_string(self):
        customer = make_customer(_uid("Pct Return"))
        result = update_company_percentage(customer.lead_details, 25)
        self.assertEqual(result, "updated")

    def test_value_is_persisted_in_db(self):
        customer = make_customer(_uid("Pct Persist"))
        update_company_percentage(customer.lead_details, 42)
        db_val = frappe.db.get_value(
            "Lead Detail Form", customer.lead_details, "company_percentage"
        )
        self.assertEqual(float(db_val), 42.0)

    def test_zero_percentage_is_accepted(self):
        customer = make_customer(_uid("Pct Zero"))
        result = update_company_percentage(customer.lead_details, 0)
        self.assertEqual(result, "updated")

    def test_hundred_percentage_is_accepted(self):
        customer = make_customer(_uid("Pct Hundred"))
        result = update_company_percentage(customer.lead_details, 100)
        self.assertEqual(result, "updated")

    def test_sequential_updates_store_latest_value(self):
        customer = make_customer(_uid("Pct Sequential"))
        update_company_percentage(customer.lead_details, 10)
        update_company_percentage(customer.lead_details, 75)
        db_val = frappe.db.get_value(
            "Lead Detail Form", customer.lead_details, "company_percentage"
        )
        self.assertEqual(float(db_val), 75.0)

    def test_nonexistent_lead_name_raises(self):
        with self.assertRaises(Exception):
            update_company_percentage("NonExistentLDF-99999", 50)
