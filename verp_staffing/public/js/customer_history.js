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

function get_department_status_badge(status) {
	const raw = (status || "").trim();
	const key = raw.toLowerCase();

	const STYLE_MAP = {
		completed: "background:#dcfce7;color:#166534;",
		pending: "background:#fef3c7;color:#92400e;",
		"request for update": "background:#dbeafe;color:#1e40af;",
	};

	const style = STYLE_MAP[key] || "background:#f1f5f9;color:#475569;";

	return `<span class="status-badge" style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:500;white-space:nowrap;${style}">${frappe.utils.escape_html(raw || "-")}</span>`;
}

function render_link_or_text(doctype, docname, label, extra_style = "") {
	if (!docname) return "-";
	label = label || docname;

	let can_view = false;
	try {
		can_view = frappe.model.can_read(doctype);
	} catch (e) {
		can_view = false;
	}

	if (can_view) {
		const route = doctype.toLowerCase().replace(/\s+/g, "-");
		return `<a
				href="/app/${route}/${encodeURIComponent(docname)}"
				target="_blank"
				style="color:#260fea;text-decoration:none;${extra_style}"
			>${frappe.utils.escape_html(label)}</a>`;
	}

	return `<span style="color:#334155;${extra_style}">${frappe.utils.escape_html(label)}</span>`;
}

function render_truncated_text(text, limit = 80) {
	if (!text) return "-";

	const full = frappe.utils.escape_html(text);

	if (text.length <= limit) return full;

	const short = frappe.utils.escape_html(text.slice(0, limit));

	return `
		<span class="truncate-wrap">
			<span class="truncate-short">${short}&hellip;
				<a href="javascript:void(0)" class="truncate-toggle" style="color:#260fea;font-weight:500;text-decoration:none;">View more</a>
			</span>
			<span class="truncate-full" style="display:none;">${full}
				<a href="javascript:void(0)" class="truncate-toggle" style="color:#260fea;font-weight:500;text-decoration:none;">View less</a>
			</span>
		</span>
	`;
}

window.verp_staffing = window.verp_staffing || {};

window.verp_staffing.render_customer_history_widget = function (frm, opts = {}) {
	const settings = Object.assign(
		{
			fieldname: "customer_details",
			method: "verp_staffing.www.customer.get_customer_history",
			customer: frm.doc.name,
			doctype: "Customer",
			interview_limit: 5,
		},
		opts,
	);

	if (!frm.fields_dict[settings.fieldname]) {
		frappe.msgprint(__('Field "{0}" not found on this form.', [settings.fieldname]));
		return;
	}

	frm.__customer_history_state = frm.__customer_history_state || {};

	const state = {
		fieldname: settings.fieldname,
		method: settings.method,
		customer: settings.customer,
		doctype: settings.doctype,
		interview_limit: settings.interview_limit,
		interview_offset: 0,
	};

	frm.__customer_history_state[settings.fieldname] = state;

	frappe.call({
		method: state.method,
		args: {
			customer: state.customer,
			interview_limit: state.interview_limit,
			interview_offset: state.interview_offset,
		},
		callback: function (r) {
			if (!r.message) return;
			render_customer_history(frm, settings.fieldname, r.message, false);
		},
	});
};

function render_customer_history(frm, fieldname, data, append_interviews = false) {
	const state = frm.__customer_history_state[fieldname];
	let html = "";

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

	html += `
		<div style="${card}">
			<p><b>${state.doctype}:</b> ${data.customer.customer_name}</p>
			<p><b>Owner:</b> ${data.customer.owner}</p>
		</div>
		`;

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
									${render_link_or_text("Sales Order", so.id, so.id, "font-weight:500;")}
								</td>
								<td style="${td}">
									${
										so.agreement && so.agreement.length
											? so.agreement
													.map(
														(ag) => `
                <div>
                    ${render_link_or_text("Agreement", ag, ag)}
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

	console.log("data; ", data);
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

	<div id="interview-container"
		style="max-height:400px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:8px;padding:10px;background:#f8fafc;">
		
		<div id="interview-list"></div>

	</div>

	<div id="interview-load-more" style="text-align:center;margin-top:15px;"></div>
	`;
			} else {
				records.forEach((dept) => {
					html += `
						<div style="margin-bottom:12px;">

							<p>
								${render_link_or_text(dept.department, dept.id, dept.id, "font-weight:500;")}
							</p>

							<p style="color:#64748b;">
								Status: ${get_department_status_badge(dept.status)}
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

					if (dept.document_references?.length) {
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
									${dept.document_references
										.map(
											(row, i) => `
										<tr>
											<td style="${td}">${i + 1}</td>
											<td style="${td}">${row.date || "-"}</td>
											<td style="${td}">${render_truncated_text(row.description, 80)}</td>
											<td style="${td}">
												${row.document ? `<a href="${row.document}" target="_blank" style="color:#260fea;">View</a>` : "-"}
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

	frm.fields_dict[fieldname].$wrapper.html(html);
	render_interviews(data, append_interviews);

	$(document)
		.off("click", ".truncate-toggle")
		.on("click", ".truncate-toggle", function () {
			const wrap = $(this).closest(".truncate-wrap");
			wrap.find(".truncate-short").toggle();
			wrap.find(".truncate-full").toggle();
		});

	$(document)
		.off("click", "#load-more-interviews")
		.on("click", "#load-more-interviews", function () {
			state.interview_offset += state.interview_limit;
			let from_date = $("#interview-from").val();
			let to_date = $("#interview-to").val();

			if (from_date && to_date && from_date > to_date) {
				frappe.msgprint("From Date cannot be greater than To Date");
				return;
			}

			frappe.call({
				method: state.method,
				args: {
					customer: state.customer,
					interview_limit: state.interview_limit,
					interview_offset: state.interview_offset,
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

			// DATE VALIDATION
			if (from_date && to_date && from_date > to_date) {
				frappe.msgprint("From Date cannot be greater than To Date");
				return;
			}

			state.interview_offset = 0;

			frappe.call({
				method: state.method,
				args: {
					customer: state.customer,
					interview_limit: state.interview_limit,
					interview_offset: state.interview_offset,
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
			// Reset inputs
			$("#interview-search").val("");
			$("#interview-from").val("");
			$("#interview-to").val("");

			// Reset pagination
			state.interview_offset = 0;

			// Reload default data (NO filters)
			frappe.call({
				method: state.method,
				args: {
					customer: state.customer,
					interview_limit: state.interview_limit,
					interview_offset: state.interview_offset,
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
	dialog.addEventListener("click", function (e) {
		if (!e.target.closest("#feedbackBox")) {
			dialog.remove();
		}
	});

	document.body.appendChild(dialog);

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
						${render_link_or_text("Interview", dept.id, dept.id, "font-weight:600;")}

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
