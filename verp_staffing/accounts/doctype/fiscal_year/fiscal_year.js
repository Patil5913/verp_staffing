// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

// verp_staffing.accounts.doctype.fiscal_year.fiscal_year.get_available_companies

// Fiscal Year – Client Script
// Features:
//   1. included_companies: smart company filter (exclude companies in active fiscal years)
//   2. Disable checkbox: confirmation dialog before saving
//   3. Once disabled: permanent read-only lock, cannot be re-enabled

frappe.ui.form.on("Fiscal Year", {
	// ─────────────────────────────────────────────────────────────
	// SETUP — attach get_query to included_companies.company
	// ─────────────────────────────────────────────────────────────
	setup: function (frm) {
		frm.set_query("included_companies", function () {
			return {
				query: "verp_staffing.accounts.doctype.fiscal_year.fiscal_year.get_available_companies",
				filters: {
					current_fiscal_year: frm.doc.name || "",
				},
			};
		});
	},

	// ─────────────────────────────────────────────────────────────
	// ONLOAD + REFRESH — enforce read-only when already disabled
	// ─────────────────────────────────────────────────────────────
	onload: function (frm) {
		_enforce_disabled_state(frm);
	},

	refresh: function (frm) {
		_enforce_disabled_state(frm);

				frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Fiscal Year";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
	},

	// ─────────────────────────────────────────────────────────────
	// DISABLED CHECKBOX — intercept every toggle
	// ─────────────────────────────────────────────────────────────
	disabled: function (frm) {
		// ── User is trying to UNCHECK (re-enable) — block it ─────
		if (!frm.doc.disabled) {
			frappe.msgprint({
				title: __("Cannot Re-enable"),
				message: __(
					"A disabled Fiscal Year is permanently locked and cannot be re-enabled.",
				),
				indicator: "red",
			});
			// Force it back to checked without re-triggering this handler
			frm.doc.disabled = 1;
			frm.refresh_field("disabled");
			return;
		}

		// ── User is checking (disabling) — show confirmation ──────
		frappe.confirm(
			__(
				"<b>Disable this Fiscal Year?</b><br><br>" +
					"This will permanently lock the Fiscal Year:<ul>" +
					"<li>No new transactions can be posted against it.</li>" +
					"<li>The record will become fully read-only.</li>" +
					"<li><b>This action cannot be undone.</b></li>" +
					"</ul>",
			),

			// ── Confirmed ─────────────────────────────────────────
			function () {
				_enforce_disabled_state(frm);
				frappe.show_alert({
					message: __("Saving disabled Fiscal Year..."),
					indicator: "orange",
				});
				frm.save();
			},

			// ── Cancelled → revert checkbox to unchecked ──────────
			function () {
				frm.doc.disabled = 0;
				frm.refresh_field("disabled");
			},
		);
	},
});

// ─────────────────────────────────────────────────────────────────
// HELPER — make the form fully read-only when disabled = 1
// ─────────────────────────────────────────────────────────────────
function _enforce_disabled_state(frm) {
	if (!frm.doc.disabled) return;

	// 1. Make all fields read-only
	frm.set_read_only();

	// 2. Hide Save / Edit / Submit buttons
	frm.disable_save();
	if (frm.toolbar) {
		frm.toolbar.page.clear_primary_action();
		frm.toolbar.page.clear_secondary_action();
	}

	// 3. Show a permanent red banner (only once per load)
	if (!frm._disabled_banner_shown) {
		frm.dashboard.add_comment(
			__(
				"This Fiscal Year is <b>permanently disabled</b> and is read-only. No changes can be made.",
			),
			"red",
			true, // persistent — not dismissible
		);
		frm._disabled_banner_shown = true;
	}

	// 4. Hide child table action buttons (Add Row, Delete)
	let grid = frm.fields_dict["included_companies"] && frm.fields_dict["included_companies"].grid;
	if (grid) {
		grid.wrapper.find(".grid-add-row, .grid-remove-rows, .row-check").hide();
		grid.cannot_add_rows = true;
		grid.cannot_delete_rows = true;
	}
}
