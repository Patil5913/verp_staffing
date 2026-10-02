# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import statistics
import time

import frappe
from frappe.tests.utils import FrappeTestCase
from verp_staffing.accounts.doctype.account.test_account import create_account_if_not_exists


class TestLoad(FrappeTestCase):

    TOTAL_RECORDS = 100
    PRINT_EVERY = 10

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        frappe.flags.print_messages = False

        # Disable commits
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

        # Optional benchmark flags
        frappe.flags.in_load_test = True
        frappe.flags.ignore_links = True

    @classmethod
    def tearDownClass(cls):

        # Restore commits
        frappe.db.commit = cls._original_commit

        # Rollback everything
        frappe.db.rollback()

        super().tearDownClass()

    def test_account_insert_performance(self):

        print(
            f"\n[PERF TEST] Inserting "
            f"{self.TOTAL_RECORDS:,} accounts "
            f"(will rollback)...\n"
        )

        latencies = []
        success = 0
        errors = 0
        total_start = time.perf_counter()

        # Create a base company ONCE (not part of benchmark)
        company = frappe.get_doc(
            {
                "doctype": "Company",
                "company_name": "Benchmark Company",
                "abbr": "BC",
                "default_currency": "INR",
                "country": "India",
            }
        )

        company.flags.ignore_mandatory = True
        company.flags.ignore_links = True
        company.insert(ignore_permissions=True, ignore_links=True)

        try:
            for i in range(self.TOTAL_RECORDS):

                start = time.perf_counter()

                try:
                    # =========================
                    # ACCOUNT SEEDING ONLY
                    # =========================
                    account = create_account_if_not_exists(
                        account_name=f"Test Account {i}",
                        company=company.name,
                        root_type="Asset",
                        account_type=None,
                        is_group=0,
                    )

                    success += 1

                except Exception as e:
                    errors += 1
                    print(f"[ERROR] Record {i}: {str(e)}")

                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)

                if (
                    (i + 1) % self.PRINT_EVERY == 0
                    or (i + 1) == self.TOTAL_RECORDS
                ):
                    print(
                        f"{i + 1:,} / {self.TOTAL_RECORDS:,} "
                        f"| avg {statistics.mean(latencies):.1f} ms "
                        f"| peak {max(latencies):.1f} ms"
                    )

        finally:
            frappe.db.rollback()

            print(
                "\n[ROLLBACK] All inserts have been rolled back. "
                "DB is unchanged.\n"
            )

        total_time = time.perf_counter() - total_start

        print("\n" + "=" * 55)
        print("        ACCOUNT SEED PERFORMANCE SUMMARY")
        print("=" * 55)

        print(f"\nAttempted   : {self.TOTAL_RECORDS:,}")
        print(f"Succeeded   : {success:,}")
        print(f"Errors      : {errors:,}")

        print(f"\nTotal time  : {total_time:.2f} s")
        print(f"Throughput  : {success / total_time:.1f} docs/s")

        print(f"\nAvg latency : {statistics.mean(latencies):.1f} ms")
        print(f"Min latency : {min(latencies):.1f} ms")
        print(f"Peak latency: {max(latencies):.1f} ms")

        print("\n" + "=" * 55)

        self.assertEqual(errors, 0)
        self.assertEqual(success, self.TOTAL_RECORDS)