from unittest import mock

from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import hierarchy_roles as hr

DATA = [
    {"parent_role": " Manager ", "child_roles": ["Lead", " Exec ", "", None]},
    {"parent_role": "Director", "child_roles": ["Manager", "Lead"]},
    {"parent_role": "", "child_roles": ["Orphan"]},
    {"parent_role": "Solo"},
]


class TestHierarchyHelpers(FrappeTestCase):
    def test_get_hierarchy_roles_strips_and_collects(self):
        self.assertEqual(hr.get_hierarchy_roles(DATA), {"Manager", "Lead", "Exec", "Director", "Orphan", "Solo"})

    def test_get_hierarchy_roles_empty(self):
        self.assertEqual(hr.get_hierarchy_roles([]), set())

    def test_build_parent_map(self):
        self.assertEqual(
            hr.build_parent_map(DATA),
            {"Lead": {"Manager", "Director"}, "Exec": {"Manager"}, "Manager": {"Director"}},
        )

    def test_get_changed_roles(self):
        old = [{"parent_role": "A", "child_roles": ["B", "C"]}]
        new = [{"parent_role": "A", "child_roles": ["B"]}, {"parent_role": "D", "child_roles": ["C"]}]
        self.assertEqual(hr.get_changed_roles(old, new), {"C"})
        self.assertEqual(hr.get_changed_roles(old, old), set())

    def test_get_department_roles_drops_blank(self):
        rows = [mock.Mock(role="A"), mock.Mock(role=None), mock.Mock(role="B")]
        with mock.patch.object(hr.frappe, "get_all", return_value=rows):
            self.assertEqual(hr.get_department_roles("Dept"), {"A", "B"})
