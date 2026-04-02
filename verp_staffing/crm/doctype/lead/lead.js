// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead", {
	onload(frm) {
		// apply_field_readonly_for_lead_owner(frm);

		// Always keep field visible but locked
		frm.set_df_property("lead_owner", "read_only_onload", 1);

		// If lead_owner is empty → auto assign employee of logged-in user
		if (!frm.doc.lead_owner) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Employee",
					filters: { user: frappe.session.user },
					fieldname: "name",
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value("lead_owner", r.message.name);
						// Lock the field so user cannot change
						frm.set_df_property("lead_owner", "read_only", 1);
					}
				},
			});
		} else {
			// If already set → lock it
			frm.set_df_property("lead_owner", "read_only", 1);
		}

		// Stop user from selecting Converted manually
		frm.set_df_property("status", "read_only", 1);
	},

	refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);
		// apply_field_readonly_for_lead_owner(frm);

		if (frm.is_new()) return;

		// Fetch status and lead_owner from DB directly
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Lead",
				filters: { name: frm.doc.name },
				fieldname: ["status", "lead_owner"],
			},
			callback: function (lead_res) {
				if (!lead_res.message) return;

				const { status, lead_owner } = lead_res.message;

				if (status === "Opportunity") {
					frappe.call({
						method: "frappe.client.get_value",
						args: {
							doctype: "Employee",
							filters: { user: frappe.session.user },
							fieldname: "name",
						},
						callback: function (r) {
							const current_employee = r.message && r.message.name;
							const is_lead_owner = current_employee === lead_owner;

							// if (is_lead_owner) {
							// 	frm.add_custom_button(__("Request for Update"), () => {
							// 		open_request_for_update_dialog(frm);
							// 	});
							// } else {
							// 	check_and_show_give_permission_button(frm);
							// }
						},
					});
				} else {
					frm.add_custom_button("Create Opportunity", () => {
						open_create_opportunity_dialog(frm);
					});
				}
			},
		});

		if (frm.is_new()) {
			frm.add_custom_button("Show Form Tour", () => {
				const tour_name = "Lead Form";
				frm.tour.init({ tour_name }).then(() => frm.tour.start());
			});
		}

		// ─── Helpers ────────────────────────────────────────────────────────────────
		// ─── Fieldname-based overrides ───────────────────────────────────────────────
		const EMAIL_FIELDS = new Set(["email", "email_id", "email_address"]);
		const MONTH_YEAR_FIELDS = new Set(["start_date", "end_date"]);

		const isEmailField = f => EMAIL_FIELDS.has(f.toLowerCase());
		const isMonthYearField = f => MONTH_YEAR_FIELDS.has(f.toLowerCase());

		function toMonthYear(value) {
			if (!value) return "";
			const parts = value.split("-");
			return parts.length >= 2 ? `${parts[1]}-${parts[0]}` : value;
		}

		function fromMonthYear(value) {
			if (!value) return "";
			const match = value.match(/^(\d{2})-(\d{4})$/);
			return match ? `${match[2]}-${match[1]}-01` : value;
		}

		function isValidMonthYear(value) {
			const match = value.match(/^(\d{2})-(\d{4})$/);
			if (!match) return false;
			const month = parseInt(match[1], 10);
			const year = parseInt(match[2], 10);
			return month >= 1 && month <= 12 && year >= 1900 && year <= 2100;
		}

		// ─── Helpers ─────────────────────────────────────────────────────────────────

		function clearError(input) {
			input.style.border = "1px solid #ccc";
			const old = input.closest(".control-input")?.querySelector(".error-text");
			if (old) old.remove();
		}

		function markInvalid(input, message) {
			input.style.border = "1px solid red";
			const wrapper = input.closest(".control-input") || input.parentNode;
			const error = document.createElement("div");
			error.className = "error-text";
			error.style.cssText = "color:red; font-size:12px; margin-top:4px;";
			error.innerText = message;
			wrapper.appendChild(error);
		}

		function getTableColumns(child_meta) {
			return child_meta.fields.filter(f =>
				f.fieldname &&
				!f.hidden &&
				!f.read_only &&
				!["Section Break", "Column Break", "HTML", "Button", "Fold", "Heading"].includes(f.fieldtype)
			);
		}

		function getDepartmentFields(doctype_name) {
			return frappe.db.get_single_value("ERP Configuration", "department_access_form_fields")
				.then(data => {
					if (!data) return [];
					try {
						return JSON.parse(data)[doctype_name] || [];
					} catch (e) {
						console.error("Invalid JSON in department_access_form_fields", e);
						return [];
					}
				});
		}

		// ─── Input renderers ─────────────────────────────────────────────────────────

		function getInputHTML(fieldtype, value, field, meta_field) {
			value = value ?? "";
			const cls = "form-control input-with-feedback dynamic-input";
			const placeholder = `placeholder="Enter ${frappe.model.unscrub(field)}"`;

			// ── Fieldname overrides (take priority over fieldtype) ──
			if (isEmailField(field)) {
				return `<input type="email" value="${value}" data-field="${field}" data-override="email" class="${cls}" placeholder="Enter email address" />`;
			}

			if (isMonthYearField(field)) {
				return `<input type="text" value="${toMonthYear(value)}" data-field="${field}" data-override="month-year" class="${cls}" placeholder="MM-YYYY" maxlength="7" />`;
			}

			switch (fieldtype) {
				case "Date":
					return `<input type="date" value="${value.split(" ")[0] || ""}" data-field="${field}" class="${cls}" />`;

				case "Int":
				case "Float":
				case "Currency":
					return `<input type="number" value="${value}" data-field="${field}" class="${cls}" />`;

				case "Check":
					return `
				<div class="checkbox" style="margin-top:6px;">
					<input type="checkbox" data-field="${field}" class="dynamic-input" ${value ? "checked" : ""} />
				</div>`;

				case "Email":
					return `<input type="email" value="${value}" data-field="${field}" data-override="email" class="${cls}" ${placeholder} />`;

				case "Select": {
					const opts = (meta_field.options || "").split("\n").filter(Boolean);
					return `
				<select data-field="${field}" class="form-control dynamic-input">
					<option value="">Select</option>
					${opts.map(o => `<option value="${o}" ${o === value ? "selected" : ""}>${o}</option>`).join("")}
				</select>`;
				}

				case "Table": {
					const child_doctype = meta_field.options;
					if (!child_doctype) return `<div style="color:red;">No Child Doctype configured</div>`;

					const child_meta = frappe.get_meta(child_doctype);
					if (!child_meta?.fields) return `<div style="color:orange;">Child meta not loaded for: ${child_doctype}</div>`;

					const columns = getTableColumns(child_meta);
					const rows = Array.isArray(value) ? value : [];

					return `
				<div class="dynamic-table" data-field="${field}">
					<table class="table table-bordered table-sm">
						<thead>
							<tr>
								${columns.map(col => `<th>${col.label}</th>`).join("")}
								<th style="width:80px;">Action</th>
							</tr>
						</thead>
						<tbody>
							${rows.map((row, i) => `
								<tr>
									${columns.map(col => `<td>${getTableInput(col, row[col.fieldname], field, i)}</td>`).join("")}
									<td><button class="btn btn-xs btn-danger remove-row">X</button></td>
								</tr>
							`).join("")}
						</tbody>
					</table>
					<button class="btn btn-xs btn-primary add-row">+ Add Row</button>
				</div>`;
				}

				default:
					return `<input type="text" value="${value}" data-field="${field}" class="${cls}" ${placeholder} />`;
			}
		}

		function getTableInput(col, value, parent_field, rowIndex) {
			value = value ?? "";
			const attrs = `data-field="${parent_field}" data-child="${col.fieldname}" data-row="${rowIndex}" class="form-control table-input"`;

			// ── Fieldname overrides ──
			if (isEmailField(col.fieldname)) {
				return `<input type="email" value="${value}" data-field="${parent_field}" data-child="${col.fieldname}" data-row="${rowIndex}" data-override="email" class="form-control table-input" placeholder="Enter email" />`;
			}

			if (isMonthYearField(col.fieldname)) {
				return `<input type="text" value="${toMonthYear(value)}" data-field="${parent_field}" data-child="${col.fieldname}" data-row="${rowIndex}" data-override="month-year" class="form-control table-input" placeholder="MM-YYYY" maxlength="7" />`;
			}

			switch (col.fieldtype) {
				case "Date":
					return `<input type="date" value="${value.split(" ")[0] || ""}" ${attrs} />`;
				case "Int":
				case "Float":
				case "Currency":
					return `<input type="number" value="${value}" ${attrs} />`;
				case "Check":
					return `<input type="checkbox" ${value ? "checked" : ""} data-field="${parent_field}" data-child="${col.fieldname}" data-row="${rowIndex}" class="table-input" />`;
				case "Select": {
					const opts = (col.options || "").split("\n").filter(Boolean);
					return `
				<select ${attrs}>
					<option value="">Select</option>
					${opts.map(o => `<option value="${o}" ${o === value ? "selected" : ""}>${o}</option>`).join("")}
				</select>`;
				}
				case "Text":
				case "Small Text":
				case "Long Text":
					return `<textarea ${attrs}>${value}</textarea>`;
				case "Link":
					return `<input type="text" value="${value}" ${attrs} placeholder="Search..." />`;
				default:
					return `<input type="text" value="${value}" ${attrs} />`;
			}
		}

		// ─── Validation ──────────────────────────────────────────────────────────────

		function validateSingleInput(input, field_map) {
			const field = input.dataset.field;
			const meta = field_map[field];
			if (!meta || meta.fieldtype === "Table" || input.type === "checkbox") return;

			clearError(input);

			const value = input.value.trim();
			const label = meta.label || frappe.model.unscrub(field);
			const override = input.dataset.override;

			if (meta.reqd && !value) {
				return markInvalid(input, `${label} is required`);
			}
			if (override === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
				return markInvalid(input, `${label} must be a valid email address`);
			}
			if (override === "month-year" && value && !isValidMonthYear(value)) {
				return markInvalid(input, `${label} must be in MM-YYYY format (e.g. 06-2023)`);
			}
			if (["Int", "Float", "Currency"].includes(meta.fieldtype) && value && isNaN(value)) {
				return markInvalid(input, `${label} must be a number`);
			}
			if (meta.fieldtype === "Date" && value && isNaN(Date.parse(value))) {
				return markInvalid(input, `${label} must be a valid date`);
			}
		}

		function validateWithMeta(field_map) {
			let isValid = true;
			let firstInvalid = null;

			document.querySelectorAll(".dynamic-input").forEach(input => {
				const field = input.dataset.field;
				const meta = field_map[field];
				if (!meta || meta.fieldtype === "Table") return;

				clearError(input);

				const value = input.type === "checkbox" ? (input.checked ? 1 : 0) : input.value;
				const label = meta.label || frappe.model.unscrub(field);
				const override = input.dataset.override;

				const fail = (msg) => {
					markInvalid(input, msg);
					isValid = false;
					if (!firstInvalid) firstInvalid = input;
				};

				if (meta.reqd && !value && input.type !== "checkbox") {
					return fail(`${label} is required`);
				}
				if (override === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
					return fail(`${label} must be a valid email address`);
				}
				if (override === "month-year" && value && !isValidMonthYear(value)) {
					return fail(`${label} must be in MM-YYYY format (e.g. 06-2023)`);
				}
				if (meta.fieldtype === "Select" && value) {
					const opts = (meta.options || "").split("\n");
					if (!opts.includes(value)) return fail(`${label} must be a valid option`);
				}
				if (["Int", "Float", "Currency"].includes(meta.fieldtype) && value && isNaN(value)) {
					return fail(`${label} must be a number`);
				}
				if (meta.fieldtype === "Date" && value && isNaN(Date.parse(value))) {
					return fail(`${label} must be a valid date`);
				}
			});

			if (firstInvalid) {
				firstInvalid.focus();
				firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
			}

			return isValid;
		}

		// ─── Data collection ─────────────────────────────────────────────────────────

		function collectFormData(field_map) {
			const data = {};

			document.querySelectorAll(".dynamic-input").forEach(input => {
				const meta = field_map[input.dataset.field];
				if (!meta || meta.fieldtype === "Table") return;

				let val = input.type === "checkbox" ? (input.checked ? 1 : 0) : input.value;
				if (input.dataset.override === "month-year" && val) val = fromMonthYear(val);

				data[input.dataset.field] = val;
			});

			document.querySelectorAll(".dynamic-table").forEach(table => {
				const field = table.dataset.field;
				const child_doctype = field_map[field].options;
				const rows = [];

				table.querySelectorAll("tbody tr").forEach(tr => {
					const row = {};
					tr.querySelectorAll("input, select, textarea").forEach(input => {
						const child_field = input.dataset.child;
						if (!child_field) return;
						let val = input.type === "checkbox" ? (input.checked ? 1 : 0) : input.value;
						if (input.dataset.override === "month-year" && val) val = fromMonthYear(val);
						row[child_field] = val;
					});
					if (Object.values(row).some(v => v !== "" && v !== 0 && v !== null)) {
						rows.push({
							...row,
							doctype: child_doctype,
							parent: frm.doc.name1,
							parentfield: field,
							parenttype: "Lead Detail Form"
						});
					}
				});

				data[field] = rows;
			});

			return data;
		}

		// ─── Event binding ───────────────────────────────────────────────────────────

		function attachLiveValidation(field_map) {
			document.querySelectorAll(".dynamic-input").forEach(input => {
				input.addEventListener("input", () => clearError(input));
				input.addEventListener("blur", () => validateSingleInput(input, field_map));
			});

			document.querySelectorAll(".dynamic-table").forEach(table => {
				const field = table.dataset.field;
				const child_doctype = field_map[field].options;
				const child_meta = frappe.get_meta(child_doctype);
				const columns = getTableColumns(child_meta);
				const tbody = table.querySelector("tbody");

				table.querySelector(".add-row").onclick = () => {
					const rowIndex = tbody.querySelectorAll("tr").length;
					const row_html = `
				<tr>
					${columns.map(col => `<td>${getTableInput(col, "", field, rowIndex)}</td>`).join("")}
					<td><button class="btn btn-xs btn-danger remove-row">X</button></td>
				</tr>`;
					tbody.insertAdjacentHTML("beforeend", row_html);
				};

				table.addEventListener("click", e => {
					if (e.target.classList.contains("remove-row")) {
						e.target.closest("tr").remove();
					}
				});
			});
		}

		// ─── Main entry point ────────────────────────────────────────────────────────

		getDepartmentFields("Lead").then(async fields => {
			const lead_detail_name = frm.doc.name1;
			if (!lead_detail_name) return;

			const [doc, meta] = await Promise.all([
				frappe.db.get_doc("Lead Detail Form", lead_detail_name),
				frappe.db.get_doc("DocType", "Lead Detail Form")
			]);

			await Promise.all(
				meta.fields
					.filter(f => f.fieldtype === "Table" && f.options)
					.map(f => frappe.model.with_doctype(f.options))
			);

			const field_map = Object.fromEntries(meta.fields.map(f => [f.fieldname, f]));

			const formFields = fields.map(field => {
				const meta_field = field_map[field];
				if (!meta_field) return "";

				const label = meta_field.label || frappe.model.unscrub(field);
				const isFullWidth = ["Table", "Text Editor", "Long Text", "HTML"].includes(meta_field.fieldtype);

				return `
			<div style="width:${isFullWidth ? "100%" : "calc(50% - 8px)"}; min-width:${isFullWidth ? "100%" : "250px"};">
				<div class="frappe-control">
					<div class="control-label" style="margin-bottom:6px;">
						${label}
						${meta_field.reqd ? '<span style="color:red;">*</span>' : ""}
					</div>
					<div class="control-input">
						${getInputHTML(meta_field.fieldtype, doc[field], field, meta_field)}
					</div>
				</div>
			</div>`;
			}).join("");

			const html = `
		<div class="form-layout">
			<div class="form-section">
				<div class="section-head">Lead Detail Form</div>
				<div class="section-body">
					<div style="display:flex; flex-wrap:wrap; gap:16px;">
						${formFields}
					</div>
					<div style="margin-top:20px;">
						<button class="btn btn-primary btn-sm" id="save_dynamic_btn">Save</button>
					</div>
				</div>
			</div>
		</div>`;

			frm.set_df_property("lead_detail", "options", html);

			setTimeout(() => {
				const btn = document.getElementById("save_dynamic_btn");
				if (!btn) return;

				attachLiveValidation(field_map);

				btn.onclick = async () => {
					if (!validateWithMeta(field_map)) {
						frappe.msgprint("Please fix highlighted fields before saving.");
						return;
					}

					const data = collectFormData(field_map);
					btn.innerText = "Saving...";
					btn.disabled = true;

					try {
						const latest_doc = await frappe.db.get_doc("Lead Detail Form", frm.doc.name1);
						Object.assign(latest_doc, data);

						await frappe.call({
							method: "frappe.client.save",
							args: { doc: latest_doc }
						});

						frappe.show_alert({ message: "Saved successfully", indicator: "green" });
					} catch (err) {
						console.error("Save error:", err);
						frappe.msgprint("An error occurred while saving. Please try again.");
					} finally {
						btn.innerText = "Save";
						btn.disabled = false;
					}
				};
			}, 300);
		});

		const roles = frappe.user_roles;

		if (roles.includes("Extra Menu Item Not Show")) {
			const hideElements = ({ selectors = [], keywordSelectors = [], keywords = [] }) => {
				selectors.forEach((sel) => {
					const el = document.querySelector(sel);
					if (el) el.style.display = "none";
				});
				keywordSelectors.forEach((sel) => {
					document.querySelectorAll(sel).forEach((el) => {
						const text = el.innerText?.trim();
						if (text && keywords.some((k) => text.includes(k))) {
							el.style.display = "none";
							const li = el.closest("li");
							if (li) li.style.display = "none";
						}
					});
				});
			};

			const MENU_HIDE = ["Links", "Duplicate", "Copy to Clipboard"];

			const cleanMenu = () => {
				MENU_HIDE.forEach((label) => {
					try {
						frm.page.remove_menu_item(label);
					} catch {}
				});
				hideElements({
					keywordSelectors: [".dropdown-menu .dropdown-item"],
					keywords: MENU_HIDE,
				});
			};

			$(frm.page.wrapper).on("shown.bs.dropdown", cleanMenu);

			const SIDEBAR_KEYWORDS = ["Assigned", "Share"];

			const cleanSidebar = () => {
				hideElements({
					selectors: [
						".form-sidebar .assigned-to",
						".form-sidebar .btn-share",
						".form-sidebar .shared-with",
					],
					keywordSelectors: [".form-sidebar *"],
					keywords: SIDEBAR_KEYWORDS,
				});
			};

			const runCleanup = () => {
				cleanMenu();
				cleanSidebar();
			};
			runCleanup();

			let attempts = 0;
			const timer = setInterval(() => {
				runCleanup();
				if (attempts++ > 12) clearInterval(timer);
			}, 200);
		}

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Lead Form";
			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});
	},
});

// this code is unnessary if allthing working right so remove it

// frappe.ui.form.on("Lead Course", {
// 	start_date(frm, cdt, cdn) {
// 		let row = locals[cdt][cdn];
// 		window.LeadCourse.check_row(row);
// 	},
// 	end_date(frm, cdt, cdn) {
// 		let row = locals[cdt][cdn];
// 		window.LeadCourse.check_row(row);
// 	},
// 	grade(frm, cdt, cdn) {
// 		let row = locals[cdt][cdn];
// 		window.LeadCourse.check_row(row);
// 	},
// });

// function open_request_for_update_dialog(frm) {
// 	frappe.call({
// 		method: "verp_staffing.crm.api.permission_request._check_permission_status",
// 		args: { ref_doctype: frm.doctype, ref_name: frm.doc.name },
// 		callback(r) {
// 			const status = r.message && r.message.status;

// 			// if (status === "approved") {
// 			// 	// Permission still active — redirect to Lead Detail Form
// 			// 	redirect_to_lead_detail_form(frm);
// 			// 	return;
// 			// }

// 			if (status === "expired") {
// 				frappe.show_alert(
// 					{
// 						message: __(
// 							"Your previous permission has expired. You can request again.",
// 						),
// 						indicator: "orange",
// 					},
// 					5,
// 				);
// 			} else if (status === "pending") {
// 				frappe.show_alert(
// 					{
// 						message: __(
// 							"Your request is already pending. Please wait for your manager to approve it.",
// 						),
// 						indicator: "orange",
// 					},
// 					5,
// 				);
// 				return;
// 			}

// 			// Show dialog to enter reason
// 			const dialog = new frappe.ui.Dialog({
// 				title: __("Request Permission to Update Email"),
// 				fields: [
// 					{
// 						fieldname: "reason",
// 						fieldtype: "Small Text",
// 						label: __("Reason for Update"),
// 						reqd: 1,
// 						description: __(
// 							"Explain why you need to edit the email field on this Lead.",
// 						),
// 					},
// 				],
// 				primary_action_label: __("Send Request"),
// 				primary_action(values) {
// 					dialog.hide();
// 					frappe.call({
// 						method: "verp_staffing.crm.api.permission_request._request_permission",
// 						args: {
// 							ref_doctype: frm.doctype,
// 							ref_name: frm.doc.name,
// 							reason: values.reason,
// 						},
// 						// freeze: true,
// 						// freeze_message: __("Sending request to your manager..."),
// 						callback(res) {
// 							if (res.message && res.message.status === "success") {
// 								frappe.show_alert(
// 									{
// 										message: __(
// 											`Request sent to manager <b>${res.message.manager_employee}</b>. You will be notified when permission is granted.`,
// 										),
// 										indicator: "blue",
// 									},
// 									7,
// 								);
// 							}
// 						},
// 					});
// 				},
// 			});

// 			dialog.show();
// 		},
// 	});
// }

// function check_and_show_give_permission_button(frm) {
// 	frappe.call({
// 		method: "verp_staffing.crm.api.permission_request._check_pending_for_manager",
// 		args: { ref_doctype: frm.doctype, ref_name: frm.doc.name },
// 		callback(r) {
// 			if (!r.message || !r.message.has_pending) return;

// 			const { requested_by, reason } = r.message;

// 			$(`button:contains("Give Permission")`).closest(".btn-group").remove();

// 			frm.add_custom_button(__("Give Permission"), () => {
// 				// Dialog with Approve AND Decline
// 				const perm_dialog = new frappe.ui.Dialog({
// 					title: __("Permission Request"),
// 					fields: [
// 						{
// 							fieldtype: "HTML",
// 							fieldname: "request_info",
// 							options: `
//                                 <div style="padding: 10px 0;">
//                                     <p>
//                                         <b>${requested_by}</b> has requested permission
//                                         to update the email field on this Lead.
//                                     </p>
//                                     <p><b>Reason:</b> ${reason}</p>
//                                     <p>
//                                         If approved, permission will be valid for
//                                         <b>${r.message.expires_in_minutes} minutes</b> only.
//                                     </p>
//                                 </div>
//                             `,
// 						},
// 					],
// 					primary_action_label: __("Approve"),
// 					primary_action() {
// 						perm_dialog.hide();
// 						frappe.call({
// 							method: "verp_staffing.crm.api.permission_request._give_permission",
// 							args: { ref_doctype: frm.doctype, ref_name: frm.doc.name },
// 							callback(res) {
// 								if (res.message && res.message.status === "approved") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												`Permission granted for ${res.message.expires_in_minutes} minutes. <b>${requested_by}</b> has been notified.`,
// 											),
// 											indicator: "green",
// 										},
// 										6,
// 									);
// 									frm.reload_doc();
// 								}
// 							},
// 						});
// 					},
// 					secondary_action_label: __("Decline"),
// 					secondary_action() {
// 						perm_dialog.hide();
// 						frappe.call({
// 							method: "verp_staffing.crm.api.permission_request._decline_permission",
// 							args: { ref_doctype: frm.doctype, ref_name: frm.doc.name },
// 							callback(res) {
// 								if (res.message && res.message.status === "declined") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												`Request declined. <b>${requested_by}</b> has been notified.`,
// 											),
// 											indicator: "red",
// 										},
// 										6,
// 									);
// 									frm.reload_doc();
// 								}
// 							},
// 						});
// 					},
// 				});
// 				perm_dialog.show();
// 			});
// 		},
// 	});
// }

// // make field read only after lead become opportunity

// function apply_field_readonly_for_lead_owner(frm) {
// 	if (frm.is_new()) return;

// 	// Fetch lead_owner and status directly from DB
// 	// because frm.doc may not have them loaded yet
// 	frappe.call({
// 		method: "frappe.client.get_value",
// 		args: {
// 			doctype: "Lead",
// 			filters: { name: frm.doc.name },
// 			fieldname: ["status", "lead_owner"],
// 		},
// 		callback: function (lead_res) {
// 			if (!lead_res.message) return;

// 			const { status, lead_owner } = lead_res.message;

// 			if (status !== "Opportunity") return;

// 			// Check if logged-in user is the lead owner
// 			frappe.call({
// 				method: "frappe.client.get_value",
// 				args: {
// 					doctype: "Employee",
// 					filters: { user: frappe.session.user },
// 					fieldname: "name",
// 				},
// 				callback: function (emp_res) {
// 					if (!emp_res.message) return;
// 					if (emp_res.message.name !== lead_owner) return;

// 					// Lead owner — always lock source
// 					frm.set_df_property("source", "read_only", 1);
// 					frm.refresh_field("source");

// 					// Check permission status for email
// 					frappe.call({
// 						method: "verp_staffing.crm.api.permission_request._check_permission_status",
// 						args: {
// 							ref_doctype: "Lead",
// 							ref_name: frm.doc.name,
// 						},
// 						callback: function (perm_res) {
// 							const perm = perm_res.message && perm_res.message.status;

// 							if (perm === "approved") {
// 								frm.set_df_property("email", "read_only", 0);
// 								frm.refresh_field("email");
// 								frappe.show_alert(
// 									{
// 										message: __(
// 											"Permission granted. You can now update the email field.",
// 										),
// 										indicator: "green",
// 									},
// 									5,
// 								);
// 							} else {
// 								frm.set_df_property("email", "read_only", 1);
// 								frm.refresh_field("email");

// 								if (perm === "pending") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												"Email is locked. Your permission request is pending manager approval.",
// 											),
// 											indicator: "orange",
// 										},
// 										5,
// 									);
// 								} else if (perm === "declined") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												"Email is locked. Your permission request was declined. Please request again.",
// 											),
// 											indicator: "red",
// 										},
// 										5,
// 									);
// 								} else if (perm === "expired") {
// 									frappe.show_alert(
// 										{
// 											message: __(
// 												"Email is locked. Your permission has expired. Please request again.",
// 											),
// 											indicator: "orange",
// 										},
// 										5,
// 									);
// 								}
// 							}
// 						},
// 					});
// 				},
// 			});
// 		},
// 	});
// }

function open_create_opportunity_dialog(frm) {
	if (frm.is_dirty()) {
		frm.save().then(() => {
			open_create_opportunity_dialog(frm);
		});
		return;
	}

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Opportunity",
			filters: { opportunity_from_lead: frm.doc.name },
			limit_page_length: 1,
		},
		callback: function (r) {
			if (r.message && r.message.length > 0) {
				frappe.msgprint({
					title: __("Error"),
					message: __("An Opportunity already exists for this Lead."),
					indicator: "red",
				});
			} else {
				const dialog = new frappe.ui.Dialog({
					title: __("Create Opportunity from Lead"),
					fields: [
						{
							fieldname: "manual_assign",
							fieldtype: "Check",
							label: "Want to assign Opportunity Owner Manually?",
						},
						{
							fieldname: "opportunity_owner",
							label: "Opportunity Owner",
							fieldtype: "Link",
							options: "Employee",
							depends_on: "eval:doc.manual_assign == 1",
							mandatory_depends_on: "eval:doc.manual_assign == 1",
							get_query() {
								return { filters: { department: "Sales" } };
							},
						},
					],
					primary_action_label: __("Create"),
					primary_action(values) {
						dialog.hide();
						if (values.manual_assign) {
							create_opportunity(frm, values.opportunity_owner);
						} else {
							frappe.call({
								method: "verp_staffing.crm.api.auto_assign.get_auto_assign_employee",
								args: {
									department: "Sales",
									target_doctype: "Opportunity",
									owner_field: "opportunity_owner",
								},
								callback(r) {
									if (r.message) {
										create_opportunity(frm, r.message);
									}
								},
							});
						}
					},
				});
				dialog.show();
			}
		},
	});
}

function create_opportunity(frm, owner) {
	frappe.call({
		method: "frappe.client.insert",
		args: {
			doc: {
				doctype: "Opportunity",
				opportunity_from_lead: frm.doc.name,
				opportunity_owner: owner,
				name1: frm.doc.name1,
			},
		},
		callback: function (response) {
			frm.reload_doc();
			if (!response.exc && response.message) {
				frappe.msgprint({
					title: "Success",
					message: "Opportunity Created",
					indicator: "green",
				});
				frm.reload_doc();
			}
		},
		error: function (err) {
			frappe.msgprint({
				title: __("Error"),
				message: err && err.exc ? err.exc : __("Failed to create Opportunity"),
				indicator: "red",
			});
		},
	});
}
