// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("RUC", {
	async refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);
		window.fetch_and_render_resume(frm);
		add_owner_grid_column(frm, "session_details");

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
			frm.set_df_property("assign_to", "read_only", 1);
		}

		window.add_forward_button(frm, (service_name = "RUC"));

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "RUC";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: display_fields,
		});

		window.setup_service_permission_button(frm);

		frm.set_query("assign_to", () => {
			return {
				query: "verp_staffing.crm.api.helpers.get_assign_to_by_service",
				filters: {
					service: "RUC",
					customer: frm.doc.customer,
				},
			};
		});
	},

	customer(frm) {
		window.fetch_and_render_resume(frm);
	},
	status(frm) {
		window.add_forward_button(frm, (service_name = "RUC"));
	},
});

function add_owner_grid_column(frm, fieldname, options = {}) {
	const { label = __("Created By") } = options;
	const grid = frm.fields_dict[fieldname].grid;
	if (!grid.__owner_column_patched) {
		grid.__owner_column_patched = true;
		const original_refresh = grid.refresh.bind(grid);
		grid.refresh = function (...args) {
			original_refresh(...args);
			inject_owner_column(grid, label);
		};
	}
	grid.refresh();
}

function inject_owner_column(grid, label) {
	if (grid.header_row) {
		inject_owner_cell(grid.header_row, label, true);
	}
	(grid.grid_rows || []).forEach((grid_row) => inject_owner_cell(grid_row, label, false));
}

function inject_owner_cell(grid_row, label, is_header) {
	if (!grid_row.row) return;
	if (!is_header && !grid_row.doc) return; // skip search/filter row
	const $row = grid_row.row;

	const display = is_header ? label : resolve_owner_display(grid_row);
	let $col = $row.children(".owner-col");

	if ($col.length) {
		$col.find(".static-area").text(display);
		$col.attr("title", is_header ? display : grid_row.doc?.owner || "");
		return;
	}

	// find the anchor BEFORE creating the new column, and exclude .owner-col
	// so it can never match itself on a stale/duplicate pass
	const $last_data_col = $row.children("[data-fieldname]").not(".owner-col").last();

	$col = make_owner_col(display, is_header);
	if (!is_header) $col.attr("title", grid_row.doc?.owner || "");

	if ($last_data_col.length) {
		$col.insertAfter($last_data_col);
	} else {
		$row.append($col); // fallback: no real data columns found
	}
}

function make_owner_col(display, is_header) {
	// detached — NOT appended here, caller controls placement
	const $col = $(`
		<div class="col grid-static-col owner-col" data-fieldname="owner" data-fieldtype="Data">
			<div class="field-area" style="display:none;"></div>
			<div class="static-area ellipsis"></div>
		</div>
	`);
	$col.find(".static-area").text(display);
	if (is_header) $col.attr("title", display);
	return $col;
}

function resolve_owner_display(grid_row) {
	const owner = grid_row.doc.owner;
	const info = owner ? frappe.user_info(owner) : null;
	return info ? info.fullname : owner || "";
}
