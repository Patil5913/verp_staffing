# import time
# import statistics
# import frappe
# from frappe.tests.utils import FrappeTestCase


# class TestEmployeeLoad(FrappeTestCase):

#     TOTAL_RECORDS = 5000
#     BATCH_SIZE = 250
#     PRINT_EVERY = 500

#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()

#         frappe.flags.in_load_test = True
#         frappe.flags.print_messages = False

#         # IMPORTANT: do NOT disable commit globally
#         cls._original_commit = frappe.db.commit

#     @classmethod
#     def tearDownClass(cls):

#         frappe.db.commit = cls._original_commit
#         frappe.db.rollback()

#         super().tearDownClass()

#     def create_employee_payload(self, i, user, department, role):
#         return {
#             "doctype": "Employee",
#             "user": user,
#             "employee_name": f"Benchmark Employee {i}",
#             "enabled": 1,
#             "employee_assignment_details_table": [
#                 {
#                     "department": department,
#                     "designation": role,
#                     "assigned_to": None,
#                 }
#             ],
#         }

#     def test_employee_production_performance(self):

#         print(
#             f"\n[PRODUCTION BENCHMARK] "
#             f"{self.TOTAL_RECORDS:,} Employees "
#             f"in batches of {self.BATCH_SIZE}\n"
#         )

#         latencies = []
#         success = 0
#         errors = 0

#         start_time = time.perf_counter()

#         # ----------------------------
#         # Use existing stable data
#         # ----------------------------
#         user = frappe.db.get_value("User", {"enabled": 1}, "name")
#         department = frappe.db.get_value("Department", {}, "name")
#         role = frappe.db.get_value("Role", {}, "name")

#         if not (user and department and role):
#             self.fail("Missing base test data (User/Department/Role)")

#         try:
#             for i in range(self.TOTAL_RECORDS):

#                 t0 = time.perf_counter()

#                 try:
#                     emp = frappe.get_doc(
#                         self.create_employee_payload(
#                             i, user, department, role
#                         )
#                     )

#                     emp.flags.ignore_permissions = True
#                     emp.flags.ignore_links = True
#                     emp.flags.ignore_mandatory = True

#                     emp.insert(
#                         ignore_permissions=True,
#                         ignore_links=True,
#                     )

#                     success += 1

#                 except Exception as e:
#                     errors += 1
#                     print(f"[ERROR] {i}: {e}")

#                 latencies.append((time.perf_counter() - t0) * 1000)

#                 # ----------------------------
#                 # REALISTIC COMMIT BATCHING
#                 # ----------------------------
#                 if (i + 1) % self.BATCH_SIZE == 0:
#                     frappe.db.commit()

#                 if (i + 1) % self.PRINT_EVERY == 0:
#                     print(
#                         f"{i+1:,}/{self.TOTAL_RECORDS:,} "
#                         f"| avg {statistics.mean(latencies):.1f} ms "
#                         f"| peak {max(latencies):.1f} ms"
#                     )

#         finally:
#             frappe.db.rollback()

#         total_time = time.perf_counter() - start_time

#         print("\n" + "=" * 60)
#         print("     EMPLOYEE PRODUCTION BENCHMARK RESULTS")
#         print("=" * 60)

#         print(f"\nAttempted   : {self.TOTAL_RECORDS:,}")
#         print(f"Succeeded   : {success:,}")
#         print(f"Errors      : {errors:,}")

#         print(f"\nTotal time  : {total_time:.2f} s")
#         print(f"Throughput  : {success / total_time:.2f} docs/sec")

#         print(f"\nAvg latency : {statistics.mean(latencies):.2f} ms")
#         print(f"Min latency : {min(latencies):.2f} ms")
#         print(f"Max latency : {max(latencies):.2f} ms")

#         print("\n" + "=" * 60)

#         self.assertEqual(errors, 0)
#         self.assertEqual(success, self.TOTAL_RECORDS)