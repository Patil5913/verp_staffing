// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt
let interview_offset = 0;
const interview_limit = 5;
let CURRENT_EMPLOYEE = null;

frappe.ui.form.on("Customer", {
	async refresh(frm) {
		frappe.breadcrumbs.clear();

		// Define the breadcrumb structure
		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: "Sales",
			doctype: frm.doctype,
			type: "Form",
		};

		frappe.breadcrumbs.update();

		set_customer_owner(frm);

		window.render_notes(frm);
		window.render_activity_section(frm);

		if (frappe.session.user != "Administrator") {
			toggle_tab_view(frm);
		}

		frm.set_query("customer_owner", function () {
			return {
				filters: [["Employee Assignment Detail", "department", "=", "Sales"]],
			};
		});

		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Employee",
				filters: { user: frappe.session.user },
				fieldname: "name",
			},
			callback(r) {
				CURRENT_EMPLOYEE = r.message?.name;
			},
		});

		if (!frm.is_new()) {
			show_sales_order(frm);

			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Employee",
					filters: { user: frappe.session.user },
					fieldname: "name",
				},
				callback: function (r) {
					if (frappe.session.user === "Administrator") {
						return;
					}
					const current_employee = r.message && r.message.name;
					const is_customer_owner = current_employee === frm.doc.customer_owner;

					if (is_customer_owner) {
						// Check if candidate form required
						frappe.call({
							method: "verp_staffing.crm.api.permission_request.get_candidate_form_required_status",
							args: { customer_name: frm.doc.name },
							callback: function (res) {
								if (!res.message || !res.message.required) return;

								// Candidate form required — check if already pending
								frappe.call({
									method: "verp_staffing.crm.api.permission_request.get_owner_pending_field_update_request",
									args: { customer_name: frm.doc.name },
									callback: function (pend_res) {
										if (pend_res.message && pend_res.message.has_pending) {
											frappe.show_alert(
												{
													message: __(
														"Your update request is pending manager approval.",
													),
													indicator: "orange",
												},
												5,
											);
											return;
										}

										// Show Update Detail button
										frm.add_custom_button(__("Update Detail"), () => {
											customer_owner_open_update_detail_dialog(frm);
										});
									},
								});
							},
						});
					} else {
						// Manager — show Accept Updates if pending
						customer_show_accept_updates(frm);
					}
				},
			});
		}

		if (frm.fields_dict.customer_details) {
			frm.fields_dict.customer_details.$wrapper.html(
				"<p style='color:#888'>Loading history...</p>",
				"<p style='color:#888'>Loading history...</p>",
			);
		}

		if (!frm.doc.name) return;
		frappe.call({
			method: "verp_staffing.www.customer.get_customer_history",
			args: {
				customer: frm.doc.name,
				interview_limit: interview_limit,
				interview_offset: interview_offset,
			},
			callback(r) {
				if (!r.message) return;
				render_customer_history(frm, r.message);
			},
		});

		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "lead_details_html",
			customer: frm.doc.name,
			fields: display_fields,
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Customer Form";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		frappe.call({
			method: "verp_staffing.crm.doctype.customer.customer.get_employee_department",
			callback: (r) => {
				let dept = r.message;
				apply_tab_visibility(frm, dept);
			},
		});
		window.add_forward_button(frm);

		frm.add_custom_button("Send Portal Link", function () {
			frappe.call({
				method: "verp_staffing.crm.doctype.customer.customer.send_portal_link",
				args: {
					customer: frm.doc.name,
					customer_name: frm.doc.name1
				},
				freeze: true,
				callback: function (r) {
					if (r.message) {
						frappe.msgprint("Portal link sent successfully");
					}
				},
			});
		});
	},

	sales_order: function (frm) {
		frappe.new_doc("Sales Order", { customer: frm.doc.name });
	},

	customer_from: function (frm) {
		if (frm.doc.customer_from) {
			frm.set_df_property("party_name", "label", frm.doc.customer_from);
		}
		set_customer_owner(frm);
		set_customer_owner(frm);
	},

	party_name: function (frm) {
		frm.trigger("fetch_source_details");
		if (!frm.is_new()) {
			load_lead_details_after_save(frm);
		}
		if (frm.doc.customer_from && frm.doc.party_name) {
			let source_doctype = frm.doc.customer_from;
			let source_name = frm.doc.party_name;
			let fetch_field = source_doctype === "name1";

			frappe.db.get_value(source_doctype, source_name, fetch_field).then((r) => {
				if (r && r.message) {
					let base_name = r.message[fetch_field];
					frm.set_value("name1", base_name ? base_name.trim() : "");
				}
			});
		}
		set_customer_owner(frm);
	},
	validate: function (frm) {
		if (frm.doc.customer_from === "Lead" && !frm.doc.party_name) {
			frappe.msgprint(__("Please select a Lead."));
			frappe.validated = false;
		} else if (frm.doc.customer_from === "Opportunity" && !frm.doc.party_name) {
			frappe.msgprint(__("Please select an Opportunity."));
			frappe.validated = false;
		}
	},
});

function set_customer_owner(frm) {
	if (frm.doc.customer_owner) return;

	if (frm.doc.customer_from === "Opportunity" && frm.doc.party_name) {
		frappe.db.get_value("Opportunity", frm.doc.party_name, "opportunity_owner").then((r) => {
			if (!r.message || !r.message.opportunity_owner) return;
			frm.set_value("customer_owner", r.message.opportunity_owner);
		});
	} else if (frm.doc.customer_from === "Lead" && frm.doc.party_name) {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Employee",
				filters: [["Employee", "user", "=", frappe.session.user]],
				fields: ["name"],
				limit: 1,
			},
			callback: function (r) {
				if (r.message && r.message.length > 0) {
					frm.set_value("customer_owner", r.message[0].name);
				}
			},
		});
	} else {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Employee",
				filters: [["Employee", "user", "=", frappe.session.user]],
				fields: ["name"],
				limit: 1,
			},
			callback: function (r) {
				if (r.message && r.message.length > 0) {
					frm.set_value("customer_owner", r.message[0].name);
				}
			},
		});
	}
}

function get_status_html(row) {
	const isAssignedUser = row.assigned_to === CURRENT_EMPLOYEE;
	const isCompleted = row.status === "Completed";

	if (!isAssignedUser) return `<span>${row.status}</span>`;
	if (isCompleted) return `<span style="color:green;">Completed</span>`;

	return `
        <select data-route="${row.name}" class="route-status">
            <option value="Active" ${row.status === "Active" ? "selected" : ""}>Active</option>
            <option value="Completed">Completed</option>
        </select>
    `;
}

function toggle_tab_view(frm) {
	frappe.call({
		method: "verp_staffing.employee.doctype.employee.employee.get_user_departments",
		callback: function (r) {
			const departments = r.message || [];

			// reset all first (important)
			frm.toggle_display("sales_tab", true);
			frm.toggle_display("sales_content", true);
			frm.toggle_display("technical_tab", true);
			frm.toggle_display("technical_content", true);
			frm.toggle_display("marketing_tab", true);
			frm.toggle_display("marketing_content", true);

			// Onboarding (NEW)
			if (!departments.includes("Onboarding")) {
				// hide onboarding section if not onboarding user
				frm.toggle_display("after_placement_details", false);
			} else {
				frm.toggle_display("after_placement_details", true);
			}
		},
	});
}

function make_safe_id(name) {
	return name.replace(/[^a-zA-Z0-9_-]/g, "_");
}

function show_sales_order(frm) {
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Sales Order",
			filters: { customer: frm.doc.name, docstatus: 1 },
			fields: ["name", "posting_date", "status", "grand_total", "currency"],
			limit_page_length: 50,
			order_by: "creation desc",
		},
		callback(r) {
			const sales_orders = r.message || [];
			const wrapper = frm.fields_dict.sales_content.$wrapper;

			if (!sales_orders.length) {
				wrapper.html(`
                    <p class="text-muted" style="padding:10px">
                        No Sales Orders found. if you have created a Sales Order against this customer, it will appear here once submitted.
                    </p>
                `);
				return;
			}

			let html = `<div style="padding:10px">`;
			sales_orders.forEach((so) => {
				const safe_id = make_safe_id(so.name);
				const status_color =
					{
						Open: "orange",
						Closed: "green",
					}[so.status] || "grey";

				html += `
                    <div style="border:1px solid var(--border-color);
                                padding:15px; border-radius:6px; margin-bottom:15px;">
                        <div style="display:flex; justify-content:space-between;
                                    align-items:center; margin-bottom:8px;">
                            <div>
                                <a href="/app/sales-order/${so.name}" target="_blank"
                                   style="font-size:15px; font-weight:600;">
                                    ${so.name}
                                </a>
                                <span class="indicator-pill ${status_color}"
                                      style="margin-left:8px; font-size:11px;">
                                    ${so.status}
                                </span>
                            </div>
                            <span class="text-muted" style="font-size:12px;">
                                ${frappe.datetime.str_to_user(so.posting_date) || ""}
                            </span>
                        </div>
                        <div id="terms_${safe_id}">
                            <span class="text-muted" style="font-size:12px;">
                                Loading payment terms...
                            </span>
                        </div>
                    </div>
                `;
			});
			html += `</div>`;

			wrapper.html(html);

			// Load payment terms for each SO
			sales_orders.forEach((so) => load_payment_terms(so.name, frm));
		},
	});
}

function load_payment_terms(so_name, frm) {
	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Sales Order", name: so_name },
		callback(r) {
			if (!r.message) return;
			const so = r.message;
			const terms = so.payment_terms || [];
			const safe_id = make_safe_id(so_name);
			const $target = frm.fields_dict.sales_content.$wrapper.find(`#terms_${safe_id}`);

			if (!terms.length) {
				$target.html(`
                    <p class="text-muted" style="font-size:12px; margin:0">
                        No payment terms added.
                    </p>
                `);
				return;
			}

			const status_config = {
				Unpaid: { color: "orange" },
				"Pending Verification": { color: "yellow" },
				Verified: { color: "green" },
				Rejected: { color: "red" },
			};

			const rows = terms
				.map((row, i) => {
					const s = status_config[row.payment_status] || { color: "grey", icon: "—" };
					const condition_label =
						row.payment_condition === "Number of Days"
							? `${row.counter} day(s) from ${frappe.datetime.str_to_user(row.start_date) || "?"}`
							: row.payment_condition === "Number of Interviews"
								? `After ${row.counter} interview(s)`
								: "Not Applied";

					return `
                    <tr>
                        <td style="text-align:center">${i + 1}</td>
                        <td>${condition_label}</td>
                        <td>${row.due_date ? frappe.datetime.str_to_user(row.due_date) : "—"}</td>
                        <td style="text-align:right">
                            ${format_currency(row.amount, so.currency)}
                        </td>
                        <td>
                            <span class="indicator-pill ${s.color}"
                                  style="font-size:11px;">
                                ${row.payment_status || "Unpaid"}
                            </span>
                        </td>
                        <td>
                            ${
								row.payment_entry
									? `<a href="/app/payment-entry/${row.payment_entry}"
                                      target="_blank" style="font-size:11px;">
                                       ${row.payment_entry}
                                   </a>`
									: `<span class="text-muted" style="font-size:11px;">—</span>`
							}
                        </td>
                    </tr>
                `;
				})
				.join("");

			$target.html(`
                <table class="table table-bordered table-condensed"
                       style="margin-top:8px; margin-bottom:0; font-size:12px;">
                    <thead style="background:var(--bg-light-gray)">
                        <tr>
                            <th style="width:30px">#</th>
                            <th>Condition</th>
                            <th>Due Date</th>
                            <th style="text-align:right">Amount</th>
                            <th>Status</th>
                            <th>Payment Entry</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `);
		},
	});
}
const DEPARTMENT_VISIBILITY = {
	sales: ["lead_details_html", "sales_tab", "resume_tab", "technical_tab", "marketing_tab"],
	resume: ["lead_details_html", "resume_tab"],
	technical: ["lead_details_html", "resume_tab", "technical_tab"],
	marketing: ["lead_details_html", "resume_tab", "technical_tab", "marketing_tab"],
};

function apply_tab_visibility(frm, department) {
	const allowed = DEPARTMENT_VISIBILITY[department] || [];
	const all_tabs = [
		"sales_tab",
		"resume_tab",
		"technical_tab",
		"marketing_tab",
		"note_tab",
		"activities_tab",
	];
	all_tabs.forEach((tab) => {
		frm.set_df_property(tab, "hidden", !allowed.includes(tab));
	});
}

function get_status_badge(status) {
	const s = (status || "").toLowerCase();
	if (s.includes("completed") || s.includes("done")) {
		return `<span class="status-badge status-success">${frappe.utils.escape_html(status)}</span>`;
	}
	if (s.includes("pending") || s.includes("open")) {
		return `<span class="status-badge status-warning">${frappe.utils.escape_html(status)}</span>`;
	}
	return `<span class="status-badge status-neutral">${frappe.utils.escape_html(status || "-")}</span>`;
}

function render_customer_history(frm, data, append_interviews = false) {
	let html = "";

	// ============================
	// COMMON STYLES
	// ============================

	const card = `
			border:1px solid #e5e7eb;
			border-radius:10px;
			padding:16px;
			margin-bottom:18px;
			background:#fff;
			box-shadow:0 1px 2px rgba(0,0,0,0.05);
		`;

	const table = `
			width:100%;
			border-collapse:collapse;
			font-size:13px;
		`;

	const th = `
			padding:8px;
			text-align:left;
			background:#f8fafc;
			color:#475569;
			font-weight:500;
		`;

	const td = `
			padding:8px;
			border-top:1px solid #f1f5f9;
			color:#334155;
		`;

	// ============================
	// CUSTOMER CREATION
	// ============================

	html += `
		<div style="${card}">
			<p><b>Customer:</b> ${data.customer.customer_name}</p>
			<p><b>Owner:</b> ${data.customer.owner}</p>
		</div>
		`;

	// ============================
	// SALES ORDER
	// ============================

	if (data.departments?.["Sales Order"]) {
		let records = data.departments["Sales Order"];

		html += `
			<div style="${card}">
				<h4 style="margin-bottom:10px;">Sales Order</h4>
				<table style="${table}">
					<thead>
						<tr>
							<th style="${th}">#</th>
							<th style="${th}">ID</th>
							<th style="${th}">Agreement</th>
						</tr>
					</thead>
					<tbody>
						${records
							.map(
								(so, i) => `
							<tr>
								<td style="${td}">${i + 1}</td>
								<td style="${td}">
									<a
										href="/app/sales-order/${so.id}"
										target="_blank"
										style="color:#260fea;font-weight:500;text-decoration:none;"
									>
										${so.id}
									</a>
								</td>
								<td style="${td}">
									${
										so.agreement && so.agreement.length
											? so.agreement
													.map(
														(ag) => `
                <div>
                    <a href="/app/agreement/${ag}" target="_blank"
                        style="color:#260fea;text-decoration:none;">
                        ${ag}
                    </a>
                </div>
            `,
													)
													.join("")
											: "-"
									}
								</td>
							</tr>
						`,
							)
							.join("")}
					</tbody>
				</table>
			</div>
			`;
	}

	// ============================
	// OTHER DEPARTMENTS
	// ============================

	if (data.departments) {
		Object.keys(data.departments).forEach((dept_name) => {
			let records = data.departments[dept_name];

			if (dept_name === "Sales Order") return;

			html += `
				<div style="${card}">
					<h4 style="margin-bottom:10px;">${dept_name}</h4>
				`;

			// ============================
			// INTERVIEW (special case)
			// ============================

			if (dept_name === "Interview") {
				html += `
	<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">

		<div style="display:flex;gap:8px;align-items:center;">

			<input type="text" id="interview-search"
				placeholder="Search company / role / status"
				style="padding:6px 10px;border:1px solid #e5e7eb;border-radius:6px;font-size:12px;" />

			From : <input type="date" id="interview-from" style="padding:6px;border:1px solid #e5e7eb;border-radius:6px;" />
			To : <input type="date" id="interview-to" style="padding:6px;border:1px solid #e5e7eb;border-radius:6px;" />

			<button id="interview-filter-btn"
		style="padding:6px 12px;background:#260fea;color:#fff;border:none;border-radius:6px;">
		Apply
	</button>

	<button id="interview-clear-btn"
		style="padding:6px 12px;background:#e5e7eb;color:#334155;border:none;border-radius:6px;">
		Clear
	</button>

		</div>
	</div>

	<!-- ✅ SCROLLABLE CONTAINER -->
	<div id="interview-container"
		style="max-height:400px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:8px;padding:10px;background:#f8fafc;">
		
		<div id="interview-list"></div>

	</div>

	<!-- ✅ LOAD MORE OUTSIDE -->
	<div id="interview-load-more" style="text-align:center;margin-top:15px;"></div>
	`;
			} else {
				// ============================
				// NORMAL DEPARTMENTS
				// ============================

				records.forEach((dept) => {
					html += `
						<div style="margin-bottom:12px;">

							<p>
								<a
									href="/app/${dept.department.toLowerCase().replace(/\s+/g, "-")}/${dept.id}"
									target="_blank"
									style="color:#260fea;font-weight:500;text-decoration:none;"
								>
									${dept.id}
								</a>
							</p>

							<p style="color:#64748b;">
								Status: ${dept.status || "-"}
							</p>

							<p style="color:#64748b;">
								Assigned: ${dept.assign_to || "-"}
							</p>

							${
								dept.resume
									? `<p><a href="${dept.resume}" target="_blank" style="color:#260fea;">View Resume</a></p>`
									: ""
							}

						</div>
						`;

					// ============================
					// SESSION TABLE
					// ============================

					if (dept.session_details?.length) {
						html += `
							<table style="${table}">
								<thead>
									<tr>
										<th style="${th}">#</th>
										<th style="${th}">Duration</th>
										<th style="${th}">Date</th>
										<th style="${th}">Projects</th>
										<th style="${th}">Quality</th>
									</tr>
								</thead>
								<tbody>
									${dept.session_details
										.map(
											(row, i) => `
										<tr>
											<td style="${td}">${i + 1}</td>
											<td style="${td}">${row.session_duration_in_hour || "-"}</td>
											<td style="${td}">${row.date || "-"}</td>
											<td style="${td}">${row.projects || "-"}</td>
											<td style="${td}">${row.quality || "-"}</td>
										</tr>
									`,
										)
										.join("")}
								</tbody>
							</table>
							`;
					}

					// ============================
					// JOB APPLICATION
					// ============================

					if (dept.job_application_count?.length) {
						html += `
							<table style="${table}">
								<thead>
									<tr>
										<th style="${th}">#</th>
										<th style="${th}">Small</th>
										<th style="${th}">Large</th>
										<th style="${th}">Total</th>
										<th style="${th}">Date</th>
									</tr>
								</thead>
								<tbody>
									${dept.job_application_count
										.map(
											(row, i) => `
										<tr>
											<td style="${td}">${i + 1}</td>
											<td style="${td}">${row.small_application || "-"}</td>
											<td style="${td}">${row.large_application || "-"}</td>
											<td style="${td}">${row.total_application || "-"}</td>
											<td style="${td}">${row.date || "-"}</td>
										</tr>
									`,
										)
										.join("")}
								</tbody>
							</table>
							`;
					}

					// ============================
					// PROOF OF WORK
					// ============================

					if (dept.proof_of_work?.length) {
						html += `
							<table style="${table}">
								<thead>
									<tr>
										<th style="${th}">#</th>
										<th style="${th}">Date</th>
										<th style="${th}">Description</th>
										<th style="${th}">Attachment</th>
									</tr>
								</thead>
								<tbody>
									${dept.proof_of_work
										.map(
											(row, i) => `
										<tr>
											<td style="${td}">${i + 1}</td>
											<td style="${td}">${row.date || "-"}</td>
											<td style="${td}">${row.description || "-"}</td>
											<td style="${td}">
												${
													row.attachments
														? `<a href="${row.attachments}" target="_blank" style="color:#260fea;">View</a>`
														: "-"
												}
											</td>
										</tr>
									`,
										)
										.join("")}
								</tbody>
							</table>
							`;
					}
				});
			}
			html += `</div>`;
		});
	}

	// ============================
	// RENDER
	// ============================

	frm.fields_dict.customer_details.$wrapper.html(html);
	render_interviews(data, append_interviews);

	$(document)
		.off("click", "#load-more-interviews")
		.on("click", "#load-more-interviews", function () {
			interview_offset += interview_limit;
			let from_date = $("#interview-from").val();
			let to_date = $("#interview-to").val();

			if (from_date && to_date && from_date > to_date) {
				frappe.msgprint("From Date cannot be greater than To Date");
				return;
			}

			frappe.call({
				method: "verp_staffing.www.customer.get_customer_history",
				args: {
					customer: cur_frm.doc.name,
					interview_limit: interview_limit,
					interview_offset: interview_offset,
					search: $("#interview-search").val(),
					from_date: $("#interview-from").val(),
					to_date: $("#interview-to").val(),
				},
				callback: function (r) {
					render_interviews(r.message, true);
				},
			});
		});

	$(document)
		.off("click", "#interview-filter-btn")
		.on("click", "#interview-filter-btn", function () {
			let search = $("#interview-search").val();
			let from_date = $("#interview-from").val();
			let to_date = $("#interview-to").val();

			// ✅ DATE VALIDATION
			if (from_date && to_date && from_date > to_date) {
				frappe.msgprint("From Date cannot be greater than To Date");
				return;
			}

			interview_offset = 0;

			frappe.call({
				method: "verp_staffing.www.customer.get_customer_history",
				args: {
					customer: cur_frm.doc.name,
					interview_limit: interview_limit,
					interview_offset: interview_offset,
					search: search,
					from_date: from_date,
					to_date: to_date,
				},
				callback: function (r) {
					render_interviews(r.message, false);
				},
			});
		});
	$(document)
		.off("click", "#interview-clear-btn")
		.on("click", "#interview-clear-btn", function () {
			// ✅ Reset inputs
			$("#interview-search").val("");
			$("#interview-from").val("");
			$("#interview-to").val("");

			// ✅ Reset pagination
			interview_offset = 0;

			// ✅ Reload default data (NO filters)
			frappe.call({
				method: "verp_staffing.www.customer.get_customer_history",
				args: {
					customer: cur_frm.doc.name,
					interview_limit: interview_limit,
					interview_offset: interview_offset,
					search: "",
					from_date: "",
					to_date: "",
				},
				callback: function (r) {
					render_interviews(r.message, false);
				},
			});
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
						<a href="/app/interview/${dept.id}" target="_blank"
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
						${r.from_time && r.to_time ? `${r.from_time} - ${r.to_time} ${r.edt_est || ""}` : "-"}
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

function customer_owner_open_update_detail_dialog(frm) {
	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_lead_detail_field_values",
		args: { customer_name: frm.doc.name },
		callback: function (r) {
			const current_values = r.message || {};

			frappe.call({
				method: "verp_staffing.crm.api.permission_request.get_customer_owner_updatable_fields",
				callback: function (fields_res) {
					const dept_fields = fields_res.message || {
						simple_fields: {},
						table_fields: {},
					};
					_open_update_detail_dialog(
						frm,
						current_values,
						dept_fields.simple_fields || {},
						dept_fields.table_fields || {},
						"owner",
					);
				},
			});
		},
	});
}

function customer_show_accept_updates(frm) {
	$(`button:contains("Accept Updates")`).closest(".btn-group").remove();
	frappe.call({
		method: "verp_staffing.crm.api.permission_request.get_all_pending_field_update_requests",
		args: { customer_name: frm.doc.name },
		callback(r) {
			$(`button:contains("Accept Updates")`).closest(".btn-group").remove();
			if (!r.message || !r.message.length) return;

			frm.add_custom_button(__("Accept Updates"), () => {
				_open_accept_updates_dialog(frm, r.message, "owner");
			});
		},
	});
}
