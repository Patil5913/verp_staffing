# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import time

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.account.test_account import (
    create_account_if_not_exists,
)
from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
)


class TestLoad(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Reduce noise + slight speed improvement
        frappe.flags.print_messages = False

        # Seed dependencies once
        cls.seed_master_data()

        # Prevent permanent DB commits during load tests
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):

        # Restore original commit function
        frappe.db.commit = cls._original_commit

        # Rollback everything created during tests
        frappe.db.rollback()

        super().tearDownClass()

    @classmethod
    def seed_master_data(cls):

        cls.company = create_company_if_not_exists(
            "Test Company",
            "TC",
        )

        # Create reusable parent account
        parent = create_account_if_not_exists(
            "Load Test Parent Asset",
            company=cls.company,
            root_type="Asset",
            is_group=1,
        )

        cls.parent_account = parent.name

    def test_bulk_account_creation_1k(self):

        start = time.perf_counter()

        created = []

        for i in range(1000):

            acc = create_account_if_not_exists(
                account_name=f"Stress Account {i}",
                company=self.company,
                parent_account=self.parent_account,
                root_type="Asset",
            )

            created.append(acc.name)

        duration = time.perf_counter() - start

        print(
            f"\nCreated {len(created)} accounts "
            f"in {duration:.2f} sec"
        )

        self.assertEqual(len(created), 1000)

    def test_bulk_account_creation_10k(self):

        start = time.perf_counter()

        # Optional benchmarking flags
        frappe.flags.ignore_links = True
        frappe.flags.ignore_account_permission = True

        inserted = 0

        for batch in range(10):

            docs = []

            for i in range(1000):

                idx = (batch * 1000) + i

                docs.append(
                    frappe.get_doc(
                        {
                            "doctype": "Account",
                            "account_name": f"Bulk Account {idx}",
                            "company": self.company,
                            "parent_account": self.parent_account,
                            "root_type": "Asset",
                            "is_group": 0,
                        }
                    )
                )

            for doc in docs:
                doc.insert(ignore_permissions=True)
                inserted += 1

            print(f"Batch {batch + 1}/10 completed")

        duration = time.perf_counter() - start

        print(
            f"\nInserted {inserted} accounts "
            f"in {duration:.2f} sec"
        )

        self.assertEqual(inserted, 10000)