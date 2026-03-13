// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service", {
	refresh(frm) {
		render_candidate_field_selector(frm);
	}
});


function render_candidate_field_selector(frm) {

	const wrapper = frm.get_field("select_candidate_details_form_fields_html").$wrapper;

	frappe.model.with_doctype("Lead Detail Form", function () {

		const meta = frappe.get_meta("Lead Detail Form");

		let selected_fields = [];
		if (frm.doc.candidate_details_form_fields) {
			selected_fields = frm.doc.candidate_details_form_fields.split(",");
		}

		let html = `
			<div style="border:1px solid #ddd;border-radius:6px;padding:16px;">
				
				<h4 style="margin-bottom:12px;">
					Configure candidate form fields for : ${frm.doc.name || "This Service"}
				</h4>

				<input 
					type="text"
					class="candidate-field-search form-control"
					placeholder="Search fields..."
					style="margin-bottom:12px;"
				/>

				<div class="candidate-field-container"
					style="
						max-height:400px;
						overflow:auto;
						display:grid;
						grid-template-columns:1fr 1fr;
						gap:8px;
					">
		`;

		meta.fields
			.sort((a,b)=>a.idx-b.idx)
			.forEach(df => {

				if (
					[
						"Section Break",
						"Column Break",
						"HTML"
					].includes(df.fieldtype)
				) {
					return;
				}

				const checked = selected_fields.includes(df.fieldname) ? "checked" : "";

				const tableBadge =
					df.fieldtype === "Table"
						? `<span style="
							background:#e3f2fd;
							color:#1565c0;
							font-size:11px;
							padding:2px 6px;
							border-radius:4px;
							margin-left:6px;">TABLE</span>`
						: "";

				html += `
					<label class="candidate-field-row"
						style="
							border:1px solid #eee;
							padding:6px 8px;
							border-radius:4px;
							display:flex;
							align-items:center;
							gap:6px;
							cursor:pointer;
						">

						<input
							type="checkbox"
							class="candidate-field-checkbox"
							data-fieldname="${df.fieldname}"
							data-label="${(df.label || df.fieldname).toLowerCase()}"
							${checked}
						>

						<span>
							${df.label || df.fieldname}
							${tableBadge}
						</span>
					</label>
				`;
			});

		html += `
				</div>
			</div>
		`;

		wrapper.html(html);


		// checkbox change handler (no rerender)
		wrapper.find(".candidate-field-checkbox").on("change", function () {
			let values = [];

			wrapper.find(".candidate-field-checkbox:checked").each(function () {
				values.push($(this).data("fieldname"));
			});

			frm.set_value("candidate_details_form_fields", values.join(","));
		});


		// search filter
		wrapper.find(".candidate-field-search").on("keyup", function () {

			const value = $(this).val().toLowerCase();

			wrapper.find(".candidate-field-row").each(function () {

				const label = $(this)
					.find(".candidate-field-checkbox")
					.data("label");

				if (label.includes(value)) {
					$(this).show();
				} else {
					$(this).hide();
				}

			});

		});

	});
}
