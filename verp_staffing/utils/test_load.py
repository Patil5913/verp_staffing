# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import statistics
import time

import frappe
from frappe.tests.utils import FrappeTestCase


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

    def test_company_insert_performance(self):

        print(
            f"\n[PERF TEST] Inserting "
            f"{self.TOTAL_RECORDS:,} companies "
            f"(will rollback)...\n"
        )

        latencies = []

        success = 0
        errors = 0

        total_start = time.perf_counter()

        try:

            for i in range(self.TOTAL_RECORDS):

                start = time.perf_counter()

                try:

                    company = frappe.get_doc(
                        {
                            "doctype": "Company",
                            "company_name": (
                                f"Load Company {i}"
                            ),
                            "abbr": f"L{i}",
                            "default_currency": "INR",
                            "country": "India",
                        }
                    )

                    company.flags.ignore_mandatory = True
                    company.flags.ignore_links = True

                    company.insert(
                        ignore_permissions=True,
                        ignore_links=True,
                    )

                    success += 1

                except Exception as e:

                    errors += 1

                    print(
                        f"[ERROR] Record {i}: {str(e)}"
                    )

                latency = (
                    time.perf_counter() - start
                ) * 1000

                latencies.append(latency)

                # -------------------------------------------------
                # PROGRESS LOGGING
                # -------------------------------------------------

                if (
                    (i + 1) % self.PRINT_EVERY == 0
                    or (i + 1) == self.TOTAL_RECORDS
                ):

                    avg_latency = statistics.mean(
                        latencies
                    )

                    peak_latency = max(latencies)

                    print(
                        f"{i + 1:,} / "
                        f"{self.TOTAL_RECORDS:,} "
                        f"| avg {avg_latency:.1f} ms "
                        f"| peak {peak_latency:.1f} ms"
                    )

        finally:

            # Rollback immediately after benchmark
            frappe.db.rollback()

            print(
                "\n[ROLLBACK] All inserts have "
                "been rolled back. "
                "DB is unchanged.\n"
            )

        # =====================================================
        # FINAL METRICS
        # =====================================================

        total_time = (
            time.perf_counter() - total_start
        )

        throughput = (
            success / total_time
            if total_time > 0
            else 0
        )

        avg_latency = (
            statistics.mean(latencies)
            if latencies
            else 0
        )

        min_latency = (
            min(latencies)
            if latencies
            else 0
        )

        peak_latency = (
            max(latencies)
            if latencies
            else 0
        )

        # =====================================================
        # SUMMARY
        # =====================================================

        print("\n" + "=" * 55)
        print("               PERFORMANCE TEST SUMMARY")
        print("=" * 55)

        print(f"\nAttempted   : {self.TOTAL_RECORDS:,}")
        print(f"Succeeded   : {success:,}")
        print(f"Errors      : {errors:,}")

        print(f"\nTotal time  : {total_time:.2f} s")
        print(f"Throughput  : {throughput:.1f} docs/s")

        print(f"\nAvg latency : {avg_latency:.1f} ms")
        print(f"Min latency : {min_latency:.1f} ms")
        print(f"Peak latency: {peak_latency:.1f} ms")

        print("\n" + "=" * 55)

        self.assertEqual(errors, 0)
        self.assertEqual(success, self.TOTAL_RECORDS)