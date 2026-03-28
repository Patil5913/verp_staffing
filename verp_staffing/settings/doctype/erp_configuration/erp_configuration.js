// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("ERP Configuration", {
	refresh(frm) {
		set_department_role_filters(frm);
		frappe.call({
			method: "verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_services",
			callback(r) {
				const services = r.message || [];
				const servicesPlus = [...services, "Lead" , "Customer"];

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
					services,
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
});

function set_department_role_filters(frm) {
	const dept_field_map = {
		sales_department: "Sales",
		technical_department: "Technical",
		marketing_department: "Marketing",
	};

	Object.entries(dept_field_map).forEach(([field, dept_name]) => {
		// Fetch roles for this department from Department doctype
		frappe.db.get_value("Department", dept_name, "roles_json").then((r) => {
			if (!r || !r.message || !r.message.roles_json) return;

			let roles = [];
			try {
				roles = JSON.parse(r.message.roles_json);
			} catch (e) {
				return;
			}

			if (!roles.length) return;

			// Set filter on the link field to show only these roles
			frm.set_query(field, function () {
				return {
					filters: [["Role", "name", "in", roles]],
				};
			});
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
