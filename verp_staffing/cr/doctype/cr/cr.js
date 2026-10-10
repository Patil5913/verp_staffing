// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt
let interview_offset = 0;
const interview_limit = 5;

frappe.ui.form.on("CR", {
	setup(frm) {
		$(frm.wrapper).on("shown.bs.tab", ".nav-link", () => {
			render_tab_data(frm);
		});
	},
	refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Customer Representative",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();
		render_tab_data(frm);

		if (!["Dispute Pending", "Refund Rejected"].includes(frm.doc.status)) {
			frm.disable_form();
			frm.disable_save();
			window.add_forward_button(frm);
		}
		const assign_to_query = () => ({
			query: "verp_staffing.crm.api.helpers.get_subordinate_employees",
			filters: { department: "CR" },
		});

		frm.set_query("assign_to", assign_to_query);
		frm.set_query("assign_to", "cr_history", assign_to_query);
		lock_history_grid(frm);
		add_resolution_buttons(frm);
	},
	status: function (frm) {
		if (frm.doc.status === "Completed") {
			frappe.confirm(
				"Marking this as Completed cannot be undone. Proceed?",
				() => {
					// User clicked 'Yes'
					frm.set_df_property("status", "read_only", 1);
					frm.save();
				},
				() => {
					// User clicked 'No' - Revert to previous value
					// frm.doc.__onsave holds values from the last save
					let previous_status = frm.doc.__onsave ? frm.doc.__onsave.status : "Draft";
					frm.set_value("status", previous_status);
				},
			);
		}
	},
});

function lock_history_grid(frm) {
	const grid = frm.fields_dict.cr_history.grid;

	grid.cannot_add_rows = true;
	grid.df.cannot_delete_rows = true;
	grid.refresh();
}

function render_tab_data(frm) {
	if (frm.is_new()) return;
	const active_tab = frm.active_tab_map && frm.active_tab_map[frm.doc.name];
	if (active_tab.df.fieldname === "history_tab") {
		load_customer_history_if_needed(frm);
	} else if (active_tab.df.fieldname === "sales_order_tab") {
		show_sales_order(frm);
	} else if (active_tab.df.fieldname === "customer_information_tab") {
		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details",
			customer: frm.doc.customer,
			fields: [
				"agreement_link",
				"signature_image",
				"my_electronic_signature_has_same_effect_as_handwritten",
				"i_consent_to_receive_sign_and_store_documents_electronically",
				"i_confirm_my_identity_and_signing_this_document_intentionally",
				"surname",
				"first_name",
				"father_name",
				"personal_phone_number",
				"email",
				"personal_linkedin",
				"date_of_birth",
				"educational_details",
				"past_experience_table",
				"technologies",
				"additional_skills",
				"entry_date",
				"current_address",
				"address_history",
				"certificate_or_completed_course",
				"current_visa_status",
				"experience",
				"number_for_marketing",
				"google_voice_number",
				"marketing_linkedin",
				"passport_number",
				"ssn_digit",
				"availability_for_interview",
				"remarks",
				"visa_copy",
				"ead_card",
				"driving_licence",
				"old_resume",
			],
		});
	}
}

function load_customer_history_if_needed(frm) {
	if (!frm.doc.customer) return;
	if (frm.__history_loaded_for === frm.doc.name) return; // already loaded for this doc

	frm.__history_loaded_for = frm.doc.name;

	if (frm.fields_dict.customer_details) {
		frm.fields_dict.customer_details.$wrapper.html(
			"<p style='color:#888'>Loading history...</p>",
		);
	}

	window.verp_staffing.render_customer_history_widget(frm, {
		fieldname: "customer_details",
		customer: frm.doc.customer,
		doctype: "Customer",
	});
}

window.viewFullFeedback = function (encodedText) {
	const fullText = decodeURIComponent(encodedText);

	const dialog = document.createElement("div");
	dialog.style = `
        position:fixed;
        top:0;left:0;right:0;bottom:0;
        background:rgba(0,0,0,0.5);
        display:flex;
        justify-content:center;
        align-items:center;
        z-index:9999;
    `;

	dialog.innerHTML = `
        <div style="
            background:#fff;
            padding:24px;
            border-radius:12px;
            width:700px;
            max-width:95%;
            max-height:80vh;
            display:flex;
            flex-direction:column;
        ">
            <h3 style="margin-bottom:12px;">Full Feedback</h3>

            <div style="
                overflow-y:auto;
                padding-right:6px;
                margin-bottom:15px;
            ">
                <p style="
                    color:#334155;
                    font-size:14px;
                    line-height:1.6;
                    word-break:break-word;
                    white-space:pre-wrap;
                "></p>
            </div>

            <div style="text-align:right;">
                <button onclick="this.closest('[data-dialog]').remove()"
                    style="
                        padding:6px 14px;
                        background:#260fea;
                        color:#fff;
                        border:none;
                        border-radius:6px;
                        cursor:pointer;
                    ">
                    Close
                </button>
            </div>
        </div>
    `;

	dialog.setAttribute("data-dialog", "true");
	// ✅ Close when clicking outside
	dialog.addEventListener("click", function (e) {
		if (!e.target.closest("#feedbackBox")) {
			dialog.remove();
		}
	});

	document.body.appendChild(dialog);

	// ✅ Safe text injection (no HTML breaking)
	dialog.querySelector("p").innerText = fullText;
};

function render_interviews(data, append = false) {
	let container = $("#interview-list");

	if (!append) {
		container.html("");
	}

	let html = "";
	let records = data.departments?.Interview || [];

	if (!records.length) {
		html += `
        <div style="text-align:center;color:#64748b;padding:20px;">
            No interviews found
        </div>
    `;
	} else {
		records.forEach((dept) => {
			html += `
		<div style="margin-top:10px;">
			<div style="border:1px solid #e5e7eb;border-radius:10px;padding:14px;background:#f9fafb;">

				<div style="display:flex;justify-content:space-between;margin-bottom:10px;">
					<a href="/verp/Interview/${dept.id}" target="_blank"
						style="font-weight:600;color:#260fea;">
						${dept.id}
					</a>

					<span style="background:#e0f2fe;padding:4px 10px;border-radius:20px;font-size:12px;">
						${dept.status || "-"}
					</span>
				</div>

				<div style="color:#64748b;margin-bottom:8px;">
					Company: ${dept.company || "-"} • Role: ${dept.role || "-"}
				</div>

				<table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
        <tr>
            <th style="border-bottom:2px solid #cbd5f5;padding:8px;">#</th>
            <th style="border-bottom:2px solid #cbd5f5;padding:8px;">Round</th>
            <th style="border-bottom:2px solid #cbd5f5;padding:8px;">Type</th>
            <th style="border-bottom:2px solid #cbd5f5;padding:8px;">Interview</th>
            <th style="border-bottom:2px solid #cbd5f5;padding:8px;">Time</th>
            <th style="border-bottom:2px solid #cbd5f5;padding:8px;">Feedback</th>
        </tr>
    </thead>
    <tbody>
        ${
			dept.interview_rounds_table?.length
				? dept.interview_rounds_table
						.map(
							(r, i) => `
                <tr style="border-bottom:1px solid #cbd5e1;">
                    <td style="padding:8px;">${i + 1}</td>
                    <td style="padding:8px;">${r.round || "-"}</td>
                    <td style="padding:8px;">${r.type_of_interview || "-"}</td>
                    <td style="padding:8px;">${r.date_of_interview || "-"}</td>
					<td style="padding:8px;">
                      ${r.from_time && r.to_time ? `${r.from_time} - ${r.to_time} ${verp_staffing.zone_abbr(r.time_zone)}` : "-"}
                    </td>
                    <td style="padding:8px;">
                                        ${
											r.feedback && r.feedback.trim()
												? (() => {
														const text = r.feedback.trim();
														const limit = 20; // 👈 number of characters you want
														const shortText = text.slice(0, limit);

														if (text.length > limit) {
															return `
                                                        
                                                            ${shortText}...
                                                            <span 
                                                                style="cursor:pointer;font-weight:500;"
                                                                onclick='viewFullFeedback("${encodeURIComponent(text)}")'
                                                            >
                                                                view
                                                            </span>
                                                    `;
														} else {
															return text;
														}
													})()
												: "-"
										}
                                        </td>
                </tr>
            `,
						)
						.join("")
				: `<tr><td colspan="7" style="text-align:center;padding:10px;">No rounds</td></tr>`
		}
    </tbody>
</table>

			</div>
		</div>
		`;
		});

		container.append(html);

		let meta = data.interview_meta;

		if (meta && meta.offset + meta.limit < meta.total) {
			$("#interview-load-more").html(`
			<button id="load-more-interviews"
				style="padding:8px 16px;border:none;background:#260fea;color:white;border-radius:6px;">
				Load More
			</button>
		`);
		} else {
			$("#interview-load-more").html("");
		}
	}
}

function show_sales_order(frm) {
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Sales Order",
			filters: { customer: frm.doc.customer },
			fields: ["name", "creation"],
			limit_page_length: 50,
			order_by: "creation desc",
		},
		callback(r) {
			let sales_orders = r.message || [];

			if (sales_orders.length === 0) {
				frm.fields_dict.sales_content.$wrapper.html("<p>No Sales Orders found</p>");
				return;
			}

			let html = `<div style="padding: 10px;">`;
			html += `<h3>Sales Orders (${sales_orders.length})</h3><hr/>`;

			sales_orders.forEach((so) => {
				let safe_id = make_safe_id(so.name);
				html += `
                    <div style="border:1px solid #ddd; padding:15px; border-radius:6px; margin-bottom:15px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h4>Sales Order: ${so.name}</h4>
                            <button class="btn btn-primary go-to-so-btn"
                                data-so="${so.name}" style="font-size:13px;">
                                go to Sales Order
                            </button>
                        </div>
                        <p><b>Date:</b> ${so.date || ""}</p>
                        <div id="terms_${safe_id}"><i>Loading Payment Terms...</i></div>
                    </div>
                `;
				load_payment_terms(so.name, frm);
			});

			html += `</div>`;
			frm.fields_dict.sales_content.$wrapper.html(html);

			frm.fields_dict.sales_content.$wrapper.find(".go-to-so-btn").on("click", function () {
				frappe.set_route("Form", "Sales Order", $(this).data("so"));
			});
		},
	});
}

function load_payment_terms(so_name, frm) {
	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Sales Order", name: so_name },
		callback: function (r) {
			if (!r.message) return;
			let so = r.message;
			let html = `
                <h5>Payment Terms</h5>
                <table class="table table-bordered" style="width:100%; margin-top:10px;">
                    <thead>
                        <tr><th>#</th><th>Date</th><th>Amount</th><th>Received?</th></tr>
                    </thead>
                    <tbody>
            `;
			(so.payment_terms || []).forEach((row, i) => {
				html += `
                    <tr>
                        <td>${i + 1}</td>
                        <td>${row.date || ""}</td>
                        <td>${row.amount || ""}</td>
                        <td>${row.is_received ? "Yes" : "No"}</td>
                    </tr>
                `;
			});
			html += `</tbody></table>`;
			let safe_id = make_safe_id(so_name);

			frm.fields_dict.sales_content.$wrapper.find(`#terms_${safe_id}`).html(html);
		},
	});
}

function make_safe_id(name) {
	return name.replace(/[^a-zA-Z0-9_-]/g, "_");
}

function add_resolution_buttons(frm) {
	if (frm.is_new() || !frm.doc.cr_history || !frm.doc.cr_history.length) return;

	const latest = frm.doc.cr_history[frm.doc.cr_history.length - 1];
	if (!["Dispute Pending", "Refund Rejected"].includes(latest.status)) return;

	frm.add_custom_button(
		"Resolve",
		() => open_resolution_dialog(frm, "Dispute Resolved"),
		"Actions",
	);
	frm.add_custom_button("Refund", () => open_resolution_dialog(frm, "Refund"), "Actions");
}

function open_resolution_dialog(frm, action) {
	const d = new frappe.ui.Dialog({
		title: action,
		fields: [
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: action === "Refund" ? "Reason for Refund" : "Resolution Remarks",
				reqd: 1,
			},
		],
		primary_action_label: action,
		primary_action(values) {
			d.disable_primary_action();
			frappe.call({
				method: "verp_staffing.cr.doctype.cr.cr.resolve_or_refund_cr",
				args: {
					cr_name: frm.doc.name,
					action: action,
					remarks: values.remarks,
				},
				callback() {
					d.hide();
					frm.reload_doc();
				},
				error() {
					d.enable_primary_action();
				},
			});
		},
	});
	d.show();
}
