(function () {
	try {
		_sample_data_guard_init();
	} catch (e) {
		console.error("sample_data_guard.js failed to initialize:", e);
	}
})();

function _sample_data_guard_init() {
	const SAMPLE_DATA_GUARD_SKIP_DOCTYPES = ["ERP Configuration"];

	// Doctypes that can plausibly hold a Link/Dynamic Link field
	// pointing at sample data. Registered explicitly as a fallback
	// alongside "*", in case the wildcard doctype isn't honored by
	// frappe.ui.form.on in this Frappe version.
	const SAMPLE_DATA_GUARD_EXPLICIT_DOCTYPES = [
		"Sales Order",
		"Purchase Order",
		"Purchase Invoice",
		"Sales Invoice",
		"Customer",
		"Lead",
		"Opportunity",
		"Supplier",
		"Interview",
		"Marketing",
		"Resume",
		"Cover Letter",
		"Training",
		"RUC",
		"Subscription",
		"Subscription Plan",
		"Journal Entry",
		"Payment Entry",
		"Lead Detail Form",
	];

	// One-way switch: sample data seeding runs once, from the setup
	// wizard, and removal runs at most once after that - so this event
	// only ever fires with is_sample_data_removed: 1. Guarded because
	// frappe.realtime may not exist yet on every page this script loads
	// on (see the file header above - this exact call, unguarded, is
	// suspected of having broken the setup wizard previously).
	if (frappe.realtime && typeof frappe.realtime.on === "function") {
		frappe.realtime.on("sample_data_removed", (data) => {
			frappe.boot.is_sample_data_removed = data.is_sample_data_removed;
		});
	}

	// ── Core check, shared by the form handler and the Quick Entry patch ──

	function get_sample_data_links(doctype, doc) {
		return new Promise((resolve) => {
			frappe.call({
				method: "verp_staffing.utils.sample_data_guard.check_links_to_sample_data",
				args: { doctype, doc },
				callback(r) {
					resolve(r.message || []);
				},
				error: () => resolve([]), // never block a save just because the check itself failed
			});
		});
	}

	function confirm_sample_data_links(links) {
		return new Promise((resolve, reject) => {
			if (!links.length) {
				resolve();
				return;
			}

			const list = links
				.map(
					(l) =>
						`<li>${__(l.label)}: <b>${frappe.utils.escape_html(l.value)}</b> (${l.reference_doctype})</li>`,
				)
				.join("");

			frappe.confirm(
				__(
					`This document links to sample data:<ul>${list}</ul>If the sample data is removed later (via "Remove Sample Data" on ERP Configuration), this entry will be deleted along with it. Save anyway?`,
				),
				() => resolve(),
				() => reject(),
			);
		});
	}

	function warn_if_linked_to_sample_data(doctype, doc) {
		if (SAMPLE_DATA_GUARD_SKIP_DOCTYPES.includes(doctype)) return Promise.resolve();
		if (frappe.boot.is_sample_data_removed) return Promise.resolve(); // cheap in-memory skip

		return get_sample_data_links(doctype, doc).then((links) => confirm_sample_data_links(links));
	}

	// ── 1. Full form saves ──────────────────────────────────────────────

	function sample_data_guard_validate(frm) {
		if (!frm.is_new()) return; // only warn the moment the link is first created

		// Idempotency guard: if both the "*" registration and an explicit
		// per-doctype registration fire for the same save, only run (and
		// only show one confirm dialog) once.
		if (frm.__sample_data_guard_running) return;
		frm.__sample_data_guard_running = true;

		return warn_if_linked_to_sample_data(frm.doctype, frm.doc)
			.then(() => {
				frm.__sample_data_guard_running = false;
			})
			.catch(() => {
				frm.__sample_data_guard_running = false;
				frappe.validated = false;
				throw new Error("sample-data-guard: save cancelled by user");
			});
	}

	if (frappe.ui && frappe.ui.form && typeof frappe.ui.form.on === "function") {
		frappe.ui.form.on("*", { validate: sample_data_guard_validate });
		SAMPLE_DATA_GUARD_EXPLICIT_DOCTYPES.forEach((doctype) =>
			frappe.ui.form.on(doctype, { validate: sample_data_guard_validate }),
		);
	}

	// ── 2. Quick Entry dialogs (list view "+ New") - bypasses the target
	// doctype's form entirely, so it needs its own hook. ────────────────

	if (frappe.ui && frappe.ui.form && frappe.ui.form.QuickEntryForm) {
		const original_insert = frappe.ui.form.QuickEntryForm.prototype.insert;

		frappe.ui.form.QuickEntryForm.prototype.insert = function () {
			const qe = this;
			const args = arguments;

			if (SAMPLE_DATA_GUARD_SKIP_DOCTYPES.includes(qe.doctype) || frappe.boot.is_sample_data_removed) {
				return original_insert.apply(qe, args);
			}

			let doc = {};
			try {
				doc = (qe.dialog && qe.dialog.get_values(true)) || {};
			} catch (e) {
				// couldn't read values for some reason - fail open rather than
				// block a Quick Entry insert on a check we can't even run
				return original_insert.apply(qe, args);
			}

			return warn_if_linked_to_sample_data(qe.doctype, doc).then(
				() => original_insert.apply(qe, args),
				() => {
					// user chose not to proceed - leave the dialog open, don't insert
				},
			);
		};
	}
}