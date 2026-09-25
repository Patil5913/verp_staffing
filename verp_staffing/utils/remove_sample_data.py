# import frappe
# from frappe import _
# from verp_staffing.utils.sample_data_guard import _get_linked_documents
# from verp_staffing.utils.sample_data_tracking import (
# 	get_all_sample_records,
# 	remove_from_log,
# 	mark_sample_data_removed,
# )

# # Reverse of the creation order in sample_data.create_sample_data().
# # This is the ONLY set of doctypes this tool will ever auto-process
# # from the tracked-sample bucket - see safety note (1) above.
# DELETE_ORDER = [
# 	"Comment",
# 	"Journal Entry",
# 	"Payment Entry",
# 	"Subscription",
# 	"Subscription Plan",
# 	"Purchase Invoice",
# 	"Purchase Order",
# 	"Sales Invoice",
# 	"Interview",
# 	"Marketing",
# 	"Resume",
# 	"Cover Letter",
# 	"Training",
# 	"RUC",
# 	"Sales Order",
# 	"Lead Detail Form",  # auto-created alongside Lead/Customer/Opportunity - must go before them
# 	"Item",
# 	"Customer",
# 	"Opportunity",
# 	"Lead",
# 	"Supplier",
# 	"Employee",
# 	"User",
# ]

# # Doctypes whose records get created/removed automatically as a side
# # effect of their parent transaction being submitted/cancelled -
# # they're not documents anyone created "on top of" sample data, so
# # surfacing them as conflicts is just noise (the real originating
# # document, if any, already shows up as its own conflict row).
# # "Comment" belongs here too: Frappe auto-logs "You created this" /
# # "value changed" entries as Comments on virtually every document, so
# # treating those as real conflicts just re-introduces the same clutter
# # GL Entry and View Log were filtered out for.
# CONFLICT_NOISE_DOCTYPES = {
# 	"GL Entry",
# 	"View Log",
# 	"Version",
# 	"Activity Log",
# 	"Notification Log",
# 	"Email Queue",
# 	"Document Follow",
# 	"Access Log",
# 	"Route History",
# 	"Deleted Document",
# }

# # Doctypes this tool will NEVER touch, under any circumstance,
# # regardless of what the log or the conflict scan says - checked
# # directly in _safe_delete(), not just filtered from the UI. Ledger/
# # audit-integrity doctypes and core system doctypes live here.
# #
# # Payment Entry, Journal Entry, Sales Invoice, and Purchase Invoice
# # are deliberately NOT here, even though this tool will never fully
# # delete them either - see the module docstring. They still need to
# # go through _safe_delete() so they get cancelled; putting them here
# # would skip that entirely, which is exactly the bug this file is
# # fixing.
# PROTECTED_DOCTYPES = CONFLICT_NOISE_DOCTYPES | {
# 	"Payment Entry",
# 	"DocType",
# 	"Role",
# 	"User Permission",
# 	"Company",
# 	"Fiscal Year",
# 	"Account",
# 	"Item Category",
# 	"Supplier Group",
# 	"Department",
# 	"Role Profile",
# 	"ERP Configuration",
# }

# # Fields checked, in order, when a delete is blocked by a real
# # remaining link and we fall back to disabling instead - matches
# # Frappe's own "You can disable this X instead of deleting it."
# # suggestion in that error message.
# DISABLE_FIELD_CANDIDATES = [
# 	("disabled", 1),
# 	("enabled", 0),
# ]

# # Sample data seeding produces on the order of a few dozen records.
# # If a single removal run ever targets far more than that, refuse
# # instead of proceeding.
# MAX_AUTO_DELETE = 500


# def get_sample_data_conflicts():
# 	"""-> [{sample_doctype, sample_name, linked_doctype, linked_name}, ...]
# 	for every link into a sample record that comes from a document
# 	that is itself NOT sample data - i.e. would be affected if the
# 	sample data is removed."""
# 	sample_records = get_all_sample_records()
# 	sample_lookup = {(dt, n) for dt, names in sample_records.items() for n in names}

# 	conflicts = []
# 	for doctype, names in sample_records.items():
# 		for name in names:
# 			for linked_doctype, linked_name in _get_linked_documents(doctype, name):
# 				if linked_doctype in CONFLICT_NOISE_DOCTYPES:
# 					continue
# 				if (linked_doctype, linked_name) in sample_lookup:
# 					continue  # internal to the sample set - not a real conflict
# 				conflicts.append(
# 					{
# 						"sample_doctype": doctype,
# 						"sample_name": name,
# 						"linked_doctype": linked_doctype,
# 						"linked_name": linked_name,
# 					}
# 				)
# 	return conflicts


# def get_summary():
# 	records = get_all_sample_records()
# 	unexpected_doctypes = sorted(set(records.keys()) - set(DELETE_ORDER))
# 	return {
# 		"counts": {dt: len(names) for dt, names in records.items()},
# 		"total": sum(len(names) for names in records.values()),
# 		"records": records,  # full breakdown so the UI can show exactly what's targeted
# 		"conflicts": get_sample_data_conflicts(),
# 		"unexpected_doctypes": unexpected_doctypes,
# 	}


# def _try_disable(doctype, name):
# 	"""Fallback for when a delete is blocked by a real remaining link.
# 	Mirrors Frappe's own suggested remedy in that error message.
# 	Returns the field name used, or None if this doctype has neither."""
# 	try:
# 		meta = frappe.get_meta(doctype)
# 	except Exception:
# 		return None
# 	fieldnames = {df.fieldname for df in meta.fields if df.fieldtype == "Check"}

# 	for field, value in DISABLE_FIELD_CANDIDATES:
# 		if field in fieldnames:
# 			frappe.db.set_value(doctype, name, field, value)
# 			return field
# 	return None


# def _safe_delete(doctype, name):
# 	"""Returns one of: "already_gone", "cancelled", "deleted", "disabled".
# 	Raises on any outcome that isn't one of those."""
# 	if doctype in PROTECTED_DOCTYPES:
# 		raise frappe.ValidationError(f"{doctype} is protected and cannot be touched by this tool")

# 	if not frappe.db.exists(doctype, name):
# 		return "already_gone"

# 	doc = frappe.get_doc(doctype, name)

# 	if doc.meta.is_submittable and doc.docstatus == 1:
# 		doc.cancel()
# 		# See the module docstring: a document that was actually
# 		# submitted may have permanent GL Entry rows or be referenced
# 		# by other submitted vouchers. Cancelling is the correct
# 		# "removed" state here - deliberately NOT attempting
# 		# frappe.delete_doc() on it afterward.
# 		return "cancelled"

# 	try:
# 		frappe.delete_doc(doctype, name, ignore_permissions=True, ignore_missing=True)
# 		return "deleted"
# 	except frappe.LinkExistsError:
# 		disabled_field = _try_disable(doctype, name)
# 		if disabled_field:
# 			return "disabled"
# 		raise


# def _error_reason(exc):
# 	msg = str(exc).strip()
# 	return msg or exc.__class__.__name__


# def execute_removal(delete_conflicts=False):
# 	records = get_all_sample_records()
# 	unexpected_doctypes = sorted(set(records.keys()) - set(DELETE_ORDER))
# 	conflicts = get_sample_data_conflicts()

# 	if conflicts and not delete_conflicts:
# 		return {"status": "conflicts", "conflicts": conflicts}

# 	tracked_count = sum(len(names) for names in records.values())
# 	conflict_count = len(conflicts) if delete_conflicts else 0
# 	if tracked_count + conflict_count > MAX_AUTO_DELETE:
# 		frappe.throw(
# 			_(
# 				"Refusing to auto-process {0} records in a single run - that is far more "
# 				"than sample data seeding should ever produce. Please review the "
# 				"'Sample Data Log' field on ERP Configuration manually before retrying."
# 			).format(tracked_count + conflict_count)
# 		)

# 	result = {
# 		"doctype_counts": {},  # total handled (any outcome) per doctype
# 		"status_counts": {"deleted": {}, "cancelled": {}, "disabled": {}, "already_gone": {}},
# 		"errors": [],
# 		"skipped_unexpected": {dt: records[dt] for dt in unexpected_doctypes},
# 	}

# 	def _record_outcome(doctype, status):
# 		result["status_counts"][status][doctype] = result["status_counts"][status].get(doctype, 0) + 1
# 		result["doctype_counts"][doctype] = result["doctype_counts"].get(doctype, 0) + 1

# 	if conflicts and delete_conflicts:
# 		for c in conflicts:
# 			try:
# 				status = _safe_delete(c["linked_doctype"], c["linked_name"])
# 				frappe.db.commit()  # per-record commit - see safety note (3)
# 				_record_outcome(c["linked_doctype"], status)
# 			except Exception as e:
# 				frappe.log_error(
# 					title=f"Sample Data: failed to process linked {c['linked_doctype']} {c['linked_name']}",
# 					message=frappe.get_traceback(),
# 				)
# 				frappe.db.rollback()
# 				result["errors"].append(
# 					{
# 						"doctype": c["linked_doctype"],
# 						"name": c["linked_name"],
# 						"error": _error_reason(e),
# 					}
# 				)

# 	def _delete_bucket(doctype, names):
# 		for name in names:
# 			try:
# 				status = _safe_delete(doctype, name)
# 				remove_from_log(doctype, name)  # only on a confirmed outcome - see safety note (4)
# 				frappe.db.commit()  # per-record commit - see safety note (3)
# 				_record_outcome(doctype, status)
# 			except Exception as e:
# 				frappe.log_error(
# 					title=f"Sample Data: failed to process {doctype} {name}",
# 					message=frappe.get_traceback(),
# 				)
# 				frappe.db.rollback()
# 				result["errors"].append({"doctype": doctype, "name": name, "error": _error_reason(e)})

# 	# ONLY DELETE_ORDER doctypes are ever processed here - anything
# 	# else tracked in the log is reported in
# 	# result["skipped_unexpected"] above and left untouched.
# 	for doctype in DELETE_ORDER:
# 		_delete_bucket(doctype, records.get(doctype, []))

# 	remaining = get_all_sample_records()
# 	all_clean = not result["errors"] and not result["skipped_unexpected"] and not remaining
# 	result["remaining"] = remaining

# 	if all_clean:
# 		mark_sample_data_removed()

# 	frappe.db.commit()

# 	return {"status": "done", "result": result, "is_sample_data_removed": all_clean}


import frappe
from frappe import _
from verp_staffing.utils.sample_data_guard import _get_linked_documents
from verp_staffing.utils.sample_data_tracking import (
    get_all_sample_records,
    remove_from_log,
    clear_log_for_doctype,
    mark_sample_data_removed,
    DEMO_COMPANY_NAME,
)

# Reverse of the creation order in sample_data.create_sample_data() for
# the doctypes that DON'T carry a `company` field and so can't be swept
# by _force_delete_sample_data() below - these still go through the
# per-record _safe_delete() path.
#
# Payment Entry, Journal Entry, Subscription, Purchase Invoice, Purchase
# Order, Sales Invoice, Sales Order, GL Entry, and Customer/Lead Detail
# Form are NOT here - see _force_delete_sample_data(). Going through
# _safe_delete() one record at a time was never reliably clearing them
# (Payment Entry sits in PROTECTED_DOCTYPES; the rest kept tripping
# LinkExistsError against orphaned GL Entry rows that a hand-maintained
# company-doctype list had missed), which is exactly the gap this file
# now closes.
DELETE_ORDER = [
    "Comment",
    "Subscription Plan",
    "Interview",
    "Marketing",
    "Resume",
    "Cover Letter",
    "Training",
    "RUC",
    "Item",
    "Opportunity",
    "Lead",
    "Supplier",
    "Employee",
    "User",
]

# Doctypes that don't carry a `company` field, so they can't be scoped
# that way - force-deleted instead by the exact names in the sample-data
# tracking log (which already includes ones created indirectly, e.g. a
# Lead Detail Form auto-generated alongside a Lead/Customer/Opportunity).
FORCE_DELETE_BY_LOG = [
    "Customer",
    "Lead Detail Form",
]

# Structural/master doctypes that must NEVER be touched by the
# company-scoped force-delete sweep below, even though some of them
# (Account, Cost Center, Warehouse...) do carry a `company` field. These
# are foundational masters auto-created for any Company, not sample
# "data" - wiping them would break the Demo Company (and anything else)
# rather than just clean up demo transactions.
COMPANY_FORCE_DELETE_PROTECTED = {
    "Company",
    "Fiscal Year",
    "Account",
    "Item Category",
    "Supplier Group",
    "Department",
    "Role Profile",
    "ERP Configuration",
    "DocType",
    "Role",
    "User Permission",
    "Cost Center",
    "Warehouse",
    "Price List",
    "Mode of Payment",
}

# Doctypes whose records get created/removed automatically as a side
# effect of their parent transaction being submitted/cancelled - not
# real conflicts, just noise.
CONFLICT_NOISE_DOCTYPES = {
    "GL Entry",
    "View Log",
    "Version",
    "Activity Log",
    "Notification Log",
    "Email Queue",
    "Document Follow",
    "Access Log",
    "Route History",
    "Deleted Document",
}

# Doctypes the per-record _safe_delete() path will NEVER touch, checked
# directly in _safe_delete(). This is unrelated to the company-scoped
# force-delete sweep (which uses COMPANY_FORCE_DELETE_PROTECTED instead,
# on purpose - GL Entry, for example, must stay force-deletable by
# company even though it's also "noise" for conflict-reporting).
PROTECTED_DOCTYPES = CONFLICT_NOISE_DOCTYPES | {
    "Payment Entry",
    "DocType",
    "Role",
    "User Permission",
    "Company",
    "Fiscal Year",
    "Account",
    "Item Category",
    "Supplier Group",
    "Department",
    "Role Profile",
    "ERP Configuration",
}

DISABLE_FIELD_CANDIDATES = [
    ("disabled", 1),
    ("enabled", 0),
]

MAX_AUTO_DELETE = 5000


def _get_company_scoped_doctypes():
    """Every doctype with a top-level 'company' Link field (standard or
    custom), that has its own DB table, minus COMPANY_FORCE_DELETE_
    PROTECTED. Computed fresh each run instead of hand-maintained - a
    fixed list was exactly what let GL Entry (auto-created by submitting
    Payment Entry/Journal Entry/Sales Invoice/Purchase Invoice, but never
    itself force-deleted) survive and then block Supplier's normal
    delete_doc() with a LinkExistsError, leaving Supplier, GL Entries,
    and Demo-Company-scoped data all still visible after "removal"."""
    standard = frappe.get_all(
        "DocField",
        filters={"fieldname": "company", "fieldtype": "Link", "options": "Company"},
        pluck="parent",
    )
    custom = frappe.get_all(
        "Custom Field",
        filters={"fieldname": "company", "fieldtype": "Link", "options": "Company"},
        pluck="dt",
    )

    result = []
    for dt in set(standard) | set(custom):
        if dt in COMPANY_FORCE_DELETE_PROTECTED:
            continue
        try:
            meta = frappe.get_meta(dt)
        except Exception:
            continue
        if meta.istable:
            continue  # child table rows live in the parent's table, not their own
        if not frappe.db.table_exists(dt):
            continue
        result.append(dt)
    return sorted(result)


def _force_handled_doctypes():
    return set(_get_company_scoped_doctypes()) | set(FORCE_DELETE_BY_LOG)


def get_sample_data_conflicts():
    """-> [{sample_doctype, sample_name, linked_doctype, linked_name}, ...]
    for every link into a sample record that comes from a document that
    is itself NOT sample data. Force-handled doctypes are skipped
    entirely - they're force-deleted regardless of any live links into
    them, so there's nothing to confirm about them."""
    sample_records = get_all_sample_records()
    sample_lookup = {(dt, n) for dt, names in sample_records.items() for n in names}
    force_handled = _force_handled_doctypes()

    conflicts = []
    for doctype, names in sample_records.items():
        if doctype in force_handled:
            continue
        for name in names:
            for linked_doctype, linked_name in _get_linked_documents(doctype, name):
                if linked_doctype in CONFLICT_NOISE_DOCTYPES:
                    continue
                if linked_doctype in force_handled:
                    continue
                if (linked_doctype, linked_name) in sample_lookup:
                    continue
                conflicts.append(
                    {
                        "sample_doctype": doctype,
                        "sample_name": name,
                        "linked_doctype": linked_doctype,
                        "linked_name": linked_name,
                    }
                )
    return conflicts


def get_summary():
    records = get_all_sample_records()
    force_handled = _force_handled_doctypes()
    unexpected_doctypes = sorted(
        set(records.keys()) - set(DELETE_ORDER) - force_handled
    )
    return {
        "counts": {dt: len(names) for dt, names in records.items()},
        "total": sum(len(names) for names in records.values()),
        "records": records,
        "conflicts": get_sample_data_conflicts(),
        "unexpected_doctypes": unexpected_doctypes,
    }


def _try_disable(doctype, name):
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return None
    fieldnames = {df.fieldname for df in meta.fields if df.fieldtype == "Check"}

    for field, value in DISABLE_FIELD_CANDIDATES:
        if field in fieldnames:
            frappe.db.set_value(doctype, name, field, value)
            return field
    return None


def _safe_delete(doctype, name):
    if doctype in PROTECTED_DOCTYPES:
        raise frappe.ValidationError(
            f"{doctype} is protected and cannot be touched by this tool"
        )

    if not frappe.db.exists(doctype, name):
        return "already_gone"

    doc = frappe.get_doc(doctype, name)

    if doc.meta.is_submittable and doc.docstatus == 1:
        doc.cancel()
        return "cancelled"

    try:
        frappe.delete_doc(doctype, name, ignore_permissions=True, ignore_missing=True)
        return "deleted"
    except frappe.LinkExistsError:
        disabled_field = _try_disable(doctype, name)
        if disabled_field:
            return "disabled"
        raise


def _error_reason(exc):
    msg = str(exc).strip()
    return msg or exc.__class__.__name__


def _force_delete_by_company(doctype, company_name):
    """Bypass docstatus/link checks entirely and delete every row of
    `doctype` tied to `company_name` in one direct SQL statement."""
    count = frappe.db.count(doctype, {"company": company_name})
    if not count:
        return 0
    frappe.db.sql(f"DELETE FROM `tab{doctype}` WHERE company = %s", (company_name,))
    return count


def _force_delete_by_names(doctype, names):
    names = [n for n in names if n]
    if not names:
        return 0
    frappe.db.sql(
        f"DELETE FROM `tab{doctype}` WHERE name IN %(names)s", {"names": names}
    )
    return len(names)


def _force_delete_sample_data(records):
    """Everything tied to the Demo Company by a `company` field (Sales/
    Purchase Order/Invoice, Payment Entry, Journal Entry, Subscription,
    GL Entry, and anything else with a company field - see
    _get_company_scoped_doctypes()), plus tracked Customer and Lead
    Detail Form rows. All wiped with direct SQL instead of _safe_delete()
    - no docstatus/link checks, no per-record looping, and critically no
    orphaned GL Entry rows left behind to block Supplier's normal delete
    further down."""
    doctype_counts = {}

    for doctype in _get_company_scoped_doctypes():
        removed = _force_delete_by_company(doctype, DEMO_COMPANY_NAME)
        if removed:
            doctype_counts[doctype] = removed
        clear_log_for_doctype(doctype)

    for doctype in FORCE_DELETE_BY_LOG:
        removed = _force_delete_by_names(doctype, records.get(doctype, []))
        if removed:
            doctype_counts[doctype] = removed
        clear_log_for_doctype(doctype)

    frappe.db.commit()
    return doctype_counts


def _delete_demo_company_if_empty():
    """Best-effort: once every company-scoped doctype has been swept
    clean for Demo Company, the Demo Company record only ever existed to
    host sample data - remove it too. Never blocks or downgrades the
    overall removal result: a failure here (something this tool doesn't
    know about still references it) is logged and reported, not raised."""
    if not (demo_company := frappe.db.exists("Company", DEMO_COMPANY_NAME)):
        return "already_gone"
    try:
        res = frappe.db.delete(
            "Fiscal Year Company",
            {
                "company": demo_company,
            },
        )
        fiscal_years = frappe.get_all(
            "Fiscal Year Company",
            filters={"company": DEMO_COMPANY_NAME},
            pluck="parent",
            distinct=True,
        )
        for fy_name in fiscal_years:
            try:
                fy = frappe.get_doc("Fiscal Year", fy_name)

                remaining = [
                    row
                    for row in fy.included_companies
                    if row.company != DEMO_COMPANY_NAME
                ]

                if not remaining:
                    continue

                fy.included_companies = remaining
                fy.save(ignore_permissions=True)
                frappe.db.commit()

            except Exception:
                frappe.db.rollback()
                frappe.log_error(
                    title="Sample Data: failed to unlink Demo Company from Fiscal Year",
                    message=frappe.get_traceback(),
                )
        comp = frappe.delete_doc(
            "Company", DEMO_COMPANY_NAME, ignore_permissions=True, ignore_missing=True
        )
        frappe.db.commit()
        return "deleted"
    except Exception as e:

        frappe.log_error(
            title="Sample Data: failed to delete Demo Company",
            message=frappe.get_traceback(),
        )
        frappe.db.rollback()
        return _error_reason(e)


def _reset_default_company_after_removal():
    """Point default_company at any other existing company. If none
    exists (or Demo Company somehow survived), leave the field exactly
    as it is - never write an empty/invalid value."""
    other_company = frappe.db.get_value(
        "Company", {"name": ["!=", DEMO_COMPANY_NAME]}, "name"
    )
    if other_company:
        frappe.db.set_single_value(
            "ERP Configuration", "default_company", other_company
        )


def execute_removal(delete_conflicts=False):
    records = get_all_sample_records()
    force_handled = _force_handled_doctypes()
    unexpected_doctypes = sorted(
        set(records.keys()) - set(DELETE_ORDER) - force_handled
    )
    conflicts = get_sample_data_conflicts()

    if conflicts and not delete_conflicts:
        return {"status": "conflicts", "conflicts": conflicts}

    tracked_count = sum(len(names) for names in records.values())
    conflict_count = len(conflicts) if delete_conflicts else 0
    if tracked_count + conflict_count > MAX_AUTO_DELETE:
        frappe.throw(
            _(
                "Refusing to auto-process {0} records in a single run - that is far more "
                "than sample data seeding should ever produce. Please review the "
                "'Sample Data Log' field on ERP Configuration manually before retrying."
            ).format(tracked_count + conflict_count)
        )

    result = {
        "doctype_counts": {},
        "status_counts": {
            "deleted": {},
            "cancelled": {},
            "disabled": {},
            "already_gone": {},
            "force_deleted": {},
        },
        "errors": [],
        "skipped_unexpected": {dt: records[dt] for dt in unexpected_doctypes},
    }

    def _record_outcome(doctype, status):
        result["status_counts"][status][doctype] = (
            result["status_counts"][status].get(doctype, 0) + 1
        )
        result["doctype_counts"][doctype] = result["doctype_counts"].get(doctype, 0) + 1

    # Force-delete the company-scoped + customer/lead-detail-form buckets
    # FIRST, so nothing downstream (Supplier, Item, Lead...) trips a
    # LinkExistsError against orphaned GL Entry / Sales Invoice / etc.
    forced_counts = _force_delete_sample_data(records)
    for doctype, n in forced_counts.items():
        result["status_counts"]["force_deleted"][doctype] = n
        result["doctype_counts"][doctype] = result["doctype_counts"].get(doctype, 0) + n

    if conflicts and delete_conflicts:
        for c in conflicts:
            try:
                status = _safe_delete(c["linked_doctype"], c["linked_name"])
                frappe.db.commit()
                _record_outcome(c["linked_doctype"], status)
            except Exception as e:
                frappe.log_error(
                    title=f"Sample Data: failed to process linked {c['linked_doctype']} {c['linked_name']}",
                    message=frappe.get_traceback(),
                )
                frappe.db.rollback()
                result["errors"].append(
                    {
                        "doctype": c["linked_doctype"],
                        "name": c["linked_name"],
                        "error": _error_reason(e),
                    }
                )

    def _delete_bucket(doctype, names):
        for name in names:
            try:
                status = _safe_delete(doctype, name)
                remove_from_log(doctype, name)
                frappe.db.commit()
                _record_outcome(doctype, status)
            except Exception as e:
                frappe.log_error(
                    title=f"Sample Data: failed to process {doctype} {name}",
                    message=frappe.get_traceback(),
                )
                frappe.db.rollback()
                result["errors"].append(
                    {"doctype": doctype, "name": name, "error": _error_reason(e)}
                )

    for doctype in DELETE_ORDER:
        _delete_bucket(doctype, records.get(doctype, []))

    remaining = get_all_sample_records()

    all_clean = (
        not result["errors"] and not result["skipped_unexpected"] and not remaining
    )
    result["remaining"] = remaining
    if all_clean:
        result["demo_company_removal"] = _delete_demo_company_if_empty()
        _reset_default_company_after_removal()

    frappe.db.commit()
    mark_sample_data_removed()

    return {"status": "done", "result": result, "is_sample_data_removed": all_clean}
