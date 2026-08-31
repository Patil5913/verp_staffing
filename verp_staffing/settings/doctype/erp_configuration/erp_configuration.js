// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

let email_config_rows = [];
let active_frm = null; // tracks current form so document-level handlers below can reach it

frappe.ui.form.on("ERP Configuration", {
	async refresh(frm) {
		active_frm = frm;
		set_department_role_filters(frm);
		render_website_app_settings(frm);
		setup_permission_table_filters(frm);
		if (!frm.doc.is_sample_data_removed) {
			add_remove_sample_data_button(frm);
		}
		await render_headlines(frm);
		// Load from doc into memory, then render
		try {
			email_config_rows = JSON.parse(frm.doc.email_configuration_detail || "[]");
		} catch {
			email_config_rows = [];
		}
		render_email_configurator(frm);

		frappe.call({
			method: "verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_services",
			callback(r) {
				const services = r.message || [];
				const servicesPlus = [...services, "Lead", "Customer"];
				const servicesPlusFordisplay = [...services, "Customer", "Opportunity"];

				render_field_selector_widget(
					frm,
					"select_candidate_details_form_fields_html",
					"candidate_details_form_fields",
					"candidate_form",
					services,
				);

				render_field_selector_widget(
					frm,
					"select_department_display_form_fields_html",
					"department_display_form_fields",
					"department_display",
					servicesPlusFordisplay,
				);

				render_field_selector_widget(
					frm,
					"department_access_fields",
					"department_access_form_fields",
					"department_access",
					servicesPlus,
				);
			},
		});
	},

	async before_save(frm) {
		// Capture any manually typed email values
		let wrapper = frm.get_field("email_configuration").$wrapper;
		wrapper.find(".email-account").each(function (i) {
			if (email_config_rows[i] !== undefined) {
				email_config_rows[i].email_account = $(this).val();
			}
		});

		frm.doc.email_configuration_detail = JSON.stringify(email_config_rows);
		frm.dirty();

		// Flush every staged System Settings edit as one request. Awaited
		// so the ERP Configuration save doesn't proceed if this fails —
		// you don't want the doc reporting "saved" while System Settings
		// silently didn't update.
		await flush_system_settings_changes();
	},
});

async function render_headlines(frm) {
	if (frm.__headline_rendered_for === frm.doc.name) return;
	frm.__headline_rendered_for = frm.doc.name;

	frm.dashboard.clear_headline();

	const r = await frappe.call({
		method: "verp_staffing.utils.onboarding_setup_helper.get_setup_progress",
	});

	const progress = r.message;

	if (!["pdf_agreement_template", "completed"].includes(progress.current_step)) {
		return;
	}

	const configs = {
		pdf_agreement_template: {
			color: "blue",
			message:
				"Configuration is complete. Create an agreement template so candidate agreements can be generated automatically.",
			button: "Create Agreement Template →",
			action: () => frappe.new_doc("Pdf Agreement Template"),
		},

		completed: {
			color: "blue",
			message: "Excellent. Your ERP setup is complete and ready for operations.",
			button: "Open Workspace →",
			action: () => frappe.set_route("workspace"),
		},
	};

	const cfg = configs[progress.current_step];

	frm.dashboard.set_headline_alert(
		__(
			`${cfg.message}
			<a href="#"
				class="btn btn-sm btn-primary onboarding-next-step"
				style="margin-left:8px;vertical-align:middle;">
				${cfg.button}
			</a>`,
		),
		cfg.color,
	);

	frm.page.wrapper
		.find(".onboarding-next-step")
		.off("click")
		.on("click", function (e) {
			e.preventDefault();
			cfg.action();
		});
}

const TYPE_OPTIONS = [
	"HR",
	"Contact",
	"Notification",
	"Support",
	"Sales",
	"Finance",
	"Marketing",
	"Operations",
];

function render_email_configurator(frm) {
	// Use module-level email_config_rows (already loaded in refresh)
	let data = email_config_rows;

	// Collect all used types across ALL rows
	let all_used_types = new Set();
	data.forEach((row) => {
		(row.types || []).forEach((t) => all_used_types.add(t));
	});

	let html = `
	<style>
	.custom-grid {
		border: 1px solid var(--border-color);
		border-radius: 6px;
		background: var(--fg-color);
		margin-bottom: 0;
		overflow: hidden;
	}
	.custom-grid table {
		width: 100%;
		border-collapse: collapse;
	}
	.custom-grid thead {
		background: var(--subtle-accent);
		font-size: 12px;
		color: var(--text-muted);
	}
	.custom-grid th {
		padding: 8px 10px;
		font-weight: 600;
		border-bottom: 1px solid var(--border-color);
		text-align: left;
	}
	.custom-grid td {
		padding: 6px 10px;
		border-bottom: 1px solid var(--border-color-light);
		vertical-align: middle;
	}
	.custom-grid tbody tr:last-child td {
		border-bottom: none;
	}
	.custom-grid tr:hover td {
		background: var(--highlight-color);
	}
	.custom-grid .form-control {
		border: none;
		background: transparent;
		height: 26px;
		padding: 2px 4px;
		color: var(--text-color);
		width: 100%;
		outline: none;
	}
	.custom-grid .form-control:focus {
		background: var(--fg-color);
		border: 1px solid var(--border-color);
		border-radius: 4px;
	}
	.grid-footer {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 0;
		margin-top: 2px;
	}
	.grid-footer .btn-delete {
		background: #e24c4c;
		color: #fff;
		border: 1px solid #e24c4c;
		padding: 3px 10px;
		font-size: 12px;
		border-radius: 5px;
		line-height: 1.5;
		cursor: pointer;
	}
	.grid-footer .btn-delete:hover {
		background: #c0392b;
		border-color: #c0392b;
	}
	.grid-footer .btn-add-row {
		background: var(--fg-color);
		color: var(--text-color);
		border: 1px solid var(--border-color);
		padding: 3px 10px;
		font-size: 12px;
		border-radius: 5px;
		line-height: 1.5;
		cursor: pointer;
	}
	.grid-footer .btn-add-row:hover {
		background: var(--subtle-accent);
	}
	.chip {
		display: inline-flex;
		align-items: center;
		background: var(--gray-200);
		color: var(--text-color);
		padding: 2px 8px;
		margin: 2px 2px 2px 0;
		border-radius: 999px;
		font-size: 11px;
		gap: 4px;
	}
	.chip .remove-type {
		cursor: pointer;
		color: var(--text-muted);
		font-size: 13px;
		line-height: 1;
	}
	.chip .remove-type:hover {
		color: var(--red-500);
	}
	.types-cell {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 2px;
	}
	.type-select {
		border: none !important;
		background: transparent !important;
		font-size: 12px;
		color: var(--text-muted);
		cursor: pointer;
		padding: 2px 4px;
		outline: none;
		max-width: 130px;
	}
	.custom-grid input[type="checkbox"] {
		transform: scale(0.9);
		cursor: pointer;
	}
	.custom-grid td:first-child,
	.custom-grid th:first-child {
		padding-left: 10px;
		width: 30px;
	}
	.custom-grid th:nth-child(2),
	.custom-grid td:nth-child(2) {
		width: 50px;
	}
	</style>

	<div class="custom-grid">
		<table>
			<thead>
				<tr>
					<th><input type="checkbox" class="select-all"></th>
					<th>No.</th>
					<th>Email Account</th>
					<th>Types</th>
				</tr>
			</thead>
			<tbody>
				${data
					.map((row, i) => {
						let row_types = row.types || [];
						// Exclude types used in other rows; allow types already in this row
						let selectable_types = TYPE_OPTIONS.filter(
							(t) => !all_used_types.has(t) || row_types.includes(t),
						).filter((t) => !row_types.includes(t));

						return `
					<tr data-idx="${i}">
						<td><input type="checkbox" class="row-check"></td>
						<td>${i + 1}</td>
						<td>
							<input type="text"
								class="form-control email-account link-field"
								data-doctype="Email Account"
								value="${frappe.utils.escape_html(row.email_account || "")}"
								placeholder="Select Email Account">
						</td>
						<td>
							<div class="types-cell">
								${row_types
									.map(
										(t) => `
									<span class="chip">
										${frappe.utils.escape_html(t)}
										<span class="remove-type" data-type="${t}">×</span>
									</span>
								`,
									)
									.join("")}
								${
									selectable_types.length > 0
										? `<select class="type-select">
										<option value="">Select Type</option>
										${selectable_types.map((opt) => `<option value="${opt}">${opt}</option>`).join("")}
									</select>`
										: `<span style="font-size:11px;color:var(--text-muted)">All types used</span>`
								}
							</div>
						</td>
					</tr>`;
					})
					.join("")}
			</tbody>
		</table>
	</div>

	<div class="grid-footer">
		<button class="btn-delete delete-selected">Delete</button>
		<button class="btn-add-row add-row">+ Add Row</button>
	</div>
	`;

	let wrapper = frm.get_field("email_configuration").$wrapper;
	wrapper.html(html);

	init_link_fields(wrapper, frm);
	init_multi_select(wrapper, frm);
	init_select_all(wrapper);
}

function init_link_fields(wrapper, frm) {
	wrapper.find(".link-field").each(function () {
		let input = this;
		let doctype = $(this).data("doctype");

		let awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 20,
			autoFirst: true,
			list: [],
		});

		input.awesomplete = awesomplete;

		$(input).on("focus input", function () {
			frappe.call({
				method: "frappe.desk.search.search_link",
				args: {
					doctype: doctype,
					txt: input.value || "",
					ignore_user_permissions: 0,
					reference_doctype: frm.doctype,
				},
				callback: function (r) {
					if (r.message) {
						awesomplete.list = r.message.map((d) => d.value);
						awesomplete.evaluate();
					}
				},
			});
		});

		// On awesomplete selection — update in-memory only
		$(input).on("awesomplete-selectcomplete", function () {
			let idx = $(input).closest("tr").data("idx");
			if (email_config_rows[idx] !== undefined) {
				email_config_rows[idx].email_account = input.value;
			}
		});
	});
}

function init_multi_select(wrapper, frm) {
	wrapper.find(".type-select").on("change", function () {
		let value = $(this).val();
		if (!value) return;

		let idx = $(this).closest("tr").data("idx");
		if (!email_config_rows[idx]) return;
		if (!email_config_rows[idx].types) email_config_rows[idx].types = [];

		if (!email_config_rows[idx].types.includes(value)) {
			email_config_rows[idx].types.push(value);
		}

		render_email_configurator(frm);
	});
}

function init_select_all(wrapper) {
	wrapper.find(".select-all").on("change", function () {
		let checked = $(this).is(":checked");
		wrapper.find(".row-check").prop("checked", checked);
	});
}

// ADD ROW — in-memory only
$(document).on("click", ".add-row", function () {
	email_config_rows.push({ email_account: "", types: [] });
	render_email_configurator(active_frm);
});

// DELETE SELECTED ROWS — in-memory only
$(document).on("click", ".delete-selected", function () {
	let frm = active_frm;
	let wrapper = frm.get_field("email_configuration").$wrapper;

	let remaining = [];
	wrapper.find(".row-check").each(function (i) {
		if (!$(this).is(":checked")) {
			remaining.push(email_config_rows[i]);
		}
	});

	email_config_rows = remaining;
	render_email_configurator(frm);
});

// EMAIL INPUT — update in-memory only (no save, no re-render)
$(document).on("input", ".email-account", function () {
	let idx = $(this).closest("tr").data("idx");
	if (email_config_rows[idx] !== undefined) {
		email_config_rows[idx].email_account = $(this).val();
	}
});

// REMOVE TYPE CHIP — in-memory only
$(document).on("click", ".remove-type", function () {
	let type = $(this).data("type");
	let idx = $(this).closest("tr").data("idx");

	if (email_config_rows[idx]) {
		email_config_rows[idx].types = (email_config_rows[idx].types || []).filter(
			(t) => t !== type,
		);
		render_email_configurator(active_frm);
	}
});

// ── Department roles cache ────────────────────────────────────────────────────
const DEPT_ROLES_CACHE = {};

function fetch_department_roles(dept_name, callback) {
	if (DEPT_ROLES_CACHE[dept_name]) {
		callback(DEPT_ROLES_CACHE[dept_name]);
		return;
	}
	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Department", name: dept_name },
		callback: function (r) {
			let roles = [];
			if (r?.message?.role && Array.isArray(r.message.role)) {
				roles = r.message.role.map((row) => row.role).filter(Boolean);
			}
			DEPT_ROLES_CACHE[dept_name] = roles;
			callback(roles);
		},
	});
}

// ── Child table filters ───────────────────────────────────────────────────────
function setup_permission_table_filters(frm) {
	frm.set_query("department", "table_tpxt", function (doc, cdt, cdn) {
		const already_selected = (doc.table_tpxt || [])
			.filter((row) => row.name !== cdn && row.department)
			.map((row) => row.department);

		const filters = [];

		if (already_selected.length) {
			filters.push(["Department", "name", "not in", already_selected]);
		}

		// Exclude the three departments that should never appear
		filters.push(["Department", "name", "not in", ["HR", "Lead", "Resume"]]);

		return { filters };
	});

	// Filter role field — only show roles belonging to selected department
	frm.set_query("role", "table_tpxt", function (doc, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		const selected_dept = row && row.department;

		if (!selected_dept) {
			// No department chosen yet — show nothing
			return {
				filters: [["Role", "name", "in", []]],
			};
		}

		const roles = DEPT_ROLES_CACHE[selected_dept] || [];
		return {
			filters: [["Role", "name", "in", roles]],
		};
	});
}

// ── Clear role when department changes in child table ─────────────────────────
frappe.ui.form.on("Permission Request Configuration", {
	department(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);

		// Clear the role whenever department changes
		frappe.model.set_value(cdt, cdn, "role", null);

		// Trigger role fetch so cache is warm for instant filter
		if (row.department) {
			fetch_department_roles(row.department, () => {
				// Refresh role field query after cache is ready
				frm.refresh_field("table_tpxt");
			});
		}
	},
});

function set_department_role_filters(frm) {
	const dept_field_map = {
		sales_department: "Sales",
		technical_department: "Technical",
		marketing_department: "Marketing",
	};

	Object.entries(dept_field_map).forEach(([field, dept_name]) => {
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Department",
				name: dept_name,
			},
			callback: function (r) {
				let roles = [];
				if (r?.message?.role && Array.isArray(r.message.role)) {
					roles = r.message.role.map((row) => row.role).filter((role) => role);
				}
				if (!roles.length) return;

				frm.set_query(field, function () {
					return {
						filters: [["Role", "name", "in", roles]],
					};
				});
			},
		});
	});
}

const SERVICE_ICONS = {
	marketing: "📣",
	resume: "📄",
	"cover letter": "✉️",
	ruc: "🗂️",
	training: "🎓",
	jdc: "📋",
	"background check": "🔍",
	"reference check": "👥",
	"drug test": "🧪",
	"employment verification": "🏢",
	"education check": "🎒",
	"credit check": "💳",
	onboarding: "🚀",
	interview: "💬",
	assessment: "📝",
};

const SPECIAL_ICONS = {
	lead: "🎯",
};

function getItemIcon(name) {
	const k = (name || "").toLowerCase();
	return SPECIAL_ICONS[k] || SERVICE_ICONS[k] || "⚙️";
}

function escapeQ(s) {
	return (s || "").replace(/"/g, "&quot;");
}

function getFieldTypeBadge(fieldtype) {
	const MAP = {
		Data: ["TEXT", "#1E3A5F", "#E8EEF5"],
		"Small Text": ["TEXT", "#1E3A5F", "#E8EEF5"],
		"Long Text": ["TEXT", "#1E3A5F", "#E8EEF5"],
		Text: ["TEXT", "#1E3A5F", "#E8EEF5"],
		Link: ["LINK", "#3C3489", "#EEEDFE"],
		Select: ["SELECT", "#7A3B00", "#FFF0D6"],
		Check: ["CHECKBOX", "#0D5C63", "#D6F4F5"],
		Date: ["DATE", "#2C3E6B", "#E4E9F5"],
		Datetime: ["DATETIME", "#2C3E6B", "#E4E9F5"],
		Int: ["NUMBER", "#2A2A2A", "#ECECEC"],
		Float: ["NUMBER", "#2A2A2A", "#ECECEC"],
		Currency: ["CURRENCY", "#1B4D2E", "#D6F0E0"],
		Attach: ["FILE", "#6B2D0F", "#FAE8DF"],
		"Attach Image": ["IMAGE", "#7A1F3D", "#FAE0EA"],
		Table: ["TABLE", "#0D2645", "#D6E6F5"],
	};
	const c = MAP[fieldtype];
	if (!c) return "";
	return `<span style="background:${c[2]};color:${c[1]};font-size:10px;padding:1px 5px;border-radius:3px;font-weight:500;white-space:nowrap;">${c[0]}</span>`;
}

const WIDGET_INTENTS = {
	candidate_form: {
		icon: "📋",
		title: "Candidate Form Fields — per Service",
		description:
			"Controls <strong>which fields appear</strong> on the candidate's application form for a specific service. Each service shows only its relevant fields — no clutter, no confusion for the candidate.",
		steps: [
			"Select a service",
			"Configure service options",
			"Tick the fields to show",
			"Save",
		],
		impact: "Affects: Candidate application form",
		selectorLabel: "service",
		accentColor: "#185FA5",
		accentBg: "#E6F1FB",
		accentBorder: "#B5D4F4",
		accentDark: "#0C447C",
	},

	department_display: {
		icon: "👁",
		title: "Department Display Fields — per Department",
		description:
			"Controls <strong>which fields are visible</strong> to a department when viewing a candidate's details form under a specific department. Sensitive data can be hidden from departments that don't need it.",
		steps: ["Select a department", "Tick the fields they can view", "Save"],
		impact: "Affects: Candidate details form visibility per department",
		selectorLabel: "department",
		accentColor: "#0A7B8A",
		accentBg: "#E0F5F7",
		accentBorder: "#7DD4DC",
		accentDark: "#065A66",
	},

	department_access: {
		icon: "🔒",
		title: "Department Access Fields — per Department",
		description:
			"Controls <strong>which fields a department can edit</strong> on a candidate's profile. Select a department to define edit authority for that context — all other fields become read-only.",
		steps: ["Select a department", "Tick the fields they can edit", "Save"],
		impact: "Affects: Edit authority on candidate details form",
		selectorLabel: "department",
		accentColor: "#A01B1B",
		accentBg: "#FDEAEA",
		accentBorder: "#F0AAAA",
		accentDark: "#6E0F0F",
	},
};

function render_field_selector_widget(frm, htmlFieldname, storageField, intentKey, itemsList) {
	const wrapper = frm.get_field(htmlFieldname).$wrapper;
	const intent = WIDGET_INTENTS[intentKey];
	const uid = intentKey;
	const isCandidateForm = intentKey === "candidate_form";

	const EXCLUDE_FIELDS = [
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
		"form_token",
		"signature_method",
		"signature",
		"agreement_html",
		"authentication_html",
		"signature_image",
		"signature_custom_html",
		"files_custom_html",
		"reference_table",
		"my_electronic_signature_has_same_effect_as_handwritten",
		"i_consent_to_receive_sign_and_store_documents_electronically",
		"i_confirm_my_identity_and_signing_this_document_intentionally",
	];

	// ── CONFIG shape differs for candidate_form ───────────────────────────
	// candidate_form: { "Resume": { fields: [...], is_agreement_required: bool, is_candidate_form_required: bool } }
	// others:         { "Resume": ["field1", "field2", ...] }

	let CONFIG = {};
	try {
		CONFIG = frm.doc[storageField] ? JSON.parse(frm.doc[storageField]) : {};
	} catch (e) {
		CONFIG = {};
	}

	// Migrate legacy flat-array format for candidate_form (if any old data exists)
	if (isCandidateForm) {
		Object.keys(CONFIG).forEach((key) => {
			if (Array.isArray(CONFIG[key])) {
				CONFIG[key] = {
					fields: CONFIG[key],
					is_agreement_required: false,
					is_candidate_form_required: false,
				};
			}
		});
	}

	// Helpers to read/write from CONFIG safely across both shapes
	function getFields(name) {
		if (isCandidateForm) return (CONFIG[name] && CONFIG[name].fields) || [];
		return CONFIG[name] || [];
	}

	function setFields(name, fields) {
		if (isCandidateForm) {
			if (!CONFIG[name])
				CONFIG[name] = {
					fields: [],
					is_agreement_required: false,
					is_candidate_form_required: false,
				};
			CONFIG[name].fields = fields;
		} else {
			CONFIG[name] = fields;
		}
	}

	function getFlag(name, flag) {
		return isCandidateForm && CONFIG[name] ? !!CONFIG[name][flag] : false;
	}

	function setFlag(name, flag, value) {
		if (!isCandidateForm) return;
		if (!CONFIG[name])
			CONFIG[name] = {
				fields: [],
				is_agreement_required: false,
				is_candidate_form_required: false,
			};
		CONFIG[name][flag] = value;
	}

	let currentItem = null;

	function makeLabel(df) {
		if (df.label) return df.label;
		return df.fieldname.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
	}

	frappe.model.with_doctype("Lead Detail Form", function () {
		const meta = frappe.get_meta("Lead Detail Form");

		const SECTIONS = [];
		let curSec = { label: "General", fields: [] };

		meta.fields
			.sort((a, b) => a.idx - b.idx)
			.forEach((df) => {
				if (df.fieldtype === "Section Break") {
					if (curSec.fields.length) SECTIONS.push(curSec);
					curSec = {
						label:
							df.label ||
							df.fieldname
								.replace(/_/g, " ")
								.replace(/\b\w/g, (c) => c.toUpperCase()),
						fields: [],
					};
					return;
				}
				if (
					["Column Break", "HTML", "Fold", "Heading", "Tab Break"].includes(df.fieldtype)
				)
					return;
				if (!df.fieldname || EXCLUDE_FIELDS.includes(df.fieldname)) return;
				if (df.hidden || df.read_only) return;
				curSec.fields.push({ ...df, label: makeLabel(df) });
			});
		if (curSec.fields.length) SECTIONS.push(curSec);

		const allFieldNames = SECTIONS.flatMap((s) => s.fields.map((f) => f.fieldname));

		// ── Intent header ─────────────────────────────────────────────────
		const stepsHtml = intent.steps
			.map(
				(s, i) => `
            <div style="display:flex;align-items:center;gap:5px;background:#fff;border:0.5px solid ${intent.accentBorder};padding:3px 9px;border-radius:20px;">
                <div style="width:14px;height:14px;border-radius:50%;background:${intent.accentColor};color:#fff;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:500;flex-shrink:0;">${i + 1}</div>
                <span style="font-size:11px;color:${intent.accentDark};">${s}</span>
            </div>
        `,
			)
			.join("");

		// ── Outer shell ───────────────────────────────────────────────────
		wrapper.html(`
            <div style="font-size:13px;color:inherit;">

                <div style="background:${intent.accentBg};border:0.5px solid ${intent.accentBorder};border-radius:10px;padding:14px 16px;margin-bottom:20px;display:flex;gap:14px;align-items:flex-start;">
                    <div style="width:36px;height:36px;border-radius:8px;background:${intent.accentColor};color:#fff;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">
                        ${intent.icon}
                    </div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:13px;font-weight:500;color:${intent.accentDark};margin:0 0 4px;">${intent.title}</div>
                        <div style="font-size:12px;line-height:1.55;color:${intent.accentColor};margin:0 0 10px;">${intent.description}</div>
                        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
                            ${stepsHtml}
                            <span style="font-size:10px;padding:2px 8px;border-radius:3px;font-weight:500;background:${intent.accentColor};color:#fff;">
                                ⚡ ${intent.impact}
                            </span>
                        </div>
                    </div>
                </div>

                <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
                    <div style="width:22px;height:22px;border-radius:50%;background:${intent.accentColor};border:1px solid ${intent.accentColor};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:500;color:#fff;flex-shrink:0;">1</div>
                    <span style="font-size:12px;font-weight:500;">Choose a ${intent.selectorLabel}</span>
                    <div style="flex:1;height:1px;background:#e8e8e8;"></div>
                    <div id="${uid}-sn2" style="width:22px;height:22px;border-radius:50%;background:#f5f5f5;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;font-size:11px;color:#bbb;flex-shrink:0;">2</div>
                    <span id="${uid}-sl2" style="font-size:12px;color:#bbb;">Select fields</span>
                </div>

                <div id="${uid}-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:8px;margin-bottom:20px;"></div>

                <div id="${uid}-panel">
                    <div style="text-align:center;padding:30px 20px;border:0.5px dashed #ddd;border-radius:10px;color:#454545;font-size:12px;">
                        ☝️ Select a ${intent.selectorLabel} above to configure its fields
                    </div>
                </div>

                <div id="${uid}-footer" style="display:none;margin-top:13px;padding:10px 14px;background:#f8f9fa;border:1px solid #eee;border-radius:8px;align-items:center;justify-content:space-between;gap:10px;">
                    <div id="${uid}-fm" style="font-size:12px;color:#666;"></div>
                    <button id="${uid}-save" style="background:${intent.accentColor};color:#fff;border:none;padding:7px 15px;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;flex-shrink:0;">
                        Save configuration
                    </button>
                </div>

            </div>
        `);

		// ── Populate selector grid ────────────────────────────────────────
		const grid = wrapper.find(`#${uid}-grid`);

		itemsList.forEach((name) => {
			const icon = getItemIcon(name);
			const cnt = getFields(name).length;

			grid.append(`
                <div class="cfs-item-${uid}" data-name="${escapeQ(name)}"
                    style="border:0.5px solid #e8e8e8;border-radius:9px;padding:10px 11px;cursor:pointer;display:flex;align-items:center;gap:9px;transition:all 0.13s;">
                    <div class="cfs-item-ic-${uid}"
                        style="width:28px;height:28px;border-radius:6px;background:#f5f5f5;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;transition:background 0.13s;">
                        ${icon}
                    </div>
                    <div style="min-width:0;">
                        <div style="font-size:12px;font-weight:500;color:#454545;">${name}</div>
                        <div class="cfs-item-ct-${uid}" style="font-size:10px;color:#888;">${cnt} field${cnt !== 1 ? "s" : ""}</div>
                    </div>
                </div>
            `);
		});

		// Selector card click
		grid.on("click", `.cfs-item-${uid}`, function () {
			grid.find(`.cfs-item-${uid}`).css({ border: "0.5px solid #e8e8e8", background: "" });
			grid.find(`.cfs-item-ic-${uid}`).css({ background: "#f5f5f5", color: "inherit" });
			$(this).css({
				border: `1.5px solid ${intent.accentColor}`,
				background: intent.accentBg,
			});
			$(this)
				.find(`.cfs-item-ic-${uid}`)
				.css({ background: intent.accentColor, color: "#fff" });
			currentItem = $(this).data("name");
			wrapper.find(`#${uid}-sn2`).css({
				background: intent.accentColor,
				color: "#fff",
				border: `1px solid ${intent.accentColor}`,
			});
			wrapper.find(`#${uid}-sl2`).css({ color: "inherit", fontWeight: "500" });
			wrapper.find(`#${uid}-footer`).css("display", "flex");
			renderPanel("");
			updateFooter();
		});

		// ── Fields panel ──────────────────────────────────────────────────
		function renderPanel(q) {
			const sel = getFields(currentItem);
			const lq = (q || "").toLowerCase();

			// ── Service options block (candidate_form only) ───────────────
			const serviceOptionsHtml = isCandidateForm
				? `
                <div style="padding:12px 14px;border-bottom:0.5px solid ${intent.accentBorder};">
                    <div style="font-size:10px;font-weight:500;letter-spacing:0.07em;text-transform:uppercase;color:${intent.accentDark};margin-bottom:10px;">
                        Service Options
                    </div>
                    <div style="display:flex;flex-direction:column;gap:8px;">

                        <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;padding:9px 11px;border-radius:7px;border:0.5px solid ${getFlag(currentItem, "is_agreement_required") ? intent.accentColor : intent.accentBorder};background:${getFlag(currentItem, "is_agreement_required") ? "#fff" : "transparent"};transition:all 0.13s;"
                            id="${uid}-agr-label">
                            <input type="checkbox"
                                id="${uid}-is_agreement_required"
                                ${getFlag(currentItem, "is_agreement_required") ? "checked" : ""}
                                style="width:14px;height:14px;accent-color:${intent.accentColor};cursor:pointer;margin:2px 0 0;flex-shrink:0;" />
                            <div>
                                <div style="font-size:12px;font-weight:500;color:${intent.accentDark};">Is Agreement Required</div>
                                <div style="font-size:11px;color:${intent.accentColor};margin-top:2px;line-height:1.4;">
                                    When checked, an agreement document is become mandatory for candidates applying under this service.
                                </div>
                            </div>
                        </label>

                        <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;padding:9px 11px;border-radius:7px;border:0.5px solid ${getFlag(currentItem, "is_candidate_form_required") ? intent.accentColor : intent.accentBorder};background:${getFlag(currentItem, "is_candidate_form_required") ? "#fff" : "transparent"};transition:all 0.13s;"
                            id="${uid}-cfr-label">
                            <input type="checkbox"
                                id="${uid}-is_candidate_form_required"
                                ${getFlag(currentItem, "is_candidate_form_required") ? "checked" : ""}
                                style="width:14px;height:14px;accent-color:${intent.accentColor};cursor:pointer;margin:2px 0 0;flex-shrink:0;" />
                            <div>
                                <div style="font-size:12px;font-weight:500;color:${intent.accentDark};">Is Candidate Form Required</div>
                                <div style="font-size:11px;color:${intent.accentColor};margin-top:2px;line-height:1.4;">
                                    When checked, the candidate details form is sent to the candidate for this service. Fields selected below will appear on that form.
                                </div>
                            </div>
                        </label>

                    </div>
                </div>
            `
				: "";

			let html = `
                <div style="border:0.5px solid #e8e8e8;border-radius:9px;overflow:hidden;">
                    ${serviceOptionsHtml}
                    <div style="padding:10px 12px;border-bottom:1px solid #eee;background:#fafafa;display:flex;gap:9px;align-items:center;">
                        <input id="${uid}-srch" type="text" placeholder="Search fields…" value="${escapeQ(q)}"
                            style="flex:1;border:0.5px solid #ddd;border-radius:6px;padding:5px 10px;font-size:12px;outline:none;"
                            oninput="__cfsRefilter_${uid}(this.value)" />
                        <span id="${uid}-selall"
                            style="font-size:11px;color:${intent.accentColor};cursor:pointer;border:0.5px solid ${intent.accentBorder};border-radius:4px;padding:3px 7px;background:${intent.accentBg};white-space:nowrap;">
                            Select all
                        </span>
                        <div style="font-size:11px;color:#888;white-space:nowrap;">
                            <strong id="${uid}-cnt" style="color:${intent.accentColor};">${sel.length}</strong> selected
                        </div>
                    </div>
            `;

			let anyVisible = false;
			SECTIONS.forEach((sec) => {
				const vis = sec.fields.filter(
					(f) =>
						!lq ||
						f.label.toLowerCase().includes(lq) ||
						f.fieldname.toLowerCase().includes(lq),
				);
				if (!vis.length) return;
				anyVisible = true;

				html += `
                    <div style="padding:8px 13px 2px;font-size:10px;font-weight:500;letter-spacing:0.07em;text-transform:uppercase;color:${intent.accentDark};display:flex;align-items:center;gap:6px;">
                        <span>${sec.label}</span>
                        <span style="flex:1;border-top:0.5px solid ${intent.accentBorder};display:block;"></span>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px;padding:0 9px 9px;">
                `;
				vis.forEach((f) => {
					const on = sel.includes(f.fieldname);
					html += `
                        <label data-fn="${f.fieldname}"
                            style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;cursor:pointer;background:${on ? intent.accentBg : "transparent"};">
                            <input type="checkbox" class="${uid}-cb" data-fieldname="${f.fieldname}"
                                ${on ? "checked" : ""}
                                style="width:13px;height:13px;accent-color:${intent.accentColor};cursor:pointer;margin:0;flex-shrink:0;" />
                            <span style="font-size:12px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;color:#454545;white-space:nowrap;" title="${f.label}">
                                ${f.label}
                            </span>
                            ${getFieldTypeBadge(f.fieldtype)}
                        </label>
                    `;
				});
				html += `</div>`;
			});

			if (!anyVisible) {
				html += `<div style="padding:28px;text-align:center;color:#aaa;font-size:12px;">No fields match "${escapeQ(q)}"</div>`;
			}
			html += `</div>`;

			wrapper.find(`#${uid}-panel`).html(html);

			// ── Service option checkbox handlers (candidate_form only) ────
			if (isCandidateForm) {
				wrapper.find(`#${uid}-is_agreement_required`).on("change", function () {
					const val = $(this).prop("checked");
					setFlag(currentItem, "is_agreement_required", val);
					const lbl = wrapper.find(`#${uid}-agr-label`);
					lbl.css({
						border: `0.5px solid ${val ? intent.accentColor : intent.accentBorder}`,
						background: val ? "#fff" : "transparent",
					});
					frm.set_value(storageField, JSON.stringify(CONFIG));
				});

				wrapper.find(`#${uid}-is_candidate_form_required`).on("change", function () {
					const val = $(this).prop("checked");
					setFlag(currentItem, "is_candidate_form_required", val);
					const lbl = wrapper.find(`#${uid}-cfr-label`);
					lbl.css({
						border: `0.5px solid ${val ? intent.accentColor : intent.accentBorder}`,
						background: val ? "#fff" : "transparent",
					});
					frm.set_value(storageField, JSON.stringify(CONFIG));
				});
			}

			// Search
			wrapper.find(`#${uid}-srch`).on("input", function () {
				const v = $(this).val();
				renderPanel(v);
				const el = wrapper.find(`#${uid}-srch`)[0];
				if (el) {
					el.focus();
					el.setSelectionRange(v.length, v.length);
				}
			});

			// Select all / deselect all
			wrapper.find(`#${uid}-selall`).on("click", function () {
				const currentFields = getFields(currentItem);
				const allOn = allFieldNames.every((fn) => currentFields.includes(fn));
				setFields(currentItem, allOn ? [] : [...allFieldNames]);
				renderPanel(wrapper.find(`#${uid}-srch`).val() || "");
				syncCardCount();
				updateFooter();
				frm.set_value(storageField, JSON.stringify(CONFIG));
			});

			// Field checkbox toggle
			wrapper.find(`.${uid}-cb`).on("change", function () {
				const fn = $(this).data("fieldname");
				const on = $(this).prop("checked");
				let fields = getFields(currentItem);
				if (on) {
					if (!fields.includes(fn)) fields.push(fn);
				} else {
					fields = fields.filter((x) => x !== fn);
				}
				setFields(currentItem, fields);
				$(this)
					.closest("label")
					.css("background", on ? intent.accentBg : "transparent");
				wrapper.find(`#${uid}-cnt`).text(getFields(currentItem).length);
				syncCardCount();
				updateFooter();
				frm.set_value(storageField, JSON.stringify(CONFIG));
			});
		}

		window[`__cfsRefilter_${uid}`] = function (v) {
			renderPanel(v);
			const el = wrapper.find(`#${uid}-srch`)[0];
			if (el) {
				el.focus();
				el.setSelectionRange(v.length, v.length);
			}
		};

		function syncCardCount() {
			const cnt = getFields(currentItem).length;
			wrapper
				.find(`.cfs-item-${uid}[data-name="${escapeQ(currentItem)}"] .cfs-item-ct-${uid}`)
				.text(`${cnt} field${cnt !== 1 ? "s" : ""}`);
		}

		function updateFooter() {
			const cnt = getFields(currentItem).length;
			wrapper
				.find(`#${uid}-fm`)
				.html(
					`<strong>${currentItem}</strong> &mdash; ${cnt} field${cnt !== 1 ? "s" : ""} configured`,
				);
		}

		wrapper.find(`#${uid}-save`).on("click", function () {
			frm.set_value(storageField, JSON.stringify(CONFIG));
			frm.save();
			$(this).text("Saved ✓").css("background", "#0F6E56");
			setTimeout(() => {
				$(this).text("Save configuration").css("background", intent.accentColor);
			}, 1800);
		});
	}); // end frappe.model.with_doctype
}

function render_website_app_settings(frm) {
	const $wrapper = frm.get_field("website_settings").$wrapper.empty();
	const $row = $('<div class="row"></div>').appendTo($wrapper);
	const $col1 = $('<div class="col-sm-6"></div>').appendTo($row);
	const $col2 = $('<div class="col-sm-6"></div>').appendTo($row);

	// page-session cache so switching tabs / re-render doesn't refetch
	if (frappe.erp_config_website_cache) {
		build_controls(frappe.erp_config_website_cache);
	} else {
		frappe.call({
			method: "verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_website_app_settings",
			callback: (r) => {
				frappe.erp_config_website_cache = r.message;
				build_controls(r.message);
			},
		});
	}

	function build_controls(data) {
		$col1.empty();
		$col2.empty();

		const name_ctrl = frappe.ui.form.make_control({
			parent: $col1,
			df: { fieldtype: "Data", fieldname: "app_name", label: "App Name" },
			render_input: true,
		});
		name_ctrl.set_value(data.app_name);
		name_ctrl.$input.on("blur", () => save_field("app_name", name_ctrl.get_value()));

		const logo_ctrl = frappe.ui.form.make_control({
			parent: $col2,
			df: { fieldtype: "Attach Image", fieldname: "app_logo", label: "App Logo" },
			render_input: true,
		});
		logo_ctrl.set_value(data.app_logo);
		logo_ctrl.df.onchange = () => save_field("app_logo", logo_ctrl.get_value());

		render_system_settings_fields(frm);
	}

	function save_field(fieldname, value) {
		if (frappe.erp_config_website_cache?.[fieldname] === value) return; // skip no-op writes
		frappe.call({
			method: "verp_staffing.settings.doctype.erp_configuration.erp_configuration.update_website_app_settings",
			args: { [fieldname]: value },
			freeze: true,
			freeze_message: __("Updating Website Settings..."),
			callback: (r) => {
				frappe.erp_config_website_cache = r.message;
				frappe.show_alert({ message: __("Website Settings updated"), indicator: "green" });
			},
		});
	}
}

// ---------------------------------------------------------------------------
// Remove Sample Data
// ---------------------------------------------------------------------------

function add_remove_sample_data_button(frm) {
	frm.add_custom_button(
		__("Remove Sample Data"),
		() => open_remove_sample_data_dialog(frm),
		__("Actions"),
	);
}

function open_remove_sample_data_dialog(frm) {
	frappe.call({
		method: "verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_sample_data_summary",
		freeze: true,
		freeze_message: __("Checking sample data…"),
		callback(r) {
			const summary = r.message || {};
			if (!summary.total) {
				frappe.msgprint(__("No sample data found."));
				return;
			}
			if (summary.unexpected_doctypes && summary.unexpected_doctypes.length) {
				show_unexpected_doctypes_dialog(summary);
				return;
			}
			if (summary.conflicts && summary.conflicts.length) {
				show_sample_data_conflict_dialog(frm, summary);
			} else {
				confirm_plain_sample_data_removal(frm, summary);
			}
		},
	});
}

// ── Shared building blocks ──────────────────────────────────────────────────

function sample_data_dialog_styles() {
	return `
	<style>
	.sd-group { border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; }
	.sd-group-head { font-weight: 600; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; word-break: break-word; }
	.sd-badge { font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; background: var(--gray-200); color: var(--text-muted); padding: 1px 6px; border-radius: 4px; flex-shrink: 0; }
	.sd-chips { display: flex; flex-wrap: wrap; gap: 6px; padding-left: 2px; }
	.sd-chip { font-size: 12px; background: var(--subtle-accent); border-radius: 6px; padding: 3px 8px; display: inline-flex; align-items: center; gap: 5px; max-width: 100%; word-break: break-word; }
	.sd-chip-dt { font-size: 10px; color: var(--text-muted); white-space: nowrap; }
	.sd-link { color: var(--text-color); text-decoration: underline; word-break: break-word; }
	.sd-link:hover { color: var(--blue-500); }
	.sd-scroll { max-height: 340px; overflow-y: auto; padding-right: 4px; }
	.sd-details summary { cursor: pointer; font-size: 13px; color: var(--text-muted); margin: 6px 0; }
	.sd-warning { background: var(--bg-orange); border: 1px solid var(--orange-300, #f0ad4e); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; font-size: 13px; }
	</style>`;
}

function sd_doc_link(doctype, name) {
	const route = frappe.utils.get_form_link
		? frappe.utils.get_form_link(doctype, name)
		: `/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}`;
	return `<a href="${route}" target="_blank" rel="noopener" class="sd-link">${frappe.utils.escape_html(name)}</a>`;
}

// records: {doctype: [name, ...]} -> grouped, clickable HTML
function sd_records_html(records) {
	return Object.entries(records || {})
		.map(([doctype, names]) => {
			const chips = names
				.map((n) => `<span class="sd-chip">${sd_doc_link(doctype, n)}</span>`)
				.join("");
			return `
				<div class="sd-group">
					<div class="sd-group-head">
						<span class="sd-badge">${frappe.utils.escape_html(doctype)}</span>
						<span>${names.length}</span>
					</div>
					<div class="sd-chips">${chips}</div>
				</div>`;
		})
		.join("");
}

// conflicts: [{sample_doctype, sample_name, linked_doctype, linked_name}] ->
// grouped by sample record, clickable HTML
function sd_conflicts_html(conflicts) {
	const groups = new Map();
	conflicts.forEach((c) => {
		const key = `${c.sample_doctype}::${c.sample_name}`;
		if (!groups.has(key)) {
			groups.set(key, { doctype: c.sample_doctype, name: c.sample_name, links: [] });
		}
		groups.get(key).links.push({ doctype: c.linked_doctype, name: c.linked_name });
	});

	return Array.from(groups.values())
		.map((g) => {
			const chips = g.links
				.map(
					(l) =>
						`<span class="sd-chip">${sd_doc_link(l.doctype, l.name)}<span class="sd-chip-dt">${frappe.utils.escape_html(l.doctype)}</span></span>`,
				)
				.join("");
			return `
				<div class="sd-group">
					<div class="sd-group-head">
						<span class="sd-badge">${frappe.utils.escape_html(g.doctype)}</span>
						${sd_doc_link(g.doctype, g.name)}
					</div>
					<div class="sd-chips">${chips}</div>
				</div>`;
		})
		.join("");
}

// ── Dialogs ──────────────────────────────────────────────────────────────────

function show_unexpected_doctypes_dialog(summary) {
	// Safety net tripped: the log contains a doctype outside the known
	// sample-data list. Refuse to proceed automatically and show
	// exactly what was found so it can be reviewed by hand.
	const html = sd_records_html(
		summary.unexpected_doctypes.reduce((acc, dt) => {
			acc[dt] = summary.records[dt];
			return acc;
		}, {}),
	);

	frappe.msgprint({
		title: __("Remove Sample Data - Manual Review Needed"),
		indicator: "orange",
		message: `
			${sample_data_dialog_styles()}
			<p>${__(
				"The sample data log contains record types this tool doesn't know how to remove automatically. Nothing has been deleted. Please review these manually:",
			)}</p>
			<div class="sd-scroll">${html}</div>
		`,
	});
}

function confirm_plain_sample_data_removal(frm, summary) {
	const dialog = new frappe.ui.Dialog({
		title: __("Remove Sample Data"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "preview_html",
				options: `
					${sample_data_dialog_styles()}
					<p>${__("This will permanently delete {0} sample records. This cannot be undone.", [summary.total])}</p>
					<details class="sd-details">
						<summary>${__("Show exactly what will be deleted")}</summary>
						<div class="sd-scroll">${sd_records_html(summary.records)}</div>
					</details>
				`,
			},
		],
		primary_action_label: __("Delete Sample Data"),
		primary_action: () => {
			dialog.hide();
			run_sample_data_removal(frm, 0);
		},
	});

	dialog.set_secondary_action_label(__("Cancel"));
	dialog.set_secondary_action(() => dialog.hide());
	dialog.show();
}

function show_sample_data_conflict_dialog(frm, summary) {
	const conflicts = summary.conflicts || summary; // supports being called with just the array too

	const dialog = new frappe.ui.Dialog({
		title: __("Sample Data Has Live Links"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "conflict_html",
				options: `
					${sample_data_dialog_styles()}
					<p>${__(
						"These documents were created on top of sample data. Removing the sample data will also delete them:",
					)}</p>
					<div class="sd-scroll">${sd_conflicts_html(Array.isArray(conflicts) ? conflicts : [])}</div>
					${
						summary.records
							? `<details class="sd-details">
								<summary>${__("Show all {0} sample records that will also be deleted", [summary.total || ""])}</summary>
								<div class="sd-scroll">${sd_records_html(summary.records)}</div>
							</details>`
							: ""
					}
				`,
			},
		],
		primary_action_label: __("Delete Sample Data and Linked Records"),
		primary_action: () => {
			dialog.hide();
			run_sample_data_removal(frm, 1);
		},
	});

	dialog.set_secondary_action_label(__("Cancel"));
	dialog.set_secondary_action(() => dialog.hide());
	dialog.show();
}

function run_sample_data_removal(frm, delete_conflicts) {
	frappe.call({
		method: "verp_staffing.settings.doctype.erp_configuration.erp_configuration.remove_sample_data",
		args: { delete_conflicts },
		freeze: true,
		freeze_message: __("Removing sample data…"),
		callback(r) {
			const res = r.message || {};

			if (res.status === "conflicts") {
				// conflicts appeared between the check and the delete call
				show_sample_data_conflict_dialog(frm, { conflicts: res.conflicts });
				return;
			}

			const result = res.result || {};
			const errors = result.errors || [];
			const skipped = result.skipped_unexpected || {};
			const remaining = result.remaining || {};
			const deleted_total = Object.values(result.doctype_counts || {}).reduce(
				(a, b) => a + b,
				0,
			);

			if (res.is_sample_data_removed) {
				frappe.show_alert({ message: __("Sample data removed."), indicator: "green" });
			} else {
				// Partial or failed run - say so plainly. The log only ever
				// drops an entry once that specific delete is confirmed, so
				// "remaining" here is the ground truth of what's still there,
				// not a guess.
				frappe.msgprint({
					title: __("Sample Data Not Fully Removed"),
					indicator: "orange",
					message: `
						${sample_data_dialog_styles()}
						<p>${__("{0} record(s) were deleted. {1} record(s) are still present.", [
							deleted_total,
							sum_record_counts(remaining),
						])}</p>
						${
							errors.length
								? `<p><b>${__("Failed - see reason below:")}</b></p>
									<div class="sd-scroll">${sd_errors_html(errors)}</div>`
								: ""
						}
						${
							Object.keys(skipped).length
								? `<p><b>${__("Skipped - not on the known sample-data list:")}</b></p>
									<div class="sd-scroll">${sd_records_html(skipped)}</div>`
								: ""
						}
					`,
				});
			}

			// Patch frappe.boot in place so sample_data_guard.js's validate
			// check goes back to being a free in-memory read for the rest of
			// this session, without needing a refresh. (The realtime event
			// from mark_sample_data_removed() does this for every other open
			// session too - this just avoids waiting on it for our own tab.)
			if (res.is_sample_data_removed) {
				frappe.boot.is_sample_data_removed = 1;
			}

			frm.reload_doc();
		},
	});
}

function sum_record_counts(records) {
	return Object.values(records || {}).reduce((total, names) => total + names.length, 0);
}

function sd_errors_html(errors) {
	return errors
		.map(
			(e) => `
				<div class="sd-group">
					<div class="sd-group-head">
						<span class="sd-badge">${frappe.utils.escape_html(e.doctype)}</span>
						${sd_doc_link(e.doctype, e.name)}
					</div>
					<div style="font-size:12px;color:var(--text-muted);padding-left:2px;">${frappe.utils.escape_html(e.error || "")}</div>
				</div>`,
		)
		.join("");
}

const SYSTEM_SETTINGS_EXISTING_SECTION_FIELDS = ["country", "language", "time_zone", "currency"];

const SYSTEM_SETTINGS_FIELD_GROUPS = [
	{
		label: "Date and Number Format",
		fields: ["date_format", "time_format", "number_format"],
	},
	{
		label: "Session, Password & Email Limits",
		fields: [
			"session_expiry",
			"deny_multiple_sessions",
			"reset_password_link_expiry_duration",
			"password_reset_limit",
			"welcome_email_template",
			"reset_password_template",
		],
	},
	{
		label: "Files",
		fields: ["max_file_size", "allowed_file_extensions"],
	},
];

let system_settings_pending_changes = {};
let system_settings_current_values = {};

function stage_system_settings_change(frm, fieldname, value) {
	system_settings_pending_changes[fieldname] = value;
	system_settings_current_values[fieldname] = value;
	frm.dirty();
}

function flush_system_settings_changes() {
	if (!Object.keys(system_settings_pending_changes).length) {
		return Promise.resolve();
	}

	const values_to_save = system_settings_pending_changes;
	system_settings_pending_changes = {}; // clear now so a fresh edit mid-flush isn't dropped or double-sent

	return new Promise((resolve, reject) => {
		frappe.call({
			method: "verp_staffing.settings.doctype.erp_configuration.erp_configuration.update_system_settings_fields",
			args: { values: values_to_save },
			freeze: true,
			freeze_message: __("Updating System Settings..."),
			callback(r) {
				const saved = (r.message && r.message.values) || {};
				Object.assign(system_settings_current_values, saved);

				if ("language" in values_to_save) {
					frappe.msgprint(__("Refreshing..."));
					window.location.reload();
				}
				resolve();
			},
			error() {
				Object.assign(system_settings_pending_changes, values_to_save);
				frappe.msgprint({
					title: __("Error"),
					indicator: "red",
					message: __("Failed to update System Settings. Your changes were not saved."),
				});
				reject(new Error("system settings save failed"));
			},
		});
	});
}

function render_system_settings_field_row(
	frm,
	$wrapper,
	current_values,
	timezones,
	fieldnames,
	section_label,
) {
	if (section_label) {
		$wrapper.append(`
			<div style="font-size:17px;font-weight:600;margin:18px 0 8px;padding-top:14px;border-top:1px solid var(--border-color);">
				${frappe.utils.escape_html(section_label)}
			</div>
		`);
	}

	const $row = $('<div class="row"></div>').appendTo($wrapper);

	fieldnames.forEach((fieldname) => {
		const source_df = frappe.meta.get_docfield("System Settings", fieldname);
		if (!source_df) return; // typo guard — fails loud in console rather than silently

		const df = Object.assign({}, source_df, {
			read_only: 0,
			read_only_depends_on: null,
			set_only_once: 0,
		});

		if (fieldname === "time_zone") {
			df.options = timezones.join("\n");
		}

		const $col = $('<div class="col-sm-6" style="margin-bottom:10px;"></div>').appendTo($row);

		const control = frappe.ui.form.make_control({
			parent: $col,
			df,
			render_input: true,
		});

		control.set_value(current_values[fieldname]).then(() => {
			control.df.onchange = () => {
				const value = control.get_value();
				if (value === current_values[fieldname]) return; // skip no-op writes
				stage_system_settings_change(frm, fieldname, value);
			};
		});
	});
}

function render_system_settings_fields(frm) {
	const $wrapper = frm.get_field("website_settings").$wrapper;

	frappe.model.with_doctype("System Settings", () => {
		frappe.call({
			method: "verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_system_settings_fields",
			callback(r) {
				const current_values = (r.message && r.message.values) || {};
				const timezones = (r.message && r.message.timezones) || [];

				// keep a module-level reference so flush_system_settings_changes
				// can reconcile server-returned values back into it after save
				system_settings_current_values = current_values;

				render_system_settings_field_row(
					frm,
					$wrapper,
					current_values,
					timezones,
					SYSTEM_SETTINGS_EXISTING_SECTION_FIELDS,
					null, // no heading — joins the existing app_name/app_logo section
				);

				SYSTEM_SETTINGS_FIELD_GROUPS.forEach((group) => {
					render_system_settings_field_row(
						frm,
						$wrapper,
						current_values,
						timezones,
						group.fields,
						group.label,
					);
				});
			},
		});
	});
}
