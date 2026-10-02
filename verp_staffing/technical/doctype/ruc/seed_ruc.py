# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import statistics
import time

import frappe
from frappe.tests.utils import FrappeTestCase


class TestLoad(FrappeTestCase):

    TOTAL_RECORDS = 10000
    PRINT_EVERY = 1000

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        frappe.flags.print_messages = False
        frappe.flags.in_load_test = True
        frappe.flags.ignore_links = True

        # Disable commits during benchmark
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

        # ==========================================
        # Create benchmark customers once
        # ==========================================

        cls.customers = []

        for i in range(cls.TOTAL_RECORDS):

            customer = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "name1": f"Benchmark Customer {i}",
                }
            )

            customer.flags.ignore_permissions = True
            customer.flags.ignore_links = True
            customer.flags.ignore_mandatory = True

            customer.insert(
                ignore_permissions=True,
                ignore_links=True,
            )

            cls.customers.append(customer.name)

    @classmethod
    def tearDownClass(cls):

        frappe.db.commit = cls._original_commit

        frappe.db.rollback()

        super().tearDownClass()

    def test_ruc_insert_performance(self):

        print(
            f"\n[PERF TEST] Inserting "
            f"{self.TOTAL_RECORDS:,} RUC docs "
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

                    ruc = frappe.get_doc(
                        {
                            "doctype": "RUC",
                            "customer": self.customers[i],
                            "status": "Pending",
                        }
                    )

                    ruc.flags.ignore_permissions = True
                    ruc.flags.ignore_links = True
                    ruc.flags.ignore_mandatory = True

                    ruc.insert(
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

                # ==========================================
                # PROGRESS LOGGING
                # ==========================================

                if (
                    (i + 1) % self.PRINT_EVERY == 0
                    or (i + 1) == self.TOTAL_RECORDS
                ):

                    print(
                        f"{i + 1:,} / "
                        f"{self.TOTAL_RECORDS:,} "
                        f"| avg {statistics.mean(latencies):.1f} ms "
                        f"| peak {max(latencies):.1f} ms"
                    )

        finally:

            frappe.db.rollback()

            print(
                "\n[ROLLBACK] All inserts have "
                "been rolled back. "
                "DB is unchanged.\n"
            )

        # ==========================================
        # FINAL METRICS
        # ==========================================

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

        # ==========================================
        # SUMMARY
        # ==========================================

        print("\n" + "=" * 55)
        print("         RUC SEED PERFORMANCE SUMMARY")
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