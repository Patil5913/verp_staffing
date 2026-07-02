//  Config is fetched, PRE-FILTERED, from a single server-driven API:
//    verp_staffing.api.sidebar.get_sidebar_permissions
//
//  SERVER IS THE SOURCE OF TRUTH:
//    The client NEVER computes write-permission or role checks itself, and
//    there isn't even a permission flag to look up client-side — the
//    server only ever returns the parents/children the current user can
//    already access. Anything they can't access simply isn't in the
//    payload. The server resolves the tree from the "Sidebar Master"
//    DocType (field: config_json) using the same two-step lookup as
//    before:
//      1. Doc where sidebar_owner = current user  → use it
//      2. Fall back to the doc where sidebar_owner = "Master"
//    filters it down to accessible items, caches the RESULT (not the raw
//    config) in Redis (frappe.cache()) per-user, and invalidates
//    automatically whenever User / Has Role / Role / DocPerm /
//    Custom DocPerm / Employee change (see hooks.py + api/sidebar.py).
//    Shipping a pre-filtered, per-user tree instead of a flat config +
//    permission map keeps both the Redis entry and the JSON sent to the
//    browser as small as possible — important once this is serving
//    1000+ distinct users each with their own shape of tree.
//
//  THREE PARENT TYPES:
//    type_1 — redirect + always-visible children (no toggle)
//    type_2 — dropdown group, no redirect, SPA toggle (zero page reload)
//    type_3 — single link, no children
//
//  SHORTCUT SUPPORT:
//    Each item may carry a `shortcut` field (e.g. "J", "J+E", "Alt+P").
//    Shortcuts are shown in a tooltip on hover (not inline) so the label
//    remains fully readable. The tooltip shows: label + shortcut badge.
//    "N" alone is reserved.
//
//  OVERFLOW TOOLTIP:
//    Any sidebar label that is visually truncated ("...") will show a tooltip
//    with the full label text on hover. If the item also has a shortcut, both
//    the full label and the shortcut badge are shown together in one tooltip.
//    Items with shortcuts always show the tooltip regardless of truncation.
//
//  NO_PLUS_DOCTYPES:
//    Doctypes listed here will NOT show the quick-create "+" button in the sidebar.
//    The same set is used to suppress the "New" button on those doctypes'
//    list pages. Edit this array to add/remove items — no other code changes
//    needed.
//
//  FEATURES:
//    ✓ type_2 toggle is pure DOM/CSS — zero page reload
//    ✓ "+" quick-create button on every doctype link (except NO_PLUS_DOCTYPES)
//    ✓ Pre-filtered, per-user tree fetched in ONE server call, cached in Redis
//    ✓ localStorage is a short-lived UI cache only (TTL 5–15 min, jittered)
//      — never the source of truth for access control
//    ✓ Logo + home navigation redirected to first accessible route
//    ✓ "Customize Sidebar" button at bottom of sidebar
//    ✓ Full-width is on by default; "Toggle Full Width" navbar button hidden
//    ✓ List-page New button hidden for doctypes in NO_PLUS_DOCTYPES
//    ✓ Overflow tooltip for truncated labels (merged with shortcut tooltip)
//    ✓ Visibility is implicit: if it's in the payload, it's accessible
// ═══════════════════════════════════════════════════════════════════════════
(function () {
	"use strict";

	// ─── NO QUICK-CREATE / NO NEW-BUTTON LIST ─────────────────────────────────
	//
	// Add the palette key (slug format) of any doctype/item for which you want to:
	//   1. Hide the "+" quick-create button in the sidebar
	//   2. Hide the "New" button on that doctype's list page
	//
	const NO_PLUS_DOCTYPES = new Set([
		"Onboardings",
		"GL Entry",
		"Supplier Group",
		"CR",
		"Agreement",
		"CRM Note",
		"CRM Event",
		"CRM Task",
		"Lead Detail Form",
		"Sales Stage",
		"Interview Status",
		"Type Of Interview",
		"Other Services",
		"Marketing Other Services",
		"Marketing",
		"Item Category",
		"UOM",
		"Cover Letter",
		"JDC",
		"Resume",
		"RUC",
		"Technical Other Services",
		"Training",
		"Bank Account Type",
		"Bank Account Subtype",
		"Sidebar Master",
	]);

	// ─── FULL WIDTH DEFAULT ────────────────────────────────────────────────────
	(function enforce_full_width() {
		document.documentElement.classList.add("fw-patched");
		function _apply() {
			document.body.classList.add("full-width");
			document.querySelectorAll(".dropdown-menu li, .dropdown-item").forEach((el) => {
				if (el.textContent && el.textContent.trim() === "Toggle Full Width") {
					el.style.display = "none";
				}
			});
		}
		_apply();
		const _fw_obs = new MutationObserver(_apply);
		if (document.body) {
			_fw_obs.observe(document.body, { childList: true, subtree: true });
		} else {
			document.addEventListener("DOMContentLoaded", () => {
				_fw_obs.observe(document.body, { childList: true, subtree: true });
			});
		}
	})();

	// ─── CACHE (localStorage — UI performance layer ONLY, not auth) ───────────
	// This never decides access on its own; it just avoids re-fetching the
	// server's permission payload on every page load. The server (Redis) is
	// always the authority, and is what actually enforces permissions no
	// matter what a user does to this local cache.
	function cache_key() {
		return "csb_config_" + ((frappe.session && frappe.session.user) || "guest");
	}
	function cache_ts_key() {
		return "csb_ts_" + ((frappe.session && frappe.session.user) || "guest");
	}
	function cache_ttl_key() {
		return "csb_ttl_" + ((frappe.session && frappe.session.user) || "guest");
	}

	let SIDEBAR_CONFIG = [];
	let NAV_ITEMS = {};

	// ─── PERMISSIONS ────────────────────────────────────────────────────────
	// There is no client-side permission logic at all anymore, not even a
	// flag lookup. The server only ever ships parents/children the user can
	// already access (see api/sidebar.py) — an inaccessible item simply
	// isn't present in SIDEBAR_CONFIG. These two helpers are kept as thin
	// passthroughs purely so the rendering code below doesn't need two code
	// paths; there is nothing left to check.
	function visible_children(parent_cfg) {
		return parent_cfg.children || [];
	}

	function parent_visible(_cfg) {
		return true;
	}

	// ─── ROUTING ──────────────────────────────────────────────────────────────
	function current_path() {
		let p = window.location.pathname;
		try {
			p = decodeURIComponent(p);
		} catch (e) {}
		return p.replace(/\/+$/, "");
	}
	function key_is_active(key) {
		const item = NAV_ITEMS[key];
		if (!item) return false;
		const route = item.route.replace(/\/+$/, "");
		const path = current_path();
		return path === route || path.startsWith(route + "/");
	}
	function parent_route_is_active(cfg) {
		if (!cfg.route) return false;
		const route = cfg.route.replace(/\/+$/, "");
		const path = current_path();
		return path === route || path.startsWith(route + "/");
	}
	function get_active_owner_key() {
		for (const cfg of SIDEBAR_CONFIG) {
			if (!parent_visible(cfg)) continue;
			if (cfg.parent_type === "type_3" && parent_route_is_active(cfg)) return cfg.key;
			if (cfg.parent_type === "type_1") {
				if (
					parent_route_is_active(cfg) ||
					(cfg.children && cfg.children.some((c) => key_is_active(c.key)))
				)
					return cfg.key;
			}
			if (cfg.parent_type === "type_2") {
				if (cfg.children && cfg.children.some((c) => key_is_active(c.key))) return cfg.key;
			}
		}
		return null;
	}

	// ─── EXPAND / COLLAPSE ────────────────────────────────────────────────────
	const EXP_KEY =
		"csb_expanded_" + ((window.frappe && frappe.session && frappe.session.user) || "guest");
	function load_expanded_key() {
		try {
			return localStorage.getItem(EXP_KEY) || null;
		} catch (e) {
			return null;
		}
	}
	function save_expanded_key(key) {
		try {
			key ? localStorage.setItem(EXP_KEY, key) : localStorage.removeItem(EXP_KEY);
		} catch (e) {}
	}
	function route_forced_expand_key() {
		for (const cfg of SIDEBAR_CONFIG) {
			if (
				cfg.parent_type === "type_2" &&
				cfg.children &&
				cfg.children.some((c) => key_is_active(c.key))
			)
				return cfg.key;
		}
		return null;
	}
	function compute_expanded_key() {
		return route_forced_expand_key() || load_expanded_key();
	}

	// ─── SPA NAVIGATE ─────────────────────────────────────────────────────────
	function spa_navigate(route) {
		if (window.frappe && frappe.set_route) {
			frappe.set_route(route.replace(/^\/app\//, ""));
		} else {
			window.location.href = route;
		}
	}

	// ─── DOM HELPERS ──────────────────────────────────────────────────────────
	function make_icon(icon_id, size) {
		size = size || "sm";
		const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		svg.setAttribute("class", "icon icon-" + size);
		svg.setAttribute("aria-hidden", "true");
		const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
		use.setAttribute("href", "#" + icon_id);
		svg.appendChild(use);
		return svg;
	}
	function make_item_inner(icon_id, label_text) {
		const icon_wrap = document.createElement("span");
		icon_wrap.className = "cn-item-icon";
		if (icon_id) icon_wrap.appendChild(make_icon(icon_id, "sm"));
		const label = document.createElement("span");
		label.className = "cn-item-label";
		label.textContent = label_text;
		return [icon_wrap, label];
	}

	// ─── "+" QUICK-CREATE BUTTON ──────────────────────────────────────────────
	function make_plus_btn(doctype) {
		const btn = document.createElement("button");
		btn.className = "cn-plus-btn";
		btn.setAttribute("aria-label", "New " + doctype);
		btn.setAttribute("title", "New " + doctype);
		btn.innerHTML =
			'<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="4" x2="12" y2="20"/><line x1="4" y1="12" x2="20" y2="12"/></svg>';
		btn.addEventListener("click", function (e) {
			e.preventDefault();
			e.stopPropagation();
			if (window.frappe && frappe.new_doc) frappe.new_doc(doctype);
			else spa_navigate("/app/" + doctype.toLowerCase().replace(/\s+/g, "-") + "/new");
		});
		return btn;
	}

	// Returns true if the "+" quick-create button should be shown for this item.
	function should_show_plus(doctype, item) {
		if (NO_PLUS_DOCTYPES.has(doctype)) return false;
		if (!item || item.type !== "doctype" || !item.doctype) return false;
		if (item.issingle) return false;
		return true;
	}

	// ─── UNIFIED TOOLTIP (overflow + shortcut) ────────────────────────────────
	let _tooltip_el = null;
	function get_tooltip_el() {
		if (!_tooltip_el) {
			_tooltip_el = document.createElement("div");
			_tooltip_el.id = "csb-shortcut-tooltip";
			document.body.appendChild(_tooltip_el);
		}
		return _tooltip_el;
	}
	function show_tooltip(anchor, label, shortcut) {
		const el = get_tooltip_el();
		const safe_label = frappe.utils.escape_html(label);
		if (shortcut) {
			const safe_sc = frappe.utils.escape_html(shortcut);
			el.innerHTML = `<span class="csb-tt-label">${safe_label}</span><kbd class="csb-tt-key">${safe_sc}</kbd>`;
		} else {
			el.innerHTML = `<span class="csb-tt-label">${safe_label}</span>`;
		}
		el.style.display = "flex";
		position_tooltip(el, anchor);
	}
	function hide_tooltip() {
		const el = get_tooltip_el();
		el.style.display = "none";
	}
	function position_tooltip(el, anchor) {
		const r = anchor.getBoundingClientRect();
		el.style.left = r.right + 8 + "px";
		el.style.top = r.top + r.height / 2 + "px";
		el.style.transform = "translateY(-50%)";
		requestAnimationFrame(() => {
			const tw = el.offsetWidth;
			if (r.right + 8 + tw > window.innerWidth - 8) {
				el.style.left = r.left - tw - 8 + "px";
			}
		});
	}
	function label_is_overflowing(anchor) {
		const label_el = anchor.querySelector(".cn-item-label");
		if (!label_el) return false;
		return label_el.scrollWidth > label_el.offsetWidth;
	}
	function attach_tooltip(el, label, shortcut) {
		el.setAttribute("data-csb-label", label);
		if (shortcut) el.setAttribute("data-csb-shortcut", shortcut);
		function on_enter() {
			const has_shortcut = !!shortcut;
			const overflowing = label_is_overflowing(el);
			if (has_shortcut || overflowing) {
				show_tooltip(el, label, shortcut || null);
			}
		}
		el.addEventListener("mouseenter", on_enter);
		el.addEventListener("focus", on_enter);
		el.addEventListener("mouseleave", hide_tooltip);
		el.addEventListener("blur", hide_tooltip);
	}

	// ─── SIDEBAR DOM ──────────────────────────────────────────────────────────
	const SIDEBAR_ID = "custom-nav-sidebar";
	function build_sidebar_dom() {
		const wrap = document.createElement("div");
		wrap.id = SIDEBAR_ID;
		wrap.className = "custom-nav-sidebar";
		SIDEBAR_CONFIG.forEach(function (cfg) {
			if (!parent_visible(cfg)) return;
			if (cfg.parent_type === "type_3") {
				wrap.appendChild(make_type3_el(cfg));
				return;
			}
			if (cfg.parent_type === "type_1") {
				wrap.appendChild(make_type1_el(cfg));
				return;
			}
			if (cfg.parent_type === "type_2") {
				wrap.appendChild(make_type2_el(cfg));
				return;
			}
		});
		wrap.appendChild(make_customize_btn());
		return wrap;
	}

	// ─── CUSTOMIZE SIDEBAR BUTTON ─────────────────────────────────────────────
	function make_customize_btn() {
		const btn = document.createElement("a");
		btn.className = "cn-item cn-customize-btn";
		btn.href = "#";
		btn.title = "Customize your sidebar layout";
		const icon_wrap = document.createElement("span");
		icon_wrap.className = "cn-item-icon";
		icon_wrap.innerHTML = `<svg class="icon icon-sm" aria-hidden="true"><use href="#icon-setting-gear"></use></svg>`;
		const label = document.createElement("span");
		label.className = "cn-item-label";
		label.textContent = "Customize Sidebar";
		btn.appendChild(icon_wrap);
		btn.appendChild(label);
		btn.addEventListener("click", async function (e) {
			e.preventDefault();
			const current_user = frappe.session && frappe.session.user;
			if (!current_user) {
				spa_navigate("/app/sidebar-master/new");
				return;
			}
			try {
				const res = await frappe.call({
					method: "frappe.client.get_value",
					args: {
						doctype: "Sidebar Master",
						fieldname: "name",
						filters: { sidebar_owner: current_user },
					},
				});
				const doc_name = res && res.message && res.message.name;
				if (doc_name) {
					spa_navigate("/app/sidebar-master/" + encodeURIComponent(doc_name));
				} else {
					spa_navigate("/app/sidebar-master/new");
				}
			} catch (err) {
				spa_navigate("/app/sidebar-master/new");
			}
		});
		return btn;
	}

	function make_type3_el(cfg) {
		const a = document.createElement("a");
		a.className = "cn-item cn-parent-link" + (parent_route_is_active(cfg) ? " is-active" : "");
		a.href = cfg.route || "#";
		a.dataset.parentKey = cfg.key;
		a.dataset.parentType = "type_3";
		make_item_inner(cfg.icon, cfg.label).forEach((el) => a.appendChild(el));
		if (
			should_show_plus(cfg.doctype, {
				type: cfg.link_type,
				doctype: cfg.doctype,
				issingle: cfg.issingle,
			})
		) {
			a.appendChild(make_plus_btn(cfg.doctype));
		}
		attach_tooltip(a, cfg.label, cfg.shortcut || "");
		a.addEventListener("click", function (e) {
			e.preventDefault();
			hide_tooltip();
			spa_navigate(cfg.route);
		});
		return a;
	}

	function make_type1_el(cfg) {
		const owner_key = get_active_owner_key();
		const wrap = document.createElement("div");
		wrap.className = "cn-group cn-group--type1" + (owner_key === cfg.key ? " has-active" : "");
		wrap.dataset.parentKey = cfg.key;
		const a = document.createElement("a");
		a.className = "cn-item cn-parent-link" + (parent_route_is_active(cfg) ? " is-active" : "");
		a.href = cfg.route || "#";
		a.dataset.parentKey = cfg.key;
		a.dataset.parentType = "type_1";
		make_item_inner(cfg.icon, cfg.label).forEach((el) => a.appendChild(el));
		attach_tooltip(a, cfg.label, cfg.shortcut || "");
		a.addEventListener("click", function (e) {
			e.preventDefault();
			hide_tooltip();
			spa_navigate(cfg.route);
		});
		wrap.appendChild(a);
		const kids = visible_children(cfg);
		if (kids.length) {
			const ul = document.createElement("ul");
			ul.className = "cn-children cn-children--type1";
			kids.forEach(function (child) {
				const item = NAV_ITEMS[child.key];
				if (!item) return;
				const li = document.createElement("li");
				const ca = document.createElement("a");
				ca.className =
					"cn-item cn-child-link" +
					(owner_key === cfg.key && key_is_active(child.key) ? " is-active" : "");
				ca.href = item.route;
				ca.dataset.navKey = child.key;
				make_item_inner(item.icon, item.name).forEach((el) => ca.appendChild(el));
				if (should_show_plus(child.doctype, item)) {
					ca.appendChild(make_plus_btn(item.doctype));
				}
				attach_tooltip(ca, item.name, item.shortcut || "");
				ca.addEventListener("click", function (e) {
					e.preventDefault();
					hide_tooltip();
					spa_navigate(item.route);
				});
				li.appendChild(ca);
				ul.appendChild(li);
			});
			wrap.appendChild(ul);
		}
		return wrap;
	}

	function make_type2_el(cfg) {
		const expanded = compute_expanded_key() === cfg.key;
		const owner_key = get_active_owner_key();
		const kids = visible_children(cfg);
		const wrap = document.createElement("div");
		wrap.className = "cn-group cn-group--type2" + (expanded ? " is-expanded" : "");
		wrap.dataset.parentKey = cfg.key;
		const header = document.createElement("div");
		header.className = "cn-item cn-parent-toggle";
		header.setAttribute("role", "button");
		header.setAttribute("tabindex", "0");
		header.setAttribute("aria-expanded", expanded ? "true" : "false");
		header.dataset.parentKey = cfg.key;
		make_item_inner(cfg.icon, cfg.label).forEach((el) => header.appendChild(el));
		attach_tooltip(header, cfg.label, cfg.shortcut || "");
		const chevron = document.createElement("span");
		chevron.className = "cn-chevron";
		chevron.innerHTML =
			'<svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,6 8,10 12,6"/></svg>';
		header.appendChild(chevron);
		function toggle_group(e) {
			e.stopPropagation();
			hide_tooltip();
			const is_open = wrap.classList.contains("is-expanded");
			document.querySelectorAll(".cn-group--type2").forEach(function (other) {
				if (other !== wrap) {
					other.classList.remove("is-expanded");
					const h = other.querySelector(".cn-parent-toggle");
					if (h) h.setAttribute("aria-expanded", "false");
				}
			});
			const next = !is_open;
			wrap.classList.toggle("is-expanded", next);
			header.setAttribute("aria-expanded", next ? "true" : "false");
			save_expanded_key(next ? cfg.key : null);
		}
		header.addEventListener("click", toggle_group);
		header.addEventListener("keydown", function (e) {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				toggle_group(e);
			}
		});
		wrap.appendChild(header);
		const ul = document.createElement("ul");
		ul.className = "cn-children";
		kids.forEach(function (child) {
			const item = NAV_ITEMS[child.key];
			if (!item) return;
			const li = document.createElement("li");
			const a = document.createElement("a");
			a.className =
				"cn-item cn-child-link" +
				(owner_key === cfg.key && key_is_active(child.key) ? " is-active" : "");
			a.href = item.route;
			a.dataset.navKey = child.key;
			make_item_inner(item.icon, item.name).forEach((el) => a.appendChild(el));
			if (should_show_plus(child.doctype, item)) {
				a.appendChild(make_plus_btn(item.doctype));
			}
			attach_tooltip(a, item.name, item.shortcut || "");
			a.addEventListener("click", function (e) {
				e.preventDefault();
				hide_tooltip();
				spa_navigate(item.route);
			});
			li.appendChild(a);
			ul.appendChild(li);
		});
		wrap.appendChild(ul);
		return wrap;
	}

	// ─── MOUNT / REFRESH ──────────────────────────────────────────────────────
	function mount_sidebar() {
		document.querySelectorAll(".layout-side-section").forEach(function (section) {
			if (section.querySelector("#" + SIDEBAR_ID)) return;
			section.appendChild(build_sidebar_dom());
		});
	}
	function refresh_sidebar_active() {
		const owner_key = get_active_owner_key();
		const expanded_key = compute_expanded_key();
		document.querySelectorAll(".cn-parent-link[data-parent-key]").forEach(function (el) {
			const cfg = SIDEBAR_CONFIG.find((c) => c.key === el.dataset.parentKey);
			if (!cfg) return;
			el.classList.toggle("is-active", parent_route_is_active(cfg));
		});
		document.querySelectorAll(".cn-group--type1[data-parent-key]").forEach(function (el) {
			el.classList.toggle("has-active", owner_key === el.dataset.parentKey);
		});
		document.querySelectorAll(".cn-group--type2[data-parent-key]").forEach(function (group) {
			const key = group.dataset.parentKey;
			group.querySelectorAll(".cn-child-link[data-nav-key]").forEach(function (el) {
				el.classList.toggle(
					"is-active",
					owner_key === key && key_is_active(el.dataset.navKey),
				);
			});
			const should_exp = key === expanded_key;
			group.classList.toggle("is-expanded", should_exp);
			const h = group.querySelector(".cn-parent-toggle");
			if (h) h.setAttribute("aria-expanded", should_exp ? "true" : "false");
		});
		document
			.querySelectorAll(".cn-group--type1 .cn-child-link[data-nav-key]")
			.forEach(function (el) {
				const pg = el.closest(".cn-group--type1");
				const pk = pg && pg.dataset.parentKey;
				el.classList.toggle(
					"is-active",
					pk === owner_key && key_is_active(el.dataset.navKey),
				);
			});
	}

	// ─── KEYBOARD SHORTCUTS ───────────────────────────────────────────────────
	let _sc_chord_first = null;
	let _sc_chord_timer = null;
	const SC_CHORD_MS = 1000;
	function build_shortcut_map() {
		const map = {};
		function add(shortcut, route) {
			if (shortcut && route) map[shortcut.toLowerCase()] = route;
		}
		SIDEBAR_CONFIG.forEach(function (cfg) {
			if (cfg.parent_type === "type_3" || cfg.parent_type === "type_1")
				add(cfg.shortcut, cfg.route);
			if (cfg.parent_type === "type_2") add(cfg.shortcut, null);
			(cfg.children || []).forEach(function (c) {
				const item = NAV_ITEMS[c.key];
				if (item) add(item.shortcut, item.route);
			});
		});
		return map;
	}
	function register_shortcuts() {
		if (window._csb_key_handler) {
			document.removeEventListener("keydown", window._csb_key_handler, true);
		}
		const map = build_shortcut_map();
		if (!Object.keys(map).length) return;
		const MODS = new Set(["Alt", "Control", "Shift", "Meta", "CapsLock", "Tab"]);
		function handler(e) {
			const tag = (e.target || {}).tagName || "";
			if (["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return;
			if ((e.target || {}).isContentEditable) return;
			if (MODS.has(e.key)) return;
			const raw = e.key.length === 1 ? e.key.toUpperCase() : e.key;
			let candidate = null;
			if (e.altKey) {
				candidate = "alt+" + raw.toLowerCase();
			} else if (e.ctrlKey) {
				candidate = "ctrl+" + raw.toLowerCase();
			} else {
				if (_sc_chord_first) {
					candidate = _sc_chord_first + "+" + raw.toLowerCase();
					clearTimeout(_sc_chord_timer);
					_sc_chord_first = null;
					_sc_chord_timer = null;
				} else {
					const single = raw.toLowerCase();
					if (map[single]) {
						_sc_chord_first = raw.toLowerCase();
						_sc_chord_timer = setTimeout(function () {
							const route = map[_sc_chord_first];
							_sc_chord_first = null;
							_sc_chord_timer = null;
							if (route) {
								e.preventDefault();
								spa_navigate(route);
							}
						}, SC_CHORD_MS);
						return;
					} else {
						_sc_chord_first = raw.toLowerCase();
						_sc_chord_timer = setTimeout(function () {
							_sc_chord_first = null;
							_sc_chord_timer = null;
						}, SC_CHORD_MS);
						return;
					}
				}
			}
			if (candidate && map[candidate]) {
				e.preventDefault();
				spa_navigate(map[candidate]);
			}
		}
		window._csb_key_handler = handler;
		document.addEventListener("keydown", handler, true);
	}

	// ─── CONFIG + PERMISSIONS LOADING ──────────────────────────────────────────
	// localStorage here is a pure UI cache: it only saves us a round-trip to
	// the server API. It is never treated as authoritative, and holding a
	// stale/tampered copy of it changes nothing about actual access control,
	// since every real read/write still goes through Frappe's own permission
	// system server-side.
	function load_from_cache() {
		try {
			const ts = parseInt(localStorage.getItem(cache_ts_key()) || "0", 10);
			const ttl = parseInt(localStorage.getItem(cache_ttl_key()) || "0", 10);
			if (!ttl || Date.now() - ts >= ttl) return null;
			const raw = localStorage.getItem(cache_key());
			if (raw) return JSON.parse(raw);
		} catch (e) {}
		return null;
	}
	function save_to_cache(payload) {
		try {
			localStorage.setItem(cache_key(), JSON.stringify(payload));
			localStorage.setItem(cache_ts_key(), String(Date.now()));
			localStorage.setItem(cache_ttl_key(), String(60 * 60 * 1000)); // 1 hour
		} catch (e) {}
	}
	function clear_cache() {
		try {
			localStorage.removeItem(cache_key());
			localStorage.removeItem(cache_ts_key());
			localStorage.removeItem(cache_ttl_key());
		} catch (e) {}
	}

	function apply_payload(payload) {
		// payload.config is already filtered to exactly what this user can
		// see — no separate permissions object to merge in.
		const config_array = (payload && payload.config) || [];
		SIDEBAR_CONFIG = config_array;
		NAV_ITEMS = {};
		config_array.forEach(function (cfg) {
			if (cfg.parent_type === "type_3") {
				NAV_ITEMS[cfg.key] = {
					name: cfg.label,
					type: cfg.link_type || "doctype",
					route: cfg.route || "/app/" + cfg.key,
					doctype: cfg.doctype || null,
					icon: cfg.icon,
					shortcut: cfg.shortcut || "",
					roles: cfg.roles || [],
					issingle: !!(
						cfg.route && cfg.route.includes("/" + encodeURIComponent(cfg.label))
					),
				};
			}
			(cfg.children || []).forEach(function (c) {
				NAV_ITEMS[c.key] = {
					name: c.name,
					type: c.type || "doctype",
					route: c.route,
					doctype: c.doctype || null,
					icon: c.icon || "icon-setting-gear",
					shortcut: c.shortcut || "",
					roles: c.roles || [],
					issingle: !!(c.route && c.route.includes("/" + encodeURIComponent(c.name))),
				};
			});
		});
	}

	// Single server call: no more per-doctype permission calls from the
	// browser. The server resolves config AND computes the permission map
	// in one whitelisted method, itself backed by frappe.cache() (Redis).
	async function fetch_sidebar_permissions() {
		if (!window.frappe || typeof frappe.call !== "function") return null;
		try {
			const res = await frappe.call({
				method: "verp_staffing.utils.sidebar.get_sidebar_permissions",
			});
			return (res && res.message) || null;
		} catch (e) {
			console.error("Custom Sidebar: failed to load sidebar permissions", e);
			return null;
		}
	}

	async function load_config() {
		const cached = load_from_cache();
		if (cached) {
			apply_payload(cached);
			return;
		}
		const payload = await fetch_sidebar_permissions();
		if (payload) {
			apply_payload(payload);
			save_to_cache(payload);
		} else {
			console.warn("Custom Sidebar: no sidebar permissions returned by server.");
		}
	}

	window.csb_reload = async function () {
		clear_cache();
		await load_config();
		const old = document.getElementById(SIDEBAR_ID);
		if (old) old.remove();
		mount_sidebar();
		register_shortcuts();
	};

	// ─── DEFAULT / HOME ROUTE ─────────────────────────────────────────────────
	function get_first_accessible_route() {
		for (const cfg of SIDEBAR_CONFIG) {
			if (!parent_visible(cfg)) continue;
			if (cfg.parent_type === "type_3" || cfg.parent_type === "type_1") return cfg.route;
			if (cfg.parent_type === "type_2") {
				const kids = visible_children(cfg);
				if (kids.length) {
					const f = NAV_ITEMS[kids[0].key];
					if (f) return f.route;
				}
			}
		}
		return null;
	}
	function resolve_default_route() {
		const path = current_path();
		if (path !== "/app" && path !== "") return;
		const target = get_first_accessible_route();
		if (target) spa_navigate(target);
	}
	function patch_frappe_default_route() {
		if (!window.frappe) return;
		const target = get_first_accessible_route();
		if (target && frappe.boot) frappe.boot.default_route = target.replace(/^\/app\//, "");
		if (typeof frappe.set_route === "function" && !frappe.set_route.__csb_patched) {
			const _orig = frappe.set_route.bind(frappe);
			frappe.set_route = function () {
				const args = Array.prototype.slice.call(arguments);
				const first = args[0];
				const is_home =
					args.length === 0 ||
					first === "" ||
					first === "/" ||
					(typeof first === "string" && first.toLowerCase() === "workspace");
				if (is_home) {
					const r = get_first_accessible_route();
					if (r) return _orig(r.replace(/^\/app\//, ""));
				}
				return _orig.apply(frappe, args);
			};
			frappe.set_route.__csb_patched = true;
		}
		if (
			frappe.router &&
			typeof frappe.router.push === "function" &&
			!frappe.router.push.__csb_patched
		) {
			const _orig_push = frappe.router.push.bind(frappe.router);
			frappe.router.push = function (route) {
				const is_home =
					!route ||
					route === "" ||
					route === "/" ||
					route === "/app" ||
					route === "/app/" ||
					(typeof route === "string" &&
						route.toLowerCase().replace(/^\/app\//, "") === "workspace");
				if (is_home) {
					const t = get_first_accessible_route();
					if (t) return _orig_push(t);
				}
				return _orig_push(route);
			};
			frappe.router.push.__csb_patched = true;
		}
	}
	function patch_logo_click() {
		document.addEventListener(
			"click",
			function (e) {
				const link = e.target.closest(".navbar-home, .navbar-brand");
				if (!link) return;
				const target = get_first_accessible_route();
				if (!target) return;
				e.preventDefault();
				e.stopImmediatePropagation();
				spa_navigate(target);
			},
			true,
		);
	}

	// ─── ROUTE CHANGE ─────────────────────────────────────────────────────────
	function on_route_change() {
		resolve_default_route();
		mount_sidebar();
		refresh_sidebar_active();
	}

	// ─── STYLES ───────────────────────────────────────────────────────────────
	function inject_styles() {
		if (document.getElementById("csb-styles")) return;
		const style = document.createElement("style");
		style.id = "csb-styles";
		style.textContent = `
      /* ── Sidebar item base ── */
      .cn-item.cn-parent-link,
      .cn-item.cn-child-link { position:relative; }

      /* ── Label: truncate with ellipsis so overflow is detectable ── */
      .cn-item-label {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-width: 0;
        flex: 1 1 0%;
      }

      /* ── Quick-create "+" button ── */
      .cn-plus-btn {
        position:absolute; right:6px; top:50%; transform:translateY(-50%);
        width:18px; height:18px; border-radius:50%;
        border:1px solid currentColor; background:transparent;
        display:flex; align-items:center; justify-content:center;
        opacity:0; cursor:pointer; transition:opacity .15s, background .15s;
        color:inherit; flex-shrink:0; padding:0; z-index:2;
      }
      .cn-item:hover .cn-plus-btn { opacity:.65; }
      .cn-plus-btn:hover { opacity:1 !important; background:var(--primary,#5c6bc0); border-color:var(--primary,#5c6bc0); color:#fff; }

      /* ── Unified tooltip (overflow label + optional shortcut) ── */
      #csb-shortcut-tooltip {
        position:fixed; z-index:99999;
        display:none; align-items:center; gap:8px;
        padding:5px 10px; border-radius:6px;
        background:var(--gray-800,#1f2937); color:#fff;
        font-size:12px; font-weight:500; line-height:1.4;
        box-shadow:0 4px 14px rgba(0,0,0,.25);
        pointer-events:none; white-space:nowrap;
        max-width:280px;
      }
      #csb-shortcut-tooltip .csb-tt-label {
        overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        flex:1; min-width:0;
      }
      #csb-shortcut-tooltip .csb-tt-key {
        display:inline-flex; align-items:center;
        padding:2px 7px; border-radius:4px;
        background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.25);
        font-size:11px; font-weight:700; font-family:monospace;
        color:#fff; flex-shrink:0; letter-spacing:.04em;
      }

      /* ── Customize Sidebar button ── */
      .cn-customize-btn {
        margin-top:8px !important;
        border-top:1px solid var(--cn-connector-color, #e5e7eb);
        padding-top:6px !important;
        color:var(--cn-text-muted, #6b7280) !important;
        font-size:12px !important;
      }
      .cn-customize-btn:hover {
        color:var(--cn-primary, #2490ef) !important;
        background:var(--cn-sidebar-hover, #f3f4f6) !important;
      }
      .cn-customize-btn .cn-item-icon svg { opacity:.7; }
      .cn-customize-btn:hover .cn-item-icon svg { opacity:1; }

      /* ── type_2 smooth expand/collapse ── */
      .cn-group--type2 .cn-children {
        max-height:0; overflow:hidden;
        transition:max-height .25s ease;
        list-style:none; margin:0; padding:0;
      }
      .cn-group--type2.is-expanded .cn-children { max-height:1200px; }

      /* ── Chevron rotate ── */
      .cn-parent-toggle .cn-chevron { transition:transform .2s ease; display:inline-flex; }
      .cn-group--type2.is-expanded .cn-parent-toggle .cn-chevron { transform:rotate(180deg); }

      /* ── Keyboard focus ring ── */
      .cn-parent-toggle:focus-visible { outline:2px solid var(--primary,#5c6bc0); outline-offset:-2px; border-radius:4px; }

      /* ── Hide "Toggle Full Width" navbar menu item ── */
      .dropdown-menu li a[onclick*="full_width"],
      .dropdown-menu li:has(> a[onclick*="full_width"]) {
        display:none !important;
      }
    `;
		document.head.appendChild(style);
	}

	// ─── INIT ─────────────────────────────────────────────────────────────────
	async function init() {
		inject_styles();
		await load_config();
		patch_frappe_default_route();
		patch_logo_click();
		resolve_default_route();
		mount_sidebar();
		register_shortcuts();
		if (window.frappe) {
			if (frappe.router && typeof frappe.router.on === "function") {
				frappe.router.on("change", on_route_change);
			}
			$(document).on("page-change frappe:navigate frappe:route-change", on_route_change);
		}
		window.addEventListener("popstate", on_route_change);
		const observer = new MutationObserver(function () {
			const missing = document.querySelector(
				".layout-side-section:not(:has(#" + SIDEBAR_ID + "))",
			);
			if (missing) mount_sidebar();
		});
		observer.observe(document.body, { childList: true, subtree: true });
	}

	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(init);
	} else if (document.readyState === "complete" || document.readyState === "interactive") {
		init();
	} else {
		document.addEventListener("DOMContentLoaded", init);
	}
})();