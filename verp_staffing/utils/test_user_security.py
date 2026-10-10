from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import user_security as us
from verp_staffing.utils import user_view as uv


def roles(mapping):
    """frappe.get_roles faked from {user: [roles]}."""
    return mock.patch.object(frappe, "get_roles", side_effect=lambda u=None: mapping.get(u, []))


class TestIsAdmin(FrappeTestCase):
    def test_admin_and_system_manager(self):
        with roles({"sm@x.com": ["System Manager"], "hr@x.com": ["HR Manager"]}):
            self.assertTrue(us.is_admin("Administrator"))
            self.assertTrue(us.is_admin("sm@x.com"))
            self.assertFalse(us.is_admin("hr@x.com"))


class TestCanManageUser(FrappeTestCase):
    HR = "hr@x.com"

    def hr(self, **kw):
        return roles({self.HR: ["HR Manager"], "sm@x.com": ["System Manager"]})

    def test_admins_manage_anyone(self):
        with self.hr():
            self.assertTrue(us.can_manage_user("anyone@x.com", "Administrator"))
            self.assertTrue(us.can_manage_user("sm2@x.com", "sm@x.com"))
            self.assertTrue(us.can_manage_user(self.HR, "sm@x.com"))

    def test_nobody_manages_themselves_or_blank_targets(self):
        with self.hr():
            self.assertFalse(us.can_manage_user(self.HR, self.HR))
            self.assertFalse(us.can_manage_user("", self.HR))
            self.assertFalse(us.can_manage_user(None, self.HR))
            self.assertFalse(us.can_manage_user("new", self.HR))

    def test_system_manager_accounts_are_off_limits_to_others(self):
        with self.hr(), mock.patch.object(frappe.db, "exists", return_value=True):
            self.assertFalse(us.can_manage_user("sm@x.com", self.HR))
        with self.hr():
            self.assertFalse(us.can_manage_user("Administrator", self.HR))

    def test_ordinary_targets_follow_write_permission(self):
        with self.hr(), mock.patch.object(frappe.db, "exists", return_value=False):
            with mock.patch.object(frappe, "has_permission", return_value=True):
                self.assertTrue(us.can_manage_user("emp@x.com", self.HR))
            with mock.patch.object(frappe, "has_permission", return_value=False):
                self.assertFalse(us.can_manage_user("emp@x.com", self.HR))

    def test_assert_variant_throws(self):
        with mock.patch.object(us, "can_manage_user", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                us.assert_can_manage_user("x@x.com")
        with mock.patch.object(us, "can_manage_user", return_value=True):
            us.assert_can_manage_user("x@x.com")


class TestAssignableRoles(FrappeTestCase):
    def test_admin_gets_every_enabled_role(self):
        with roles({"sm@x.com": ["System Manager"]}), mock.patch.object(frappe, "get_all", return_value=["A", "B"]):
            self.assertEqual(us.assignable_roles("sm@x.com"), {"A", "B"})

    def test_others_get_only_what_they_hold_minus_privileged_ones(self):
        with roles({"hr@x.com": ["HR Manager", "Sales", "System Manager", "All", "Guest", "Administrator"]}):
            pass
        with roles({"hr@x.com": ["HR Manager", "Sales", "All", "Guest"]}):
            self.assertEqual(us.assignable_roles("hr@x.com"), {"HR Manager", "Sales"})


class TestGuardUserSave(FrappeTestCase):
    def doc(self, before_roles=(), new_roles=(), before=True, **fields):
        d = mock.MagicMock()
        d.name = "target@x.com"
        d.flags.ignore_permissions = False
        d.get.side_effect = lambda k, default=None: {
            "roles": [SimpleNamespace(role=r) for r in new_roles],
            **fields,
        }.get(k, default)
        if before:
            b = mock.MagicMock()
            b.get.side_effect = lambda k, default=None: {"roles": [SimpleNamespace(role=r) for r in before_roles]}.get(k, default)
            d.get_doc_before_save.return_value = b
        else:
            d.get_doc_before_save.return_value = None
        return d

    def run_guard(self, doc, actor="hr@x.com", admin=False, can_manage=True, assignable=()):
        with mock.patch.object(us, "is_admin", return_value=admin), \
             mock.patch.object(us, "can_manage_user", return_value=can_manage), \
             mock.patch.object(us, "assignable_roles", return_value=set(assignable)):
            us.guard_user_save(doc)

    def test_skipped_for_system_contexts(self):
        d = self.doc(new_roles=["System Manager"])
        d.flags.ignore_permissions = True
        self.run_guard(d, can_manage=False)
        for flag in ("in_install", "in_patch", "in_migrate", "in_import", "in_test"):
            d = self.doc(new_roles=["System Manager"])
            setattr(frappe.flags, flag, True)
            try:
                if flag != "in_test":  # the suite itself runs with in_test set
                    self.run_guard(d, can_manage=False)
            finally:
                setattr(frappe.flags, flag, flag == "in_test")

    def test_admins_unrestricted(self):
        with mock.patch.dict(frappe.flags, {"in_test": False}):
            self.run_guard(self.doc(new_roles=["System Manager"]), admin=True, can_manage=False)

    def test_role_changes_need_manage_rights_and_assignable_roles(self):
        with mock.patch.dict(frappe.flags, {"in_test": False}):
            with self.assertRaises(frappe.PermissionError):
                self.run_guard(self.doc(new_roles=["Sales"]), can_manage=False, assignable=["Sales"])
            with self.assertRaises(frappe.PermissionError):
                self.run_guard(self.doc(new_roles=["System Manager"]), assignable=["Sales"])
            with self.assertRaises(frappe.PermissionError):
                self.run_guard(self.doc(before_roles=["System Manager"], new_roles=[]), assignable=["Sales"])
            self.run_guard(self.doc(before_roles=["Sales"], new_roles=["Sales", "HR"]), assignable=["HR"])

    def test_new_users_skip_the_manage_check_but_not_the_assignable_one(self):
        with mock.patch.dict(frappe.flags, {"in_test": False}):
            self.run_guard(self.doc(new_roles=["Sales"], before=False), can_manage=False, assignable=["Sales"])
            with self.assertRaises(frappe.PermissionError):
                self.run_guard(self.doc(new_roles=["System Manager"], before=False), can_manage=False, assignable=["Sales"])

    def test_security_fields_need_manage_rights(self):
        with mock.patch.dict(frappe.flags, {"in_test": False}):
            d = self.doc(before_roles=["Sales"], new_roles=["Sales"], enabled=0)
            d.get_doc_before_save.return_value.get.side_effect = lambda k, default=None: {"roles": [SimpleNamespace(role="Sales")], "enabled": 1}.get(k, default)
            with self.assertRaises(frappe.PermissionError):
                self.run_guard(d, can_manage=False)
            self.run_guard(d, can_manage=True)

    def test_unchanged_security_fields_are_fine(self):
        with mock.patch.dict(frappe.flags, {"in_test": False}):
            d = self.doc(before_roles=["Sales"], new_roles=["Sales"])
            self.run_guard(d, can_manage=False)

    def test_security_fields_list_covers_the_critical_ones(self):
        for f in ("enabled", "user_type", "restrict_ip", "simultaneous_sessions"):
            self.assertIn(f, us.SECURITY_FIELDS)


class TestUserViewEndpoints(FrappeTestCase):
    def test_controls_for_a_new_user_follow_create_permission(self):
        with mock.patch.object(frappe, "has_permission", return_value=True), mock.patch.object(uv, "assignable_roles", return_value={"B", "A"}):
            out = uv.get_user_controls("new")
        self.assertTrue(out["can_manage"])
        self.assertEqual(out["assignable_roles"], ["A", "B"])
        self.assertFalse(out["is_self"])

    def test_controls_for_yourself(self):
        me = frappe.session.user
        with mock.patch.object(uv, "can_manage_user", return_value=False):
            out = uv.get_user_controls(me)
        self.assertTrue(out["is_self"] and out["can_change_own_password"] and out["can_send_reset"])
        self.assertFalse(out["can_manage"] or out["can_view_roles"])
        self.assertEqual(out["assignable_roles"], [])

    def test_cannot_disable_yourself_or_administrator(self):
        doc = SimpleNamespace(name=frappe.session.user)
        with mock.patch.object(uv, "_get_user_for_write", return_value=doc):
            with self.assertRaises(frappe.ValidationError):
                uv.set_user_enabled(frappe.session.user, 0)
        with mock.patch.object(uv, "_get_user_for_write", return_value=SimpleNamespace(name="Administrator")):
            with self.assertRaises(frappe.ValidationError):
                uv.set_user_enabled("Administrator", 0)

    def test_disable_really_disables(self):
        doc = mock.MagicMock()
        doc.name = "other@x.com"
        with mock.patch.object(uv, "_get_user_for_write", return_value=doc):
            self.assertEqual(uv.set_user_enabled("other@x.com", "0"), {"enabled": False})
        self.assertEqual(doc.enabled, 0)
        doc.save.assert_called_once()

    def test_roles_cannot_be_changed_beyond_what_you_may_assign(self):
        doc = mock.MagicMock()
        doc.roles = [SimpleNamespace(role="Sales")]
        with mock.patch.object(uv, "_get_user_for_write", return_value=doc), \
             mock.patch.object(frappe, "get_all", return_value=["Sales", "HR", "System Manager"]), \
             mock.patch.object(uv, "assignable_roles", return_value={"Sales", "HR"}):
            with self.assertRaises(frappe.PermissionError):
                uv.set_user_roles("t@x.com", '["Sales", "System Manager"]')
            doc.save.assert_not_called()

    def test_roles_overwrite_and_drop_unknown_roles(self):
        doc = mock.MagicMock()
        doc.roles = [SimpleNamespace(role="Sales")]
        with mock.patch.object(uv, "_get_user_for_write", return_value=doc), \
             mock.patch.object(frappe, "get_all", return_value=["Sales", "HR"]), \
             mock.patch.object(uv, "assignable_roles", return_value={"Sales", "HR"}), \
             mock.patch.object(uv, "get_roles_matrix", return_value={"ok": 1}):
            self.assertEqual(uv.set_user_roles("t@x.com", ["HR", "Ghost"]), {"ok": 1})
        doc.set.assert_called_once_with("roles", [])
        doc.append.assert_called_once_with("roles", {"role": "HR"})
        doc.save.assert_called_once()

    def test_get_user_for_write_requires_permission_and_manage_rights(self):
        doc = mock.MagicMock()
        doc.has_permission.return_value = False
        with mock.patch.object(frappe, "get_doc", return_value=doc):
            with self.assertRaises(frappe.PermissionError):
                uv._get_user_for_write("t@x.com")
        doc.has_permission.return_value = True
        with mock.patch.object(frappe, "get_doc", return_value=doc), mock.patch.object(uv, "assert_can_manage_user", side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                uv._get_user_for_write("t@x.com")

    def test_password_rules(self):
        with self.assertRaises(frappe.ValidationError):
            uv.set_new_password("x@x.com", "")
        with self.assertRaises(frappe.ValidationError):
            uv.set_new_password(frappe.session.user, "newpass")  # your own password needs the current one
        with mock.patch("frappe.utils.password.check_password", side_effect=frappe.AuthenticationError) as check:
            with self.assertRaises(frappe.AuthenticationError):
                uv.set_new_password(frappe.session.user, "newpass", "wrong")
            check.assert_called_once()

    def test_changing_someone_elses_password_needs_manage_rights(self):
        with mock.patch.object(uv, "_get_user_for_write", side_effect=frappe.PermissionError), mock.patch("frappe.utils.password.update_password") as upd:
            with self.assertRaises(frappe.PermissionError):
                uv.set_new_password("other@x.com", "newpass")
            upd.assert_not_called()
        with mock.patch.object(uv, "_get_user_for_write"), mock.patch("frappe.utils.password.update_password") as upd:
            self.assertEqual(uv.set_new_password("other@x.com", "newpass"), {"ok": True})
            upd.assert_called_once_with("other@x.com", "newpass")

    def test_reset_email_rules(self):
        doc = mock.MagicMock()
        doc.name, doc.enabled = "Administrator", 1
        with mock.patch.object(uv, "assert_can_manage_user"), mock.patch.object(frappe, "get_doc", return_value=doc):
            with self.assertRaises(frappe.ValidationError):
                uv.send_reset_email("Administrator")
        doc.name, doc.enabled = "t@x.com", 0
        with mock.patch.object(uv, "assert_can_manage_user"), mock.patch.object(frappe, "get_doc", return_value=doc):
            with self.assertRaises(frappe.ValidationError):
                uv.send_reset_email("t@x.com")
        doc.enabled = 1
        with mock.patch.object(uv, "assert_can_manage_user"), mock.patch.object(frappe, "get_doc", return_value=doc):
            self.assertEqual(uv.send_reset_email("t@x.com"), {"ok": True})
        doc._reset_password.assert_called_once_with(send_email=True)
