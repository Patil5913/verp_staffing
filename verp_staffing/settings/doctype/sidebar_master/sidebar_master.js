// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// ─── CONSTANTS ───────────────────────────────────────────────────────────────

const FRAPPE_ICONS = [
	{ id: "icon-setting-gear", label: "Settings" },
	{ id: "icon-users", label: "Users" },
	{ id: "icon-user", label: "User" },
	{ id: "icon-customer", label: "Customer" },
	{ id: "icon-employee", label: "Employee" },
	{ id: "icon-keyboard", label: "Keyboard" },
	{ id: "icon-mail", label: "Mail" },
	{ id: "icon-calendar", label: "Calendar" },
	{ id: "icon-file", label: "File" },
	{ id: "icon-small-file", label: "Small File" },
	{ id: "icon-folder-open", label: "Folder" },
	{ id: "icon-pen", label: "Pen" },
	{ id: "icon-share", label: "Share" },
	{ id: "icon-tag", label: "Tag" },
	{ id: "icon-list-alt", label: "List" },
	{ id: "icon-assign", label: "Assign" },
	{ id: "icon-support", label: "Support" },
	{ id: "icon-tool", label: "Tool" },
	{ id: "icon-website", label: "Website" },
	{ id: "icon-call", label: "Call" },
	{ id: "icon-stock", label: "Stock" },
	{ id: "icon-expenses", label: "Expenses" },
	{ id: "icon-accounting", label: "Accounting" },
	{ id: "icon-money-coins-1", label: "Money" },
	{ id: "icon-milestone", label: "Milestone" },
	{ id: "icon-getting-started", label: "Getting Started" },
	{ id: "icon-branch", label: "Branch" },
	{ id: "icon-sort-ascending", label: "Sort" },
	{ id: "icon-organization", label: "Organization" },
	{ id: "icon-number-card", label: "Card" },
	{ id: "icon-quantity-1", label: "Quantity" },
	{ id: "icon-dashboard", label: "Dashboard" },
	{ id: "icon-report", label: "Report" },
	{ id: "icon-project", label: "Project" },
	{ id: "icon-manufacturing", label: "Manufacturing" },
	{ id: "icon-purchase", label: "Purchase" },
	{ id: "icon-sales", label: "Sales" },
	{ id: "icon-hr", label: "HR" },
	{ id: "icon-crm", label: "CRM" },
	{ id: "icon-payroll", label: "Payroll" },
	{ id: "icon-leave", label: "Leave" },
	{ id: "icon-attendance", label: "Attendance" },
	{ id: "icon-asset", label: "Asset" },
	{ id: "icon-loan", label: "Loan" },
	{ id: "icon-quality", label: "Quality" },
	{ id: "icon-integrations", label: "Integrations" },
	{ id: "icon-help-circle", label: "Help" },
	{ id: "icon-external-link", label: "External Link" },
];

const TYPE_DEFS = [
	{
		value: "type_3",
		short: "Single Link",
		icon: "→",
		desc: "One direct link. No sub-items.",
		badge: "LINK",
		badgeColor: "#4f46e5",
	},
	// {
	// 	value: "type_1",
	// 	short: "Link + Children",
	// 	icon: "⊕",
	// 	desc: "Navigates to a page AND shows children beneath it.",
	// 	badge: "LINK+",
	// 	badgeColor: "#0891b2",
	// },
	{
		value: "type_2",
		short: "Group",
		icon: "▾",
		desc: "Expands / collapses children. Header does not navigate.",
		badge: "GROUP",
		badgeColor: "#059669",
	},
];

const TYPE_MAP = {};
TYPE_DEFS.forEach((d) => (TYPE_MAP[d.value] = d));

const CUSTOM_PAGES = [
	{
		key: "permission-manager",
		name: "Permission Manager",
		route: "/app/permission-manager",
		icon: "icon-setting-gear",
		type: "page",
	},
	{
		key: "setup",
		name: "Setup Guide",
		route: "/app/setup",
		icon: "icon-getting-started",
		type: "page",
	},
	{
		key: "email-inbox",
		name: "Email Inbox",
		route: "/app/email-inbox",
		icon: "icon-mail",
		type: "page",
	},
	{ key: "role", name: "Roles", route: "/app/role", icon: "icon-small-file", type: "page" },
	{
		key: "coa",
		name: "Chart of Accounts",
		route: "/app/account/view/tree",
		icon: "icon-accounting",
		type: "page",
	},
];

const IS_ADMIN = () =>
	frappe.user_roles.includes("Administrator") || frappe.user_roles.includes("System Manager");

const API = {
	doctypes:
		"verp_staffing.settings.doctype.sidebar_master.sidebar_master.get_accessible_doctypes",
	reports: "verp_staffing.settings.doctype.sidebar_master.sidebar_master.get_accessible_reports",
};

let sb_frm = null;

function sb_mark_dirty() {
	if (sb_frm) sb_frm.dirty();
}

// ─── FORM HANDLER ────────────────────────────────────────────────────────────

frappe.ui.form.on("Sidebar Master", {
	async refresh(frm) {
		sb_frm = frm;
		if (frm.is_new()) frm.set_value("sidebar_owner", frappe.session.user);
		inject_styles();
		render_builder_shell(frm);
		await load_palette_items(frm);
		load_canvas_from_json(frm);
		bind_toolbar(frm);
	},
	config_json(frm) {
		load_canvas_from_json(frm);
	},
	validate(frm) {
		// ── Guard: no empty labels ────────────────────────────────────────────
		for (const s of sb_sections) {
			if (!s.label || !s.label.trim()) {
				frappe.throw(__("One or more sections have an empty label. Please fill in all labels before saving."));
				return false;
			}
		}

		// ── Auto-derive keys from labels before uniqueness check ──────────────
		// Keys are always computed from the label at save time; the user never
		// types a key manually. We do a final sync pass here to ensure the
		// in-memory state is consistent with what will be written to config_json.
		sb_sections.forEach((s) => {
			if (!s.link_key || s._key_auto) {
				s.link_key = sb_slug(s.label);
			}
		});

		// ── Unique key constraint ─────────────────────────────────────────────
		// Each section key must be unique across the entire canvas. For group /
		// link+children sections the key is derived from the label; for type_3
		// sections the key is the original palette item key. Either way, if two
		// sections end up with the same key the config would silently break
		// sidebar routing, so we block the save here with a clear message.
		const seen_keys = new Map(); // key → label (for the error message)
		for (const s of sb_sections) {
			const k = s.link_key;
			if (!k) continue;
			if (seen_keys.has(k)) {
				frappe.throw(
					__(
						`Two sections produce the same key <strong>"${k}"</strong>: ` +
						`<b>"${seen_keys.get(k)}"</b> and <b>"${s.label}"</b>. ` +
						`Please rename one of them so their keys are unique.`
					)
				);
				return false;
			}
			seen_keys.set(k, s.label);
		}

		// ── Palette key conflict check ────────────────────────────────────────
		// A group/type_1 section whose derived key matches an existing palette
		// item key would cause that palette item to appear greyed-out even though
		// it is not actually on the canvas. Catch this and surface it clearly.
		for (const s of sb_sections) {
			if (s.parent_type === "type_3") continue; // type_3 keys ARE palette keys — that's expected
			const k = s.link_key;
			if (!k) continue;
			const conflict = sb_palette_items.find((p) => p.key === k);
			if (conflict) {
				frappe.throw(
					__(
						`The group label <b>"${s.label}"</b>` +
						`is making conflicts with the existing item <b>"${conflict.name}"</b>. ` +
						`Please choose a different label for this group.`
					)
				);
				return false;
			}
		}

		save_canvas_to_json(frm);
	},
	after_save(frm) {
		if (typeof window.csb_reload === "function") {
			window.csb_reload();
		} else {
			window.location.reload();
		}
	},
});

// ─── STYLES ──────────────────────────────────────────────────────────────────

function inject_styles() {
	const el = document.getElementById("sb-styles");
	if (el) el.remove();
	const s = document.createElement("style");
	s.id = "sb-styles";
	s.textContent = `
	/* ═══ ROOT ═══════════════════════════════════════════════════ */
	#sb-root { font-size:14px; border:1px solid var(--border-color); border-radius:8px; overflow:hidden; background:var(--bg-color); }
	#sb-root * { box-sizing:border-box; }

	/* ═══ GUIDE BANNER ══════════════════════════════════════════ */
	.sb-guide-banner { display:flex; align-items:flex-start; gap:12px; padding:10px 14px; background:var(--alert-bg,#eff6ff); border-bottom:1px solid var(--border-color); font-size:12px; color:var(--text-color); line-height:1.5; }
	.sb-guide-banner .gb-icon { font-size:18px; flex-shrink:0; }
	.sb-guide-banner .gb-body { flex:1; }
	.sb-guide-banner strong { color:var(--primary); }
	.gb-steps { display:flex; gap:6px; margin-top:5px; flex-wrap:wrap; }
	.sb-guide-step { display:flex; align-items:center; gap:4px; font-size:11px; color:var(--text-muted); background:var(--fg-color); border:1px solid var(--border-color); border-radius:20px; padding:2px 8px; }
	.gs-num { width:14px; height:14px; border-radius:50%; background:var(--primary); color:#fff; font-size:9px; font-weight:700; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
	.sb-guide-close { background:none; border:none; cursor:pointer; color:var(--text-muted); font-size:15px; padding:0; flex-shrink:0; align-self:flex-start; }
	.sb-guide-close:hover { color:var(--text-color); }

	/* ═══ LAYOUT ════════════════════════════════════════════════ */
	.sb-layout { display:grid; grid-template-columns:260px 1fr; height:660px; overflow:hidden; }

	/* ═══ PALETTE ═══════════════════════════════════════════════ */
	.sb-palette { border-right:1px solid var(--border-color); display:flex; flex-direction:column; background:var(--fg-color); overflow:hidden; }
	.sb-palette-head { padding:10px 10px 7px; border-bottom:1px solid var(--border-color); display:flex; flex-direction:column; gap:6px; flex-shrink:0; }
	.sb-palette-head-top { display:flex; align-items:center; justify-content:space-between; }
	.sb-palette-head-top .label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.07em; color:var(--text-muted); }
	.sb-palette-head-top .count { font-size:11px; color:var(--text-muted); }
	.sb-search { position:relative; }
	.sb-search input { width:100%; padding:5px 8px 5px 26px; border:1px solid var(--border-color); border-radius:5px; font-size:12px; background:var(--control-bg); color:var(--text-color); outline:none; }
	.sb-search input:focus { border-color:var(--primary); }
	.sb-search .search-icon { position:absolute; left:7px; top:50%; transform:translateY(-50%); color:var(--text-muted); font-size:12px; }
	.sb-filter-tabs { display:flex; gap:3px; }
	.sb-tab { padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; cursor:pointer; border:1px solid var(--border-color); color:var(--text-muted); background:transparent; }
	.sb-tab.active { background:var(--primary); color:#fff; border-color:var(--primary); }
	.sb-palette-list { flex:1; overflow-y:auto; padding:4px 0; }
	.sb-group-label { padding:7px 10px 2px; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:var(--text-muted); }
	.sb-palette-item { display:flex; align-items:center; gap:7px; padding:5px 10px; cursor:grab; user-select:none; transition:background .1s; }
	.sb-palette-item:hover { background:var(--control-bg-on-hover); }
	.sb-palette-item.in-use { opacity:.3; pointer-events:none; }
	.sb-palette-item:not(.in-use)::after { content:"drag →"; font-size:10px; color:var(--text-muted); opacity:0; margin-left:auto; text-transform:uppercase; letter-spacing:.04em; flex-shrink:0; }
	.sb-palette-item:not(.in-use):hover::after { opacity:1; }
	.pi-icon { width:22px; height:22px; border-radius:4px; background:var(--control-bg); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
	.pi-icon .icon { color:var(--primary); }
	.pi-info { flex:1; min-width:0; }
	.pi-name { font-size:12px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--text-color); }
	.pi-type { font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.04em; }

	/* ═══ CANVAS SHELL ══════════════════════════════════════════ */
	.sb-canvas { display:flex; flex-direction:column; background:var(--bg-color); overflow:hidden; }
	.sb-canvas-head { display:flex; align-items:center; justify-content:space-between; padding:9px 14px 7px; background:var(--fg-color); border-bottom:1px solid var(--border-color); flex-shrink:0; }
	.sb-canvas-head .label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.07em; color:var(--text-muted); }
	.sb-canvas-head-right { display:flex; align-items:center; gap:10px; }
	.sb-canvas-tip { font-size:11px; color:var(--text-muted); }

	/* Canvas body */
	.sb-canvas-body { flex:1; overflow-y:auto; padding:10px 10px 40px; }
	.sb-empty-state { text-align:center; padding:50px 20px; color:var(--text-muted); font-size:14px; }
	.sb-empty-state i { font-size:36px; margin-bottom:10px; display:block; opacity:.35; }
	.sb-empty-state p { margin:4px 0 0; font-size:12px; }

	.sb-canvas-body.palette-drag-active { outline:2px dashed var(--border-color); outline-offset:-4px; border-radius:6px; }
	.sb-canvas-body.palette-drag-active.drag-over-canvas { outline-color:var(--primary); background:rgba(99,102,241,.04); }
	.sb-canvas-body.child-zone-active .sb-section:not(.accepting-child) { opacity:.45; pointer-events:none; }
	.sb-canvas-body.child-zone-active .sb-section.accepting-child { opacity:1; pointer-events:auto; }

	/* ═══ SECTION ═══════════════════════════════════════════════ */
	.sb-section { background:var(--fg-color); border:1px solid var(--border-color); border-radius:7px; margin-bottom:6px; overflow:visible; transition:box-shadow .12s; }
	.sb-section:hover { box-shadow:0 1px 6px rgba(0,0,0,.07); }
	.sb-section.drag-over-section { outline:2px dashed var(--primary); outline-offset:2px; }
	.sb-section.section-dragging { opacity:.3; box-shadow:none; }
	.sb-section[data-ptype="type_3"] { border-left:3px solid #4f46e5; }
	.sb-section[data-ptype="type_1"] { border-left:3px solid #0891b2; }
	.sb-section[data-ptype="type_2"] { border-left:3px solid #059669; }

	/* ── Section header row ── */
	.sb-section-header { display:flex; align-items:center; gap:7px; padding:8px 10px; background:var(--fg-color); border-radius:6px 6px 0 0; user-select:none; }
	.sb-section[data-ptype="type_3"] .sb-section-header { border-radius:4px; }

	.sh-drag { color:var(--text-muted); font-size:15px; cursor:grab; padding:2px; border-radius:3px; flex-shrink:0; line-height:1; }
	.sh-drag:hover { color:var(--primary); background:var(--control-bg); }
	.sh-drag:active { cursor:grabbing; }

	.sh-icon-btn { width:26px; height:26px; border-radius:5px; border:1px dashed var(--border-color); background:var(--bg-color); display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0; }
	.sh-icon-btn:hover { border-color:var(--primary); background:var(--primary-light,#ebf5fb); }

	.sh-label { flex:1; border:none; background:transparent; font-size:14px; font-weight:600; color:var(--text-color); outline:none; cursor:text; min-width:30px; }
	.sh-label:focus { background:var(--control-bg); border-radius:3px; padding:1px 4px; }
	.sh-label.needs-input { border-bottom:2px dashed var(--orange-400,#f6ad55); color:var(--text-muted); font-style:italic; }

	/* Type badge */
	.sh-type-wrap { position:relative; flex-shrink:0; }
	.sh-type-badge { display:inline-flex; align-items:center; gap:4px; padding:3px 8px; border-radius:20px; border:1.5px solid transparent; font-size:11px; font-weight:700; letter-spacing:.04em; cursor:pointer; transition:all .12s; white-space:nowrap; user-select:none; }
	.sh-type-badge[data-type="type_3"] { background:#ede9fe; color:#4f46e5; border-color:#c4b5fd; }
	.sh-type-badge[data-type="type_1"] { background:#e0f2fe; color:#0369a1; border-color:#7dd3fc; }
	.sh-type-badge[data-type="type_2"] { background:#dcfce7; color:#15803d; border-color:#86efac; }
	.sh-type-badge:hover { filter:brightness(.93); }

	/* Type picker dropdown */
	.sh-type-dropdown { display:none; position:absolute; top:calc(100% + 4px); right:0; background:var(--fg-color); border:1px solid var(--border-color); border-radius:8px; box-shadow:0 6px 20px rgba(0,0,0,.13); padding:4px; min-width:210px; z-index:9999; }
	.sh-type-dropdown.open { display:block; }
	.sh-type-option { display:flex; align-items:center; gap:9px; padding:7px 10px; border-radius:5px; cursor:pointer; font-size:13px; color:var(--text-color); transition:background .1s; }
	.sh-type-option:hover { background:var(--control-bg-on-hover); }
	.sh-type-option.active { background:var(--primary-light,#ebf5fb); }
	.sh-type-option-icon { font-size:15px; width:20px; text-align:center; flex-shrink:0; }
	.sh-type-option-body { flex:1; }
	.sh-type-option-label { font-weight:600; font-size:12px; }
	.sh-type-option-desc { font-size:11px; color:var(--text-muted); margin-top:1px; }
	.sh-type-locked { font-size:11px; color:var(--text-muted); padding:2px 8px; background:var(--bg-color); border:1px solid var(--border-color); border-radius:20px; }

	.sh-del-btn { width:22px; height:22px; border-radius:4px; border:none; background:transparent; color:var(--text-muted); cursor:pointer; font-size:14px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
	.sh-del-btn:hover { background:var(--red-100,#fde8e8); color:var(--red-500,#e53e3e); }

	/* Shortcut pill */
	.sh-shortcut-pill { display:inline-flex; align-items:center; gap:5px; padding:2px 8px; border-radius:20px; border:1.5px dashed var(--border-color); background:var(--bg-color); color:var(--text-muted); font-size:11px; cursor:pointer; flex-shrink:0; transition:all .12s; white-space:nowrap; user-select:none; }
	.sh-shortcut-pill:hover { border-color:var(--primary); color:var(--primary); background:var(--primary-light,#ebf5fb); }
	.sh-shortcut-pill.has-shortcut { border-style:solid; border-color:var(--primary); color:var(--primary); background:var(--primary-light,#ebf5fb); font-weight:700; }
	.sh-shortcut-pill .sp-icon { font-size:12px; }

	/* Shortcut popup */
	.sb-shortcut-popup { display:none; position:fixed; z-index:10000; background:var(--fg-color); border:1px solid var(--border-color); border-radius:10px; box-shadow:0 8px 30px rgba(0,0,0,.18); padding:18px 20px; min-width:280px; max-width:320px; }
	.sb-shortcut-popup.open { display:block; }
	.sb-sp-title { font-size:14px; font-weight:700; color:var(--text-color); margin-bottom:4px; }
	.sb-sp-sub   { font-size:12px; color:var(--text-muted); margin-bottom:14px; line-height:1.5; }
	.sb-sp-keys  { display:flex; align-items:center; justify-content:center; gap:6px; padding:14px; background:var(--bg-color); border-radius:7px; border:2px dashed var(--border-color); margin-bottom:12px; min-height:52px; font-size:13px; color:var(--text-muted); transition:border-color .15s, background .15s; }
	.sb-sp-keys.recording { border-color:var(--primary); background:var(--primary-light,#ebf5fb); }
	.sb-sp-keys.error     { border-color:var(--red-400,#fc8181); background:var(--red-50,#fff5f5); }
	.sb-sp-key { display:inline-flex; align-items:center; justify-content:center; padding:4px 9px; background:var(--fg-color); border:1.5px solid var(--border-color); border-radius:5px; box-shadow:0 2px 0 var(--border-color); font-size:13px; font-weight:700; font-family:monospace; color:var(--text-color); min-width:32px; }
	.sb-sp-plus { color:var(--text-muted); font-size:14px; font-weight:700; }
	.sb-sp-prompt { color:var(--text-muted); font-size:12px; }
	.sb-sp-error  { font-size:12px; color:var(--red-500,#e53e3e); font-weight:600; text-align:center; min-height:16px; margin-bottom:8px; }
	.sb-sp-actions { display:flex; align-items:center; justify-content:space-between; gap:8px; }
	.sb-sp-btn { padding:5px 14px; border-radius:6px; border:1.5px solid var(--border-color); background:var(--bg-color); color:var(--text-muted); font-size:12px; font-weight:600; cursor:pointer; transition:all .1s; }
	.sb-sp-btn:hover { border-color:var(--primary); color:var(--primary); background:var(--primary-light,#ebf5fb); }
	.sb-sp-btn.primary { background:var(--primary); color:#fff; border-color:var(--primary); }
	.sb-sp-btn.primary:hover { filter:brightness(.92); }
	.sb-sp-btn.danger { border-color:var(--red-400,#fc8181); color:var(--red-500,#e53e3e); }
	.sb-sp-btn.danger:hover { background:var(--red-50,#fff5f5); }

	/* Section divider */
	.sb-section-divider { display:flex; align-items:center; gap:8px; padding:5px 10px 5px 14px; border-top:1px solid var(--border-color); background:var(--bg-color); font-size:11px; color:var(--text-muted); font-weight:600; letter-spacing:.04em; text-transform:uppercase; }
	.sb-section-divider .sd-label { flex:1; }
	.sb-section-divider .sd-count { font-size:10px; color:var(--text-muted); }

	/* ═══ CHILDREN ZONE ══════════════════════════════════════════ */
	.sb-children { padding:0 8px 8px 28px; min-height:52px; position:relative; background:var(--bg-color); border-radius:0 0 6px 6px; }
	.sb-children-drop-bar { display:flex; align-items:center; justify-content:center; gap:6px; margin-bottom:4px; padding:5px 8px; border:1.5px dashed var(--border-color); border-radius:5px; font-size:11px; color:var(--text-muted); background:transparent; transition:all .15s; }
	.sb-children.drop-over .sb-children-drop-bar { border-color:var(--primary); background:var(--primary-light,#ebf5fb); color:var(--primary); font-weight:600; }
	.sb-children::before { content:""; position:absolute; left:14px; top:0; bottom:12px; width:1px; background:var(--border-color); border-radius:1px; }

	/* ── Child row ── */
	.sb-child { display:flex; align-items:center; gap:6px; padding:5px 7px 5px 5px; border-radius:5px; margin-top:3px; background:var(--fg-color); border:1px solid var(--border-color); user-select:none; font-size:13px; position:relative; transition:border-color .1s, box-shadow .1s; }
	.sb-child::before { content:""; position:absolute; left:-14px; top:50%; width:13px; height:1px; background:var(--border-color); }
	.sb-child:hover { border-color:var(--primary); box-shadow:0 1px 4px rgba(0,0,0,.06); }
	.sb-child.child-dragging { opacity:.3; border-style:dashed; }
	.sb-child.child-drag-over { border-top:2px solid var(--primary); margin-top:1px; }

	.ci-drag { color:var(--text-muted); font-size:12px; cursor:grab; flex-shrink:0; padding:1px 2px; border-radius:3px; line-height:1; }
	.ci-drag:hover { color:var(--primary); background:var(--control-bg); }
	.ci-drag:active { cursor:grabbing; }
	.ci-icon-btn { width:18px; height:18px; border-radius:3px; background:var(--control-bg); display:flex; align-items:center; justify-content:center; flex-shrink:0; cursor:pointer; border:1px solid transparent; }
	.ci-icon-btn:hover { border-color:var(--primary); background:var(--primary-light,#ebf5fb); }
	.ci-label { flex:1; font-size:12px; font-weight:500; color:var(--text-color); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
	.ci-badge { font-size:10px; color:var(--text-muted); background:var(--bg-color); border:1px solid var(--border-color); border-radius:3px; padding:1px 5px; text-transform:uppercase; letter-spacing:.04em; flex-shrink:0; }

	/* Child shortcut pill */
	.ci-shortcut { display:inline-flex; align-items:center; gap:3px; padding:1px 6px; border-radius:10px; border:1px dashed var(--border-color); font-size:10px; color:var(--text-muted); cursor:pointer; flex-shrink:0; transition:all .1s; white-space:nowrap; }
	.ci-shortcut:hover { border-color:var(--primary); color:var(--primary); background:var(--primary-light,#ebf5fb); }
	.ci-shortcut.has-shortcut { border-style:solid; border-color:var(--primary); color:var(--primary); background:var(--primary-light,#ebf5fb); font-weight:700; }

	.ci-del { width:16px; height:16px; border-radius:50%; border:none; background:transparent; color:var(--text-muted); cursor:pointer; font-size:13px; display:flex; align-items:center; justify-content:center; opacity:0; flex-shrink:0; }
	.sb-child:hover .ci-del { opacity:1; }
	.ci-del:hover { background:var(--red-100,#fde8e8); color:var(--red-500,#e53e3e); }

	/* ═══ ICON PICKER ════════════════════════════════════════════ */
	.sb-icon-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(58px,1fr)); gap:5px; max-height:260px; overflow-y:auto; padding:2px 0; }
	.sb-icon-chip { display:flex; flex-direction:column; align-items:center; gap:3px; padding:6px 3px; border-radius:5px; border:1px solid var(--border-color); cursor:pointer; font-size:10px; color:var(--text-muted); text-align:center; background:var(--bg-color); }
	.sb-icon-chip:hover { border-color:var(--primary); color:var(--primary); }
	.sb-icon-chip.selected { border-color:var(--primary); background:var(--primary); color:#fff; }
	.sb-icon-chip .icon { font-size:16px; }

	/* ═══ SCROLLBARS ═════════════════════════════════════════════ */
	.sb-palette-list::-webkit-scrollbar, .sb-canvas-body::-webkit-scrollbar, .sb-icon-grid::-webkit-scrollbar { width:4px; }
	.sb-palette-list::-webkit-scrollbar-thumb, .sb-canvas-body::-webkit-scrollbar-thumb, .sb-icon-grid::-webkit-scrollbar-thumb { background:var(--border-color); border-radius:4px; }
	`;
	document.head.appendChild(s);
}

// ─── SHELL HTML ──────────────────────────────────────────────────────────────

function render_builder_shell(frm) {
	const wrapper = frm.get_field("sidebar_builder").$wrapper;
	if (wrapper.find("#sb-root").length) return;
	wrapper.html(`
		<div id="sb-root">
			<div class="sb-guide-banner" id="sb-guide-banner">
				<span class="gb-icon">💡</span>
				<div class="gb-body">
					<strong>How to build your sidebar</strong> — Drag items from the left panel to the canvas. Set type, icon, and optional keyboard shortcut per item.
					<div class="gb-steps">
						<span class="sb-guide-step"><span class="gs-num">1</span> Drag item → canvas (new section)</span>
						<span class="sb-guide-step"><span class="gs-num">2</span> Click type badge to change nav type</span>
						<span class="sb-guide-step"><span class="gs-num">3</span> For Group/Link+Children: drag into the indented child area</span>
						<span class="sb-guide-step"><span class="gs-num">4</span> Click <strong>⌨ shortcut</strong> pill to record a shortcut (Alt + key)</span>
						<span class="sb-guide-step"><span class="gs-num">5</span> Drag ⠿ to reorder · click ✕ to remove</span>
						<span class="sb-guide-step"><span class="gs-num">6</span> Hit <strong>Save</strong> when done</span>
					</div>
				</div>
				<button class="sb-guide-close" id="sb-guide-close">✕</button>
			</div>
			<div class="sb-layout">
				<div class="sb-palette">
					<div class="sb-palette-head">
						<div class="sb-palette-head-top">
							<span class="label">Available Items</span>
							<span class="count" id="sb-palette-count">Loading…</span>
						</div>
						<div class="sb-search">
							<span class="search-icon">🔍</span>
							<input id="sb-search" type="text" placeholder="Search doctypes, reports…" autocomplete="off">
						</div>
						<div class="sb-filter-tabs">
							<button class="sb-tab active" data-filter="all">All</button>
							<button class="sb-tab" data-filter="doctype">Doctypes</button>
							<button class="sb-tab" data-filter="report">Reports</button>
							<button class="sb-tab" data-filter="page">Pages</button>
						</div>
					</div>
					<div class="sb-palette-list" id="sb-palette-list">
						<div class="sb-empty-state"><i class="uil uil-spinner-alt"></i>Loading…</div>
					</div>
				</div>
				<div class="sb-canvas">
					<div class="sb-canvas-head">
						<span class="label">Sidebar Structure</span>
						<div class="sb-canvas-head-right">
							<span class="sb-canvas-tip">drag ⠿ to reorder</span>
							<span class="count" id="sb-canvas-count">0 sections</span>
						</div>
					</div>
					<div class="sb-canvas-body" id="sb-canvas-body">
						<div class="sb-empty-state" id="sb-empty-state">
							<i class="uil uil-sidebar-alt"></i>
							<strong>No items yet</strong>
							<p>Drag items from the left panel to build your sidebar</p>
						</div>
						<div id="sb-sections"></div>
					</div>
				</div>
			</div>
		</div>
	`);

	// Global shortcut popup (singleton)
	if (!document.getElementById("sb-shortcut-popup")) {
		const popup = document.createElement("div");
		popup.id = "sb-shortcut-popup";
		popup.className = "sb-shortcut-popup";
		popup.innerHTML = `
			<div class="sb-sp-title">Set Keyboard Shortcut</div>
			<div class="sb-sp-sub">
				Press <strong>any key</strong> for a single-key shortcut (e.g. <kbd>J</kbd>),
				<strong>two keys together</strong> for a chord (e.g. <kbd>J</kbd>+<kbd>E</kbd>),
				or <strong>Alt + key</strong>. The key <strong>N</strong> alone is reserved.
			</div>
			<div class="sb-sp-keys" id="sb-sp-keys">
				<span class="sb-sp-prompt">Press a key or key combination…</span>
			</div>
			<div class="sb-sp-error" id="sb-sp-error"></div>
			<div class="sb-sp-actions">
				<button class="sb-sp-btn danger" id="sb-sp-clear">Remove shortcut</button>
				<div style="display:flex;gap:6px">
					<button class="sb-sp-btn" id="sb-sp-cancel">Cancel</button>
					<button class="sb-sp-btn primary" id="sb-sp-apply" disabled>Apply</button>
				</div>
			</div>
		`;
		document.body.appendChild(popup);
		bind_shortcut_popup();
	}
}

// ─── STATE ───────────────────────────────────────────────────────────────────

let sb_palette_items = [];
let sb_sections = [];
let sb_filter = "all";
let sb_drag = null;

let sb_sp_context = null;
let sb_sp_pending = "";

// ─── UTILS ───────────────────────────────────────────────────────────────────

function sb_uid() {
	return "s_" + Math.random().toString(36).slice(2, 9);
}
function sb_slug(n) {
	return n
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/(^-|-$)/g, "");
}

function sb_used_keys() {
	const keys = new Set();
	sb_sections.forEach((s) => {
		keys.add(s.link_key);
		(s.children || []).forEach((c) => keys.add(c.key));
	});
	return keys;
}

function sb_used_shortcuts(exclude_id) {
	const used = new Set();
	sb_sections.forEach((s) => {
		if (s._id !== exclude_id && s.shortcut) used.add(s.shortcut.toLowerCase());
		(s.children || []).forEach((c, ci) => {
			const cid = s._id + ":" + ci;
			if (cid !== exclude_id && c.shortcut) used.add(c.shortcut.toLowerCase());
		});
	});
	return used;
}

function sb_update_canvas_count() {
	const el = document.getElementById("sb-canvas-count");
	if (el) el.textContent = sb_sections.length + " section" + (sb_sections.length !== 1 ? "s" : "");
}

function sb_palette_drag_start() {
	document.getElementById("sb-canvas-body")?.classList.add("palette-drag-active");
}
function sb_palette_drag_end() {
	const b = document.getElementById("sb-canvas-body");
	if (b) b.classList.remove("palette-drag-active", "drag-over-canvas", "child-zone-active");
}
function sb_child_zone_enter(acceptingSection) {
	const b = document.getElementById("sb-canvas-body");
	if (!b) return;
	b.classList.add("child-zone-active");
	document.querySelectorAll(".sb-section").forEach((el) => {
		el.classList.toggle("accepting-child", el === acceptingSection);
	});
}
function sb_child_zone_leave() {
	const b = document.getElementById("sb-canvas-body");
	if (b) b.classList.remove("child-zone-active");
	document.querySelectorAll(".sb-section").forEach((el) => el.classList.remove("accepting-child"));
}

// ─── LOAD PALETTE ────────────────────────────────────────────────────────────

async function load_palette_items() {
	sb_palette_items = [];
	const admin = IS_ADMIN();

	try {
		const res = await frappe.call({ method: API.doctypes });
		const doctypes = res?.message || [];
		doctypes.forEach((dt) => {
			const key = sb_slug(dt.name);
			const route = dt.issingle
				? "/app/" + key + "/" + encodeURIComponent(dt.name)
				: "/app/" + key;
			sb_palette_items.push({
				key,
				name: dt.name,
				type: "doctype",
				doctype: dt.name,
				route,
				icon: "icon-setting-gear",
				module: dt.module || "Other",
			});
		});
	} catch (e) {
		frappe.msgprint({ title: __("Warning"), message: __("Could not load doctypes."), indicator: "orange" });
	}

	try {
		let reports = [];
		if (admin) {
			const res = await frappe.call({
				method: "frappe.client.get_list",
				args: { doctype: "Report", fields: ["name", "report_type"], limit_page_length: 300, order_by: "name asc" },
			});
			reports = res?.message || [];
		} else {
			const res = await frappe.call({ method: API.reports });
			reports = res?.message || [];
		}
		reports.forEach((r) => {
			sb_palette_items.push({
				key: sb_slug(r.name),
				name: r.name,
				type: "report",
				route: "/app/query-report/" + encodeURIComponent(r.name),
				icon: "icon-report",
				module: "Reports",
			});
		});
	} catch (e) { /* silent */ }

	CUSTOM_PAGES.forEach((p) => sb_palette_items.push({ ...p, module: "Pages" }));

	const cnt = document.getElementById("sb-palette-count");
	if (cnt) cnt.textContent = sb_palette_items.length + " items";
	render_palette();
}

// ─── RENDER PALETTE ──────────────────────────────────────────────────────────

function render_palette() {
	const list = document.getElementById("sb-palette-list");
	if (!list) return;
	const q = (document.getElementById("sb-search")?.value || "").toLowerCase();
	const used = sb_used_keys();

	const filtered = sb_palette_items.filter((item) => {
		if (sb_filter !== "all" && item.type !== sb_filter) return false;
		if (q && !item.name.toLowerCase().includes(q) && !(item.module || "").toLowerCase().includes(q)) return false;
		return true;
	});

	if (!filtered.length) {
		list.innerHTML = `<div class="sb-empty-state" style="padding:20px"><span>No items match</span></div>`;
		return;
	}

	const groups = {};
	filtered.forEach((item) => {
		const g = item.module || "Other";
		(groups[g] = groups[g] || []).push(item);
	});

	list.innerHTML = "";
	Object.keys(groups).sort().forEach((group) => {
		const lbl = document.createElement("div");
		lbl.className = "sb-group-label";
		lbl.textContent = group;
		list.appendChild(lbl);

		groups[group].forEach((item) => {
			const div = document.createElement("div");
			div.className = "sb-palette-item" + (used.has(item.key) ? " in-use" : "");
			div.draggable = !used.has(item.key);
			div.dataset.key = item.key;
			const ic = item.type === "report" ? "uil uil-chart" : item.type === "page" ? "uil uil-link" : "uil uil-table";
			div.innerHTML = `
				<div class="pi-icon"><i class="${ic} icon"></i></div>
				<div class="pi-info">
					<div class="pi-name" title="${frappe.utils.escape_html(item.name)}">${frappe.utils.escape_html(item.name)}</div>
					<div class="pi-type">${item.type}</div>
				</div>
			`;
			div.addEventListener("dragstart", (e) => {
				sb_drag = { kind: "palette", item };
				e.dataTransfer.effectAllowed = "copy";
				sb_palette_drag_start();
			});
			div.addEventListener("dragend", () => {
				sb_drag = null;
				sb_palette_drag_end();
			});
			list.appendChild(div);
		});
	});
}

// ─── CANVAS ──────────────────────────────────────────────────────────────────

function add_item_to_canvas(item) {
	const is_locked = item.type === "report" || item.type === "page";
	sb_sections.push({
		_id: sb_uid(),
		label: item.name,
		icon: item.icon || "icon-setting-gear",
		parent_type: "type_3",
		route: item.route,
		link_key: item.key,
		link_type: item.type,
		doctype: item.doctype || null,
		children: [],
		_locked_type: is_locked,
		_lock_label: is_locked ? (item.type === "report" ? "Report" : "Page") : null,
		shortcut: "",
	});
	render_canvas();
	render_palette();
	sb_mark_dirty();
}

function load_canvas_from_json(frm) {
	let data = [];
	try {
		data = frm.doc.config_json ? JSON.parse(frm.doc.config_json) : [];
	} catch (e) {
		console.error("Sidebar Master: bad config_json", e);
	}
	sb_sections = data.map((s) => {
		const is_locked = s.link_type === "report" || s.link_type === "page";
		return {
			_id: sb_uid(),
			label: s.label,
			icon: s.icon || "icon-setting-gear",
			parent_type: s.parent_type,
			route: s.route || "",
			link_key: s.key,
			link_type: s.link_type || "doctype",
			doctype: s.doctype || null,
			children: (s.children || []).map((c) => ({
				key: c.key,
				name: c.name,
				type: c.type,
				route: c.route,
				doctype: c.doctype || null,
				icon: c.icon || "icon-setting-gear",
				shortcut: c.shortcut || "",
			})),
			_locked_type: is_locked,
			_lock_label: is_locked ? (s.link_type === "report" ? "Report" : "Page") : null,
			shortcut: s.shortcut || "",
		};
	});
	render_canvas();
	render_palette();
}

function save_canvas_to_json(frm) {
	const data = sb_sections.map((sec) => {
		const o = {
			key: sec.link_key,
			label: sec.label,
			icon: sec.icon,
			parent_type: sec.parent_type,
			shortcut: sec.shortcut || "",
		};
		if (sec.parent_type === "type_3" || sec.parent_type === "type_1") o.route = sec.route;
		if (sec.parent_type === "type_3") {
			o.link_type = sec.link_type;
			o.doctype = sec.doctype;
		}
		if (sec.parent_type !== "type_3" && sec.children.length)
			o.children = sec.children.map((c) => ({
				key: c.key,
				name: c.name,
				type: c.type,
				route: c.route,
				doctype: c.doctype || null,
				icon: c.icon || "icon-setting-gear",
				shortcut: c.shortcut || "",
			}));
		return o;
	});
	const nj = JSON.stringify(data, null, 2);
	if (nj !== (frm.doc.config_json || "[]")) frm.set_value("config_json", nj);
}

// ─── RENDER CANVAS ───────────────────────────────────────────────────────────

function render_canvas() {
	const sec_el = document.getElementById("sb-sections");
	const empty_el = document.getElementById("sb-empty-state");
	const body = document.getElementById("sb-canvas-body");
	if (!sec_el) return;

	sec_el.innerHTML = "";
	if (empty_el) empty_el.style.display = sb_sections.length ? "none" : "";
	sb_update_canvas_count();
	sb_sections.forEach((sec, idx) => render_section(sec, idx, sec_el));

	if (body && !body._sb_canvas_bound) {
		body._sb_canvas_bound = true;
		body.addEventListener("dragover", (e) => {
			if (!sb_drag || sb_drag.kind !== "palette") return;
			if (e.target.closest(".sb-children")) return;
			e.preventDefault();
			body.classList.add("drag-over-canvas");
		});
		body.addEventListener("dragleave", (e) => {
			if (!body.contains(e.relatedTarget)) body.classList.remove("drag-over-canvas");
		});
		body.addEventListener("drop", (e) => {
			body.classList.remove("drag-over-canvas");
			if (!sb_drag || sb_drag.kind !== "palette") return;
			if (e.target.closest(".sb-children")) return;
			e.preventDefault();
			const item = sb_drag.item;
			sb_drag = null;
			sb_palette_drag_end();
			if (sb_used_keys().has(item.key)) return;
			add_item_to_canvas(item);
		});
	}
}

// ─── RENDER SECTION ──────────────────────────────────────────────────────────

function render_section(sec, idx, container) {
	const is_type3 = sec.parent_type === "type_3";
	const is_locked = sec._locked_type;
	const typedef = TYPE_MAP[sec.parent_type] || TYPE_MAP["type_3"];

	const div = document.createElement("div");
	div.className = "sb-section";
	div.dataset.id = sec._id;
	div.dataset.ptype = sec.parent_type;

	const hdr = document.createElement("div");
	hdr.className = "sb-section-header";

	const type_html = is_locked
		? `<span class="sh-type-locked">${sec._lock_label || "Direct Link"}</span>`
		: `<div class="sh-type-wrap">
				<span class="sh-type-badge" data-type="${sec.parent_type}" title="Click to change type">
					${typedef.icon} ${typedef.short}
				</span>
				<div class="sh-type-dropdown" id="td-${sec._id}">
					${TYPE_DEFS.map((d) => `
						<div class="sh-type-option${sec.parent_type === d.value ? " active" : ""}" data-type="${d.value}">
							<span class="sh-type-option-icon">${d.icon}</span>
							<div class="sh-type-option-body">
								<div class="sh-type-option-label">${d.short}</div>
								<div class="sh-type-option-desc">${d.desc}</div>
							</div>
						</div>
					`).join("")}
				</div>
			</div>`;

	const sc_has = !!sec.shortcut;
	// For group sections show placeholder label when empty
	const needs_group_label = !is_type3 && !is_locked;

	hdr.innerHTML = `
		<span class="sh-drag" title="Drag to reorder">⠿</span>
		<button class="sh-icon-btn" title="Click to change icon">
			<svg class="icon icon-sm"><use href="#${frappe.utils.escape_html(sec.icon || "icon-setting-gear")}"></use></svg>
		</button>
		<input class="sh-label${needs_group_label && !sec.label ? " needs-input" : ""}" value="${frappe.utils.escape_html(sec.label || "")}" placeholder="${needs_group_label ? "Enter group label…" : "Label"}" spellcheck="false">
		${type_html}
		<span class="sh-shortcut-pill${sc_has ? " has-shortcut" : ""}" data-sec-id="${sec._id}" title="${sc_has ? "Shortcut: " + sec.shortcut + " (click to change)" : "Click to set a keyboard shortcut"}">
			<span class="sp-icon">⌨</span>${sc_has ? sec.shortcut : "shortcut"}
		</span>
		<button class="sh-del-btn" title="Remove section">✕</button>
	`;

	// ── Icon ──────────────────────────────────────────────────────────────────
	hdr.querySelector(".sh-icon-btn").addEventListener("click", () => open_icon_picker(sec._id, null));

	// ── Label ─────────────────────────────────────────────────────────────────
	// The key is always derived from the label automatically — users never type
	// a key manually. For group / link+children sections we keep the in-memory
	// link_key in sync with the label as the user types, so that duplicate-key
	// errors surfaced at save time reference the correct derived key.
	const labelInput = hdr.querySelector(".sh-label");
	labelInput.addEventListener("input", (e) => {
		sec.label = e.target.value;
		labelInput.classList.toggle("needs-input", needs_group_label && !sec.label.trim());
		if (!is_type3) {
			// Auto-derive key silently — no input shown, no inline error
			sec.link_key = sb_slug(e.target.value);
			sec._key_auto = true; // mark as auto-derived so validate() knows
		}
		sb_mark_dirty();
	});

	// ── Delete ────────────────────────────────────────────────────────────────
	hdr.querySelector(".sh-del-btn").addEventListener("click", () => {
		sb_sections.splice(idx, 1);
		render_canvas();
		render_palette();
		sb_mark_dirty();
	});

	// ── Shortcut pill ─────────────────────────────────────────────────────────
	hdr.querySelector(".sh-shortcut-pill").addEventListener("click", (e) => {
		e.stopPropagation();
		open_shortcut_popup(sec, null, null, e.currentTarget);
	});

	// ── Type badge & dropdown ─────────────────────────────────────────────────
	if (!is_locked) {
		const badge = hdr.querySelector(".sh-type-badge");
		const dropdown = hdr.querySelector(".sh-type-dropdown");
		badge.addEventListener("click", (e) => {
			e.stopPropagation();
			const open = dropdown.classList.toggle("open");
			if (open) {
				document.querySelectorAll(".sh-type-dropdown.open").forEach((d) => {
					if (d !== dropdown) d.classList.remove("open");
				});
			}
		});
		hdr.querySelectorAll(".sh-type-option").forEach((opt) => {
			opt.addEventListener("click", () => {
				const new_type = opt.dataset.type;
				const old_type = sec.parent_type;
				dropdown.classList.remove("open");

				// When switching FROM type_3 TO a group type, clear label and
				// key so the user provides their own group name.
				if (old_type === "type_3" && new_type !== "type_3") {
					sec.label = "";
					sec.link_key = "";
					sec._key_auto = true;
					sec.route = "";
				}

				sec.parent_type = new_type;
				render_canvas();
				sb_mark_dirty();
			});
		});
	}

	// ── Section drag ──────────────────────────────────────────────────────────
	const grip = hdr.querySelector(".sh-drag");
	grip.addEventListener("mousedown", () => { div.draggable = true; });
	div.addEventListener("dragstart", (e) => {
		if (!div.draggable) { e.preventDefault(); return; }
		sb_drag = { kind: "section", idx };
		e.dataTransfer.effectAllowed = "move";
		setTimeout(() => div.classList.add("section-dragging"), 0);
	});
	div.addEventListener("dragend", () => {
		div.draggable = false;
		div.classList.remove("section-dragging");
		document.querySelectorAll(".sb-section").forEach((s) => s.classList.remove("drag-over-section"));
		if (sb_drag?.kind === "section") sb_drag = null;
	});
	div.addEventListener("dragover", (e) => {
		if (!sb_drag || sb_drag.kind !== "section") return;
		if (e.target.closest(".sb-children")) return;
		e.preventDefault();
		document.querySelectorAll(".sb-section").forEach((s) => s.classList.remove("drag-over-section"));
		div.classList.add("drag-over-section");
	});
	div.addEventListener("dragleave", (e) => {
		if (!div.contains(e.relatedTarget)) div.classList.remove("drag-over-section");
	});
	div.addEventListener("drop", (e) => {
		if (e.target.closest(".sb-children")) return;
		e.preventDefault();
		div.classList.remove("drag-over-section");
		if (!sb_drag || sb_drag.kind !== "section") return;
		const from = sb_drag.idx, to = idx;
		sb_drag = null;
		if (from === to) return;
		const [moved] = sb_sections.splice(from, 1);
		sb_sections.splice(to, 0, moved);
		render_canvas();
		sb_mark_dirty();
	});

	div.appendChild(hdr);

	// ── Children zone ─────────────────────────────────────────────────────────
	if (!is_type3) {
		const divider = document.createElement("div");
		divider.className = "sb-section-divider";
		divider.innerHTML = `<span class="sd-label">Child links</span><span class="sd-count">${sec.children.length || "none"}</span>`;
		div.appendChild(divider);
		div.appendChild(make_children_zone(sec, div));
	}

	document.addEventListener("click", () => {
		hdr.querySelector(".sh-type-dropdown")?.classList.remove("open");
	}, { once: false, capture: false });

	container.appendChild(div);
}

// ─── CHILDREN ZONE ───────────────────────────────────────────────────────────

function make_children_zone(sec, sectionEl) {
	const zone = document.createElement("div");
	zone.className = "sb-children";
	zone.dataset.parentId = sec._id;

	const refresh_zone = () => {
		zone.innerHTML = "";
		const bar = document.createElement("div");
		bar.className = "sb-children-drop-bar";
		bar.innerHTML = `<span>↓ Drop here to add child link</span>`;
		zone.appendChild(bar);
		sec.children.forEach((child, ci) => zone.appendChild(make_child_el(sec, child, ci, refresh_zone)));
		const divider = sectionEl.querySelector(".sd-count");
		if (divider) divider.textContent = sec.children.length || "none";
	};
	refresh_zone();

	zone.addEventListener("dragenter", (e) => {
		if (!sb_drag || sb_drag.kind !== "palette") return;
		e.preventDefault();
		zone.classList.add("drop-over");
		sb_child_zone_enter(sectionEl);
	});
	zone.addEventListener("dragover", (e) => {
		if (!sb_drag) return;
		if (sb_drag.kind === "palette") {
			e.preventDefault(); e.stopPropagation();
			zone.classList.add("drop-over");
		} else if (sb_drag.kind === "child" && sb_drag.sec === sec) {
			e.preventDefault();
		}
	});
	zone.addEventListener("dragleave", (e) => {
		if (!zone.contains(e.relatedTarget)) { zone.classList.remove("drop-over"); sb_child_zone_leave(); }
	});
	zone.addEventListener("drop", (e) => {
		zone.classList.remove("drop-over");
		sb_child_zone_leave();
		if (!sb_drag || sb_drag.kind !== "palette") return;
		e.preventDefault(); e.stopPropagation();
		const item = sb_drag.item;
		sb_drag = null;
		sb_palette_drag_end();
		if (sb_used_keys().has(item.key)) return;
		sec.children.push({ key: item.key, name: item.name, type: item.type, route: item.route, doctype: item.doctype || null, icon: item.icon || "icon-setting-gear", shortcut: "" });
		refresh_zone();
		render_palette();
		sb_mark_dirty();
	});

	return zone;
}

// ─── CHILD ELEMENT ───────────────────────────────────────────────────────────

function make_child_el(sec, child, ci, refresh_zone) {
	const li = document.createElement("div");
	li.className = "sb-child";
	li.dataset.childIdx = ci;

	const sc_has = !!child.shortcut;
	const sc_label = sc_has ? child.shortcut : "⌨";

	li.innerHTML = `
		<span class="ci-drag" title="Drag to reorder">⠿</span>
		<button class="ci-icon-btn" title="Click to change icon">
			<svg class="icon icon-xs"><use href="#${frappe.utils.escape_html(child.icon || "icon-setting-gear")}"></use></svg>
		</button>
		<span class="ci-label" title="${frappe.utils.escape_html(child.name)}">${frappe.utils.escape_html(child.name)}</span>
		<span class="ci-badge">${child.type}</span>
		<span class="ci-shortcut${sc_has ? " has-shortcut" : ""}" title="${sc_has ? "Shortcut: " + child.shortcut + " (click to change)" : "Click to set shortcut"}">${sc_label}</span>
		<button class="ci-del" title="Remove">✕</button>
	`;

	li.querySelector(".ci-icon-btn").addEventListener("click", (e) => {
		e.stopPropagation();
		open_icon_picker(null, { sec, ci, refresh_zone });
	});
	li.querySelector(".ci-del").addEventListener("click", () => {
		sec.children.splice(ci, 1);
		refresh_zone();
		render_palette();
		sb_mark_dirty();
	});
	li.querySelector(".ci-shortcut").addEventListener("click", (e) => {
		e.stopPropagation();
		open_shortcut_popup(sec, child, refresh_zone, e.currentTarget);
	});

	const grip = li.querySelector(".ci-drag");
	grip.addEventListener("mousedown", () => { li.draggable = true; });
	li.addEventListener("dragstart", (e) => {
		if (!li.draggable) { e.preventDefault(); return; }
		e.stopPropagation();
		sb_drag = { kind: "child", sec, ci };
		e.dataTransfer.effectAllowed = "move";
		setTimeout(() => li.classList.add("child-dragging"), 0);
	});
	li.addEventListener("dragend", () => {
		li.draggable = false;
		li.classList.remove("child-dragging");
		li.closest(".sb-children")?.querySelectorAll(".child-drag-over").forEach((el) => el.classList.remove("child-drag-over"));
		if (sb_drag?.kind === "child") sb_drag = null;
	});
	li.addEventListener("dragover", (e) => {
		if (!sb_drag || sb_drag.kind !== "child" || sb_drag.sec !== sec) return;
		e.preventDefault(); e.stopPropagation();
		li.closest(".sb-children")?.querySelectorAll(".child-drag-over").forEach((el) => el.classList.remove("child-drag-over"));
		if (sb_drag.ci !== ci) li.classList.add("child-drag-over");
	});
	li.addEventListener("drop", (e) => {
		e.preventDefault(); e.stopPropagation();
		li.classList.remove("child-drag-over");
		if (!sb_drag || sb_drag.kind !== "child" || sb_drag.sec !== sec) return;
		const from = sb_drag.ci, to = ci;
		sb_drag = null;
		if (from === to) return;
		const [moved] = sec.children.splice(from, 1);
		sec.children.splice(to, 0, moved);
		refresh_zone();
		sb_mark_dirty();
	});

	return li;
}

// ─── SHORTCUT POPUP ──────────────────────────────────────────────────────────

function bind_shortcut_popup() {
	const popup = document.getElementById("sb-shortcut-popup");
	const keysEl = document.getElementById("sb-sp-keys");
	const errorEl = document.getElementById("sb-sp-error");
	const applyBtn = document.getElementById("sb-sp-apply");
	const clearBtn = document.getElementById("sb-sp-clear");
	const cancelBtn = document.getElementById("sb-sp-cancel");

	let chord_first = null;
	let chord_timer = null;
	const CHORD_WAIT_MS = 1000;
	const MODIFIER_KEYS = new Set(["Alt", "Control", "Shift", "Meta", "CapsLock", "Tab"]);

	function show_error(msg) {
		errorEl.textContent = msg;
		keysEl.classList.add("error");
		keysEl.classList.remove("recording");
		setTimeout(() => {
			errorEl.textContent = "";
			keysEl.classList.remove("error");
			keysEl.classList.add("recording");
			reset_chord();
		}, 2000);
	}
	function reset_chord() {
		chord_first = null;
		clearTimeout(chord_timer);
		chord_timer = null;
	}
	function render_waiting_for_second(firstKey) {
		keysEl.innerHTML = `
			<span class="sb-sp-key">${firstKey}</span>
			<span class="sb-sp-plus">+</span>
			<span class="sb-sp-prompt" style="font-size:11px">press second key or wait…</span>
		`;
		keysEl.classList.remove("error");
		keysEl.classList.add("recording");
	}
	function set_keys_display(shortcut) {
		if (!shortcut) {
			keysEl.innerHTML = `<span class="sb-sp-prompt">Press a key or key combination…</span>`;
			keysEl.classList.remove("error");
			keysEl.classList.add("recording");
			applyBtn.disabled = true;
		} else {
			const parts = shortcut.split("+");
			if (parts.length === 1) {
				keysEl.innerHTML = `<span class="sb-sp-key">${parts[0]}</span>`;
			} else {
				keysEl.innerHTML = parts.map((p) => `<span class="sb-sp-key">${p}</span>`).join(`<span class="sb-sp-plus">+</span>`);
			}
			keysEl.classList.remove("error", "recording");
			applyBtn.disabled = false;
		}
	}
	function close_popup() {
		popup.classList.remove("open");
		sb_sp_context = null;
		sb_sp_pending = "";
		reset_chord();
		document.removeEventListener("keydown", handle_key, true);
		document.removeEventListener("keyup", handle_keyup, true);
	}
	function commit_shortcut(shortcut) {
		reset_chord();
		const ctx = sb_sp_context;
		if (!ctx) return;
		const exclude_id = ctx.child ? ctx.sec._id + ":" + ctx.sec.children.indexOf(ctx.child) : ctx.sec._id;
		const used = sb_used_shortcuts(exclude_id);
		if (used.has(shortcut.toLowerCase())) {
			show_error(`"${shortcut}" is already used by another item`);
			return;
		}
		sb_sp_pending = shortcut;
		set_keys_display(shortcut);
		errorEl.textContent = "";
	}
	function handle_key(e) {
		e.preventDefault(); e.stopPropagation();
		if (e.key === "Escape") { close_popup(); return; }
		if (MODIFIER_KEYS.has(e.key)) return;
		const raw_key = e.key.length === 1 ? e.key.toUpperCase() : e.key;
		let shortcut = "";
		if (e.altKey) {
			if (raw_key.toLowerCase() === "n") { show_error('"N" is reserved and cannot be used'); return; }
			shortcut = "Alt+" + raw_key;
			reset_chord(); commit_shortcut(shortcut); return;
		}
		if (e.ctrlKey) {
			if (raw_key.toLowerCase() === "n") { show_error('"N" is reserved and cannot be used'); return; }
			shortcut = "Ctrl+" + raw_key;
			reset_chord(); commit_shortcut(shortcut); return;
		}
		if (raw_key.toLowerCase() === "n" && !chord_first) {
			show_error('"N" alone is reserved. Use it as the second key of a chord (e.g. J+N) or with Alt/Ctrl.');
			return;
		}
		if (chord_first) {
			shortcut = chord_first + "+" + raw_key;
			reset_chord(); commit_shortcut(shortcut);
		} else {
			chord_first = raw_key;
			render_waiting_for_second(chord_first);
			chord_timer = setTimeout(() => {
				if (!chord_first) return;
				const single = chord_first;
				reset_chord(); commit_shortcut(single);
			}, CHORD_WAIT_MS);
		}
	}
	function handle_keyup() {}

	applyBtn.addEventListener("click", () => {
		if (!sb_sp_pending || !sb_sp_context) return;
		if (sb_sp_context.child) {
			sb_sp_context.child.shortcut = sb_sp_pending;
			if (sb_sp_context.refresh_zone) sb_sp_context.refresh_zone();
		} else {
			sb_sp_context.sec.shortcut = sb_sp_pending;
			render_canvas();
		}
		sb_mark_dirty();
		close_popup();
	});
	clearBtn.addEventListener("click", () => {
		if (!sb_sp_context) return;
		if (sb_sp_context.child) {
			sb_sp_context.child.shortcut = "";
			if (sb_sp_context.refresh_zone) sb_sp_context.refresh_zone();
		} else {
			sb_sp_context.sec.shortcut = "";
			render_canvas();
		}
		sb_mark_dirty();
		close_popup();
	});
	cancelBtn.addEventListener("click", close_popup);

	popup._open = function (ctx, anchor) {
		sb_sp_context = ctx;
		sb_sp_pending = ctx.child ? ctx.child.shortcut || "" : ctx.sec.shortcut || "";
		reset_chord();
		set_keys_display(sb_sp_pending);
		errorEl.textContent = "";
		const r = anchor.getBoundingClientRect();
		const pw = 340, ph = 250;
		let left = r.left, top = r.bottom + 6;
		if (left + pw > window.innerWidth - 10) left = window.innerWidth - pw - 10;
		if (top + ph > window.innerHeight - 10) top = r.top - ph - 6;
		popup.style.left = Math.max(8, left) + "px";
		popup.style.top = Math.max(8, top) + "px";
		popup.classList.add("open");
		document.addEventListener("keydown", handle_key, true);
		document.addEventListener("keyup", handle_keyup, true);
		setTimeout(() => {
			document.addEventListener("click", function outside(ev) {
				if (!popup.contains(ev.target) && ev.target !== anchor) {
					close_popup();
					document.removeEventListener("click", outside);
				}
			});
		}, 50);
	};
}

function open_shortcut_popup(sec, child, refresh_zone, anchor) {
	const popup = document.getElementById("sb-shortcut-popup");
	if (!popup || !popup._open) return;
	popup._open({ sec, child, refresh_zone }, anchor);
}

// ─── ICON PICKER ─────────────────────────────────────────────────────────────

let icon_picker_selected = null;

function open_icon_picker(section_id, child_ctx) {
	if (section_id) {
		icon_picker_selected = sb_sections.find((s) => s._id === section_id)?.icon || null;
	} else if (child_ctx) {
		icon_picker_selected = child_ctx.sec.children[child_ctx.ci]?.icon || null;
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Choose Icon"),
		fields: [
			{ fieldtype: "Data", fieldname: "icon_search", label: __("Search Icons"), placeholder: "e.g. user, mail, file…" },
			{ fieldtype: "HTML", fieldname: "icon_grid_html", options: `<div class="sb-icon-grid" id="sb-icon-picker-grid">${build_icon_grid_html("")}</div>` },
		],
		primary_action_label: __("Apply"),
		primary_action() {
			if (!icon_picker_selected) { dialog.hide(); return; }
			if (section_id) {
				const sec = sb_sections.find((s) => s._id === section_id);
				if (sec) { sec.icon = icon_picker_selected; render_canvas(); sb_mark_dirty(); }
			} else if (child_ctx) {
				const child = child_ctx.sec.children[child_ctx.ci];
				if (child) { child.icon = icon_picker_selected; child_ctx.refresh_zone(); sb_mark_dirty(); }
			}
			dialog.hide();
		},
	});
	dialog.show();
	dialog.fields_dict.icon_search.$input.on("input", function () {
		dialog.$wrapper.find("#sb-icon-picker-grid").html(build_icon_grid_html($(this).val()));
		bind_icon_chips(dialog);
	});
	bind_icon_chips(dialog);
}

function build_icon_grid_html(q) {
	const list = q ? FRAPPE_ICONS.filter((i) => i.label.toLowerCase().includes(q.toLowerCase()) || i.id.includes(q.toLowerCase())) : FRAPPE_ICONS;
	return list.map((ic) => `
		<div class="sb-icon-chip${ic.id === icon_picker_selected ? " selected" : ""}" data-icon="${ic.id}">
			<svg class="icon icon-md"><use href="#${ic.id}"></use></svg>
			<span>${ic.label}</span>
		</div>
	`).join("");
}

function bind_icon_chips(dialog) {
	dialog.$wrapper.find(".sb-icon-chip").on("click", function () {
		dialog.$wrapper.find(".sb-icon-chip").removeClass("selected");
		$(this).addClass("selected");
		icon_picker_selected = $(this).data("icon");
	});
}

// ─── TOOLBAR ─────────────────────────────────────────────────────────────────

function bind_toolbar(frm) {
	const wrapper = frm.get_field("sidebar_builder").$wrapper;
	wrapper.find(".sb-tab").off("click").on("click", function () {
		wrapper.find(".sb-tab").removeClass("active");
		$(this).addClass("active");
		sb_filter = $(this).data("filter");
		render_palette();
	});
	wrapper.find("#sb-search").off("input").on("input", () => render_palette());
	document.getElementById("sb-guide-close")?.addEventListener("click", () => {
		document.getElementById("sb-guide-banner").style.display = "none";
	});
}