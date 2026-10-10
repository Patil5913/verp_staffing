from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.quota.utils import quota


def site_config(**quota_cfg):
    return mock.patch.object(frappe, "get_site_config", return_value={"quota": quota_cfg})


class TestUserLimit(FrappeTestCase):
    def test_non_integer_limit_throws(self):
        with site_config(users_limit="10"):
            with self.assertRaises(frappe.ValidationError):
                quota.user_limit()
        with site_config():
            with self.assertRaises(frappe.ValidationError):
                quota.user_limit()

    def test_chat_external_user_does_not_use_a_seat(self):
        doc = frappe._dict(roles=[frappe._dict(role="Chat External")])
        with site_config(users_limit="bad"):
            quota.user_limit(doc)  # returns before the limit is even read

    def test_under_limit_passes(self):
        with site_config(users_limit=10), mock.patch.object(frappe.db, "sql", return_value=[[3]]):
            quota.user_limit()

    def test_at_limit_notifies_and_throws(self):
        with site_config(users_limit=3), mock.patch.object(frappe.db, "sql", return_value=[[3]]), \
             mock.patch.object(frappe.db, "get_value", return_value=None), \
             mock.patch.object(quota, "send_notification") as notify:
            with self.assertRaises(frappe.ValidationError):
                quota.user_limit()
        notify.assert_called_once()
        self.assertEqual(notify.call_args.kwargs["recipients"], ["Administrator"])


class TestStorageCounter(FrappeTestCase):
    def setUp(self):
        self.store = {}
        cache = mock.Mock()
        cache.get_value.side_effect = lambda k: self.store.get(k)
        cache.set_value.side_effect = lambda k, v, **kw: self.store.__setitem__(k, v)
        p = mock.patch.object(frappe, "cache", return_value=cache)
        p.start()
        self.addCleanup(p.stop)

    def test_cold_start_reconciles_from_db(self):
        with mock.patch.object(frappe.db, "sql", return_value=[[1234]]):
            self.assertEqual(quota.get_files_bytes(), 1234)
        self.assertEqual(self.store[quota.STORAGE_CACHE_KEY], 1234)

    def test_insert_and_delete_adjust_the_counter(self):
        self.store[quota.STORAGE_CACHE_KEY] = 100
        quota.on_file_after_insert(frappe._dict(is_folder=0, file_size=50))
        self.assertEqual(self.store[quota.STORAGE_CACHE_KEY], 150)
        quota.on_file_after_delete(frappe._dict(is_folder=0, file_size=70))
        self.assertEqual(self.store[quota.STORAGE_CACHE_KEY], 80)

    def test_counter_never_goes_negative(self):
        self.store[quota.STORAGE_CACHE_KEY] = 10
        quota.on_file_after_delete(frappe._dict(is_folder=0, file_size=999))
        self.assertEqual(self.store[quota.STORAGE_CACHE_KEY], 0)

    def test_folders_and_missing_sizes_are_ignored(self):
        self.store[quota.STORAGE_CACHE_KEY] = 10
        quota.on_file_after_insert(frappe._dict(is_folder=1, file_size=500))
        quota.on_file_after_insert(frappe._dict(is_folder=0, file_size=None))
        self.assertEqual(self.store[quota.STORAGE_CACHE_KEY], 10)

    def test_db_size_is_cached(self):
        with mock.patch.object(frappe.db, "sql", return_value=[[2048]]) as sql:
            self.assertEqual(quota.get_db_size_bytes(), 2048)
            self.assertEqual(quota.get_db_size_bytes(), 2048)
        self.assertEqual(sql.call_count, 1)

    def test_backups_bytes_defaults_to_zero(self):
        self.assertEqual(quota.get_backups_bytes(), 0)


class TestSiteSpaceLimit(FrappeTestCase):
    GB = 1024**3

    def run_with(self, limit, files=0, db=0, backups=0):
        with site_config(site_space_limit_gb=limit), \
             mock.patch.object(quota, "get_files_bytes", return_value=files), \
             mock.patch.object(quota, "get_db_size_bytes", return_value=db), \
             mock.patch.object(quota, "get_backups_bytes", return_value=backups), \
             mock.patch.object(frappe, "enqueue") as enqueue:
            try:
                quota.site_space_limit()
            finally:
                self.enqueue = enqueue

    def test_non_numeric_limit_throws(self):
        with site_config(site_space_limit_gb="5"):
            with self.assertRaises(frappe.ValidationError):
                quota.site_space_limit()

    def test_under_limit_passes(self):
        self.run_with(5, files=self.GB, db=self.GB)
        self.enqueue.assert_not_called()

    def test_files_db_and_backups_all_count(self):
        with self.assertRaises(frappe.ValidationError):
            self.run_with(2, files=self.GB, db=self.GB, backups=self.GB)
        self.enqueue.assert_called_once()

    def test_enqueued_notifier_exists(self):
        """The job path handed to enqueue must resolve to a real function."""
        with self.assertRaises(frappe.ValidationError):
            self.run_with(1, files=2 * self.GB)
        path = self.enqueue.call_args.args[0]
        self.assertIs(frappe.get_attr(path), quota.notify_limit_exceeded)


class TestExpiry(FrappeTestCase):
    def test_block_non_admin(self):
        with mock.patch.object(frappe.local, "conf", frappe._dict(archive_mode=0)):
            quota.block_non_admin()  # not in archive mode: nothing happens
        login = mock.Mock()
        with mock.patch.object(frappe.local, "conf", frappe._dict(archive_mode=1)), \
             mock.patch.object(frappe.local, "login_manager", login, create=True), \
             mock.patch.object(frappe, "msgprint"):
            prev = frappe.session.user
            try:
                frappe.session.user = "Administrator"
                quota.block_non_admin()
                login.logout.assert_not_called()
                frappe.session.user = "someone@x.com"
                quota.block_non_admin()
                login.logout.assert_called_once()
            finally:
                frappe.session.user = prev

    def test_check_site_expiry_only_in_last_five_days(self):
        from frappe.utils import add_days, nowdate

        def run(days):
            with site_config(expiry_date=add_days(nowdate(), days)), \
                 mock.patch.object(frappe, "get_all", return_value=[]), \
                 mock.patch.object(frappe.db, "get_value", return_value=None), \
                 mock.patch.object(quota, "send_notification") as notify, \
                 mock.patch.object(frappe, "publish_realtime"):
                quota.check_site_expiry()
                return notify

        run(3).assert_called_once()
        run(6).assert_not_called()
        run(0).assert_not_called()
        run(-2).assert_not_called()

    def test_check_site_expiry_without_config_is_noop(self):
        with site_config(), mock.patch.object(quota, "send_notification") as notify:
            quota.check_site_expiry()
        notify.assert_not_called()

    def test_site_expiry_check_archives_expired_sites(self):
        from frappe.utils import add_days, nowdate

        login = mock.Mock()
        with site_config(expiry_date=add_days(nowdate(), -1)), \
             mock.patch.object(quota, "enable_archive_mode") as archive, \
             mock.patch.object(frappe.local, "login_manager", login, create=True), \
             mock.patch.object(frappe, "msgprint"):
            quota.site_expiry_check()
        archive.assert_called_once()
        login.logout.assert_called_once()

    def test_site_expiry_check_leaves_live_sites_alone(self):
        from frappe.utils import add_days, nowdate

        with site_config(expiry_date=add_days(nowdate(), 30)), mock.patch.object(quota, "enable_archive_mode") as archive:
            quota.site_expiry_check()
        archive.assert_not_called()
