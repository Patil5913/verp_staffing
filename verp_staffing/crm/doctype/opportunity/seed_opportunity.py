import statistics
import time

import frappe
from frappe.tests.utils import FrappeTestCase


class TestOpportunityLoad(FrappeTestCase):

    TOTAL_RECORDS = 10000
    PRINT_EVERY = 1000

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        frappe.flags.print_messages = False
        frappe.flags.in_load_test = True
        frappe.flags.ignore_links = True

        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()
        super().tearDownClass()

    def test_opportunity_insert_performance(self):

        print(
            f"\n[PERF TEST] Inserting "
            f"{self.TOTAL_RECORDS:,} opportunities "
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

                    opportunity = frappe.get_doc(
                        {
                            "doctype": "Opportunity",

                            # Core required field
                            "name1": f"Opportunity {i}",

                            # Core workflow fields
                            "status": "Open",
                            "sales_stage": "Prospecting",
                            "currency": "USD",

                            # Optional but realistic load simulation
                            "opportunity_amount": 1000 + i,
                            "probability_": 10,
                            "expected_closing_date": frappe.utils.add_days(
                                frappe.utils.today(),
                                30,
                            ),

                            # Links (keep minimal to avoid external dependency cost)
                            "opportunity_owner": None,
                            "source": None,
                        }
                    )

                    # benchmark flags
                    opportunity.flags.ignore_links = True
                    opportunity.flags.ignore_mandatory = True
                    opportunity.flags.ignore_permissions = True

                    opportunity.insert(
                        ignore_permissions=True,
                        ignore_links=True,
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
            print("\n[ROLLBACK] All inserts rolled back.\n")

        total_time = time.perf_counter() - total_start

        throughput = success / total_time if total_time else 0

        print("\n" + "=" * 55)
        print("      OPPORTUNITY SEED PERFORMANCE SUMMARY")
        print("=" * 55)

        print(f"\nAttempted   : {self.TOTAL_RECORDS:,}")
        print(f"Succeeded   : {success:,}")
        print(f"Errors      : {errors:,}")

        print(f"\nTotal time  : {total_time:.2f} s")
        print(f"Throughput  : {throughput:.1f} docs/s")

        print(f"\nAvg latency : {statistics.mean(latencies):.1f} ms")
        print(f"Min latency : {min(latencies):.1f} ms")
        print(f"Peak latency: {max(latencies):.1f} ms")

        print("\n" + "=" * 55)

        self.assertEqual(errors, 0)
        self.assertEqual(success, self.TOTAL_RECORDS)