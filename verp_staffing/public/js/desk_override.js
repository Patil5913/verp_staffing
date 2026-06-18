// Config-driven global navigation for Frappe.
//
// THREE PARENT TYPES:
//   type_1 — redirect + navbar children
//   type_2 — dropdown (no redirect) + per-child navbar context
//   type_3 — single link, no children, no navbar
//
// VISIBILITY RULES:
//   Administrator: skip ALL role and permission checks — sees everything
//   Others — Parent: user must have module role; Child doctype: can_read(); Child report: free

(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════════
  // SECTION 1 — CONFIGURATION
  // ═══════════════════════════════════════════════════════════

  // icon: Frappe SVG sprite id (e.g. "icon-employee" → <use href="#icon-employee">)
  const NAV_ITEMS = {
    "role": {
      name: "Role",
      type: "doctype",
      route: "/app/role",
      doctype: "Role",
      icon: "icon-quantity-1"
    },
    "permission-manager": {
      name: "Permission Manager",
      type: "report",
      route: "/app/permission-manager",
      icon: "icon-quantity-1"
    },
    "employee": {
      name: "Employee",
      type: "doctype",
      route: "/app/employee",
      doctype: "Employee",
      icon: "icon-customer"
    },
    "department": {
      name: "Department",
      type: "doctype",
      route: "/app/department",
      doctype: "Department",
      icon: "icon-tag"
    },
    "hierarchy": {
      name: "Hierarchy",
      type: "doctype",
      route: "/app/hierarchy",
      doctype: "Hierarchy",
      icon: "icon-sort-ascending"
    },
    "erp-configuration": {
      name: "ERP Settings",
      type: "doctype",
      route: "/app/erp-configuration/ERP Configuration",
      doctype: "ERP Configuration",
      icon: "icon-setting-gear"
    },
    "email-domain": {
      name: "Email domain",
      type: "doctype",
      route: "/app/email-domain",
      doctype: "Email Domain",
      icon: "icon-mail"
    },
    "email-account": {
      name: "Email Account",
      type: "doctype",
      route: "/app/email-account",
      doctype: "Email Account",
      icon: "icon-mail"
    },
    "pdf-agreement-template": {
      name: "Pdf Agreement Template",
      type: "doctype",
      route: "/app/pdf-agreement-template",
      doctype: "Pdf Agreement Template",
      icon: "icon-pen"
    },
    "resume": {
      name: "Resume",
      type: "doctype",
      route: "/app/resume",
      doctype: "Resume",
      icon: "icon-small-file"
    },
    "ruc": {
      name: "RUC",
      type: "doctype",
      route: "/app/ruc",
      doctype: "RUC",
      icon: "icon-support"
    },
    "jdc": {
      name: "JDC",
      type: "doctype",
      route: "/app/jdc",
      doctype: "JDC",
      icon: "icon-support"
    },
    "training": {
      name: "Training",
      type: "doctype",
      route: "/app/training",
      doctype: "Training",
      icon: "icon-getting-started"
    },
    "cover-letter": {
      name: "Cover Letter",
      type: "doctype",
      route: "/app/cover-letter",
      doctype: "Cover Letter",
      icon: "icon-folder-open"
    },
    "technical-other-services": {
      name: "Tech Other Services",
      type: "doctype",
      route: "/app/technical-other-services",
      doctype: "Technical Other Services",
      icon: "icon-tool"
    },
    "interview": {
      name: "Interview",
      type: "doctype",
      route: "/app/interview",
      doctype: "Interview",
      icon: "icon-list-alt"
    },
    "marketing-other-services": {
      name: "Marketing Other Services",
      type: "doctype",
      route: "/app/marketing-other-services",
      icon: "icon-milestone"
    },
    "report": {
      name: "Reports",
      type: "report",
      route: "/app/report",
      icon: "icon-file"
    },
    "opportunity": {
      name: "Opportunity",
      type: "doctype",
      route: "/app/opportunity",
      doctype: "Opportunity",
      icon: "icon-assign"
    },
    "customer": {
      name: "Customer",
      type: "doctype",
      route: "/app/customer",
      doctype: "Customer",
      icon: "icon-customer"
    },
    "company": {
      name: "Company",
      type: "doctype",
      route: "/app/company",
      doctype: "Company",
      icon: "icon-organization"
    },
    "fiscal-year": {
      name: "Fiscal Year",
      type: "doctype",
      route: "/app/fiscal-year",
      doctype: "Fiscal Year",
      icon: "icon-calendar"
    },
    "accounts-settings": {
      name: "Accounts Settings",
      type: "doctype",
      route: "/app/accounts-settings/Accounts Settings",
      doctype: "Accounts Settings",
      icon: "icon-setting-gear"
    },
    "bank-account": {
      name: "Bank Account",
      type: "doctype",
      route: "/app/bank-account",
      doctype: "Bank Account",
      icon: "icon-number-card"
    },
    "sales-order": {
      name: "Sales Order",
      type: "doctype",
      route: "/app/sales-order",
      doctype: "Sales Order",
      icon: "icon-stock"
    },
    "sales-invoice": {
      name: "Sales Invoice",
      type: "doctype",
      route: "/app/sales-invoice",
      doctype: "Sales Invoice",
      icon: "icon-expenses"
    },
    "purchase-order": {
      name: "Purchase Order",
      type: "doctype",
      route: "/app/purchase-order",
      doctype: "Purchase Order",
      icon: "icon-stock"
    },
    "purchase-invoice": {
      name: "Purchase Invoice",
      type: "doctype",
      route: "/app/purchase-invoice",
      doctype: "Purchase Invoice",
      icon: "icon-expenses"
    },
    "journal-entry": {
      name: "Journal Entry",
      type: "doctype",
      route: "/app/journal-entry",
      doctype: "Journal Entry",
      icon: "icon-money-coins-1"
    },
    "payment-entry": {
      name: "Payment Entry",
      type: "doctype",
      route: "/app/payment-entry",
      doctype: "Payment Entry",
      icon: "icon-money-coins-1"
    },
    "supplier": {
      name: "Supplier",
      type: "doctype",
      route: "/app/supplier",
      doctype: "Supplier",
      icon: "icon-share"
    },
    "subscription": {
      name: "Subscription",
      type: "doctype",
      route: "/app/subscription",
      doctype: "Subscription",
      icon: "icon-money-coins-1"
    },
    "subscription-plan": {
      name: "Subscription Plan",
      type: "doctype",
      route: "/app/subscription-plan",
      doctype: "Subscription Plan",
      icon: "icon-money-coins-1"
    },
  };

  // icon: Frappe SVG sprite id for the parent module header
  const SIDEBAR_CONFIG = [
    {
      key: "setup",
      label: "Setup Guide",
      parent_type: "type_3",
      route: "/app/setup",
      role: "_show_setup",
      icon: "icon-setting-gear"
    },
    {
      key: "staffing-master",
      label: "Staffing Master",
      parent_type: "type_2",
      role: "_show_staffing_master",
      icon: "icon-keyboard",
      children: ["department", "hierarchy", "erp-configuration", "email-domain", "email-account", "pdf-agreement-template"]
    },
    {
      key: "item",
      label: "Item",
      parent_type: "type_3",
      route: "/app/item",
      role: "_show_item",
      icon: "icon-stock"
    },
    {
      key: "user",
      label: "User",
      parent_type: "type_1",
      route: "/app/user",
      role: "_show_employees",
      icon: "icon-users",
      children: ["role", "permission-manager"]
    },
    {
      key: "employee",
      label: "Employee",
      parent_type: "type_1",
      route: "/app/employee",
      role: "_show_employees",
      icon: "icon-users",
      children: ["department", "hierarchy"]
    },
    {
      key: "lead",
      label: "Lead",
      parent_type: "type_3",
      route: "/app/lead",
      role: "_show_lead",
      icon: "icon-share"
    },
    {
      key: "sales",
      label: "Sales",
      parent_type: "type_2",
      role: "_show_sales",
      icon: "icon-call",
      children: ["opportunity", "customer", "sales-order"]
    },
    {
      key: "technical",
      label: "Technical",
      parent_type: "type_2",
      role: "_show_technical",
      icon: "icon-website",
      children: ["resume", "jdc", "ruc", "training", "cover-letter", "technical-other-services"]
    },
    {
      key: "marketing",
      label: "Marketing",
      parent_type: "type_1",
      route: "/app/marketing",
      role: "_show_marketing",
      icon: "icon-users",
      children: ["interview", "marketing-other-services", "report"]
    },
    {
      key: "other-services",
      label: "Other Services",
      parent_type: "type_3",
      route: "/app/other-services",
      role: "_show_other_service",
      icon: "icon-setting-gear"
    },
    {
      key: "onboardings",
      label: "Onboarding",
      parent_type: "type_3",
      route: "/app/onboardings",
      role: "_show_onboarding",
      icon: "icon-branch"
    },
    {
      key: "cr",
      label: "CR",
      parent_type: "type_3",
      route: "/app/cr",
      role: "_show_cr",
      icon: "icon-assign"
    },
    {
      key: "email-inbox",
      label: "Email Inbox",
      parent_type: "type_3",
      route: "/app/email-inbox",
      role: "_show_email_inbox",
      icon: "icon-mail"
    },
    {
      key: "e-sign",
      label: "E Sign",
      parent_type: "type_3",
      route: "/app/e-sign",
      role: "_show_e_sign",
      icon: "icon-pen"
    },

    {
      key: "account-master",
      label: "Accounts Master",
      parent_type: "type_2",
      role: "_show_account_master",
      icon: "icon-keyboard",
      children: ["company", "fiscal-year", "accounts-settings", "bank-account"]
    },
    {
      key: "coa",
      label: "Charts of accounts",
      parent_type: "type_3",
      route: "/app/account/view/tree",
      role: "_show_coa",
      icon: "icon-stock"
    },
    {
      key: "pe_request",
      label: "Pending PE Request",
      parent_type: "type_3",
      route: "/app/pending-pe-request",
      role: "_show_pe_request",
      icon: "icon-expenses"
    },
    {
      key: "accounting",
      label: "Accounting",
      parent_type: "type_2",
      role: "_show_accounting",
      icon: "icon-accounting",
      children: [
        "sales-order",
        "sales-invoice",
        "purchase-order",
        "purchase-invoice",
        "journal-entry",
        "payment-entry",
        "supplier",
        "subscription",
        "report",
      ]
    }
  ];

  const NAVBAR_CONTEXT = {
    "department": ["hierarchy", "employee"],
    "hierarchy": ["department", "employee"],

    "resume": ["jdc", "ruc", "training", "cover-letter", "technical-other-services"],
    "jdc": ["resume", "ruc", "training", "cover-letter", "technical-other-services"],
    "ruc": ["resume", "jdc", "training", "cover-letter", "technical-other-services"],
    "training": ["resume", "jdc", "ruc", "cover-letter", "technical-other-services"],
    "cover-letter": ["resume", "jdc", "ruc", "training", "technical-other-services"],
    "technical-other-services": ["resume", "jdc", "ruc", "training", "cover-letter"],

    "opportunity": ["customer", "sales-order"],
    "customer": ["opportunity", , "sales-order"],

    "company": ["fiscal-year"],
    "fiscal-year": ["company"],

    "sales-order":       ["customer", "sales-invoice", "journal-entry", "payment-entry"],
    "sales-invoice":     ["sales-order", "journal-entry", "payment-entry"],
    "purchase-order":    ["purchase-invoice", "journal-entry", "payment-entry"],
    "purchase-invoice":  ["purchase-order", "journal-entry", "payment-entry"],
    "journal-entry":     ["sales-order", "sales-invoice", "purchase-order", "purchase-invoice", "payment-entry"],
    "payment-entry":     ["sales-order", "sales-invoice", "purchase-order", "purchase-invoice", "journal-entry"],
    "subscription": ["subscription-plan"],
  };

  // ═══════════════════════════════════════════════════════════
  // SECTION 2 — PERMISSION & ROLE HELPERS
  // ═══════════════════════════════════════════════════════════

  // Returns true if current user is Administrator — skip all checks.
  function is_administrator() {
    if (!window.frappe) return false;
    return (
      frappe.session && frappe.session.user === "Administrator"
    ) || (
      frappe.user_roles && frappe.user_roles.includes("Administrator")
    );
  }

  function user_has_role(role) {
    if (is_administrator()) return true;
    if (!window.frappe || !frappe.user_roles) return false;
    return frappe.user_roles.includes(role);
  }

  function can_read(doctype) {
    if (is_administrator()) return true;
    if (!window.frappe) return false;
    try {
      return !!frappe.model.can_read(doctype);
    } catch (e) {
      return false;
    }
  }

  function item_accessible(key) {
    if (is_administrator()) return true;
    const item = NAV_ITEMS[key];
    if (!item) return false;
    if (item.type === "doctype") return can_read(item.doctype);
    return true;
  }

  function visible_children(parent_cfg) {
    if (!parent_cfg.children) return [];
    return parent_cfg.children.filter(item_accessible);
  }

  function parent_visible(parent_cfg) {
    if (!user_has_role(parent_cfg.role)) return false;
    if (parent_cfg.parent_type === "type_3") return item_accessible(parent_cfg.key);
    return visible_children(parent_cfg).length > 0;
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 3 — ROUTE HELPERS
  // ═══════════════════════════════════════════════════════════

  // Decoded so config routes written with literal characters (e.g. a
  // single-doctype route containing a space, "ERP Configuration") still
  // match the browser's pathname, which encodes spaces as %20.
  function current_path() {
    let path = window.location.pathname;
    try {
      path = decodeURIComponent(path);
    } catch (e) {
      // malformed sequence — fall back to the raw pathname
    }
    return path.replace(/\/+$/, "");
  }

  function current_slug() {
    const m = current_path().match(/^\/app\/([^/]+)/);
    return m ? m[1] : null;
  }

  function key_is_active(key) {
    const item = NAV_ITEMS[key];
    if (!item) return false;
    const route = item.route.replace(/\/+$/, "");
    const path  = current_path();
    return path === route || path.startsWith(route + "/");
  }

  function parent_route_is_active(parent_cfg) {
    if (!parent_cfg.route) return false;
    const route = parent_cfg.route.replace(/\/+$/, "");
    const path  = current_path();
    return path === route || path.startsWith(route + "/");
  }

  // Some NAV_ITEMS (e.g. "department") are referenced as a child from
  // more than one SIDEBAR_CONFIG entry — once as a real sidebar dropdown
  // child (Staffing Master), once purely so a type_1 parent can offer it
  // as navbar context (Employee). Only ONE entry should ever show the
  // "active" treatment for a given route. The first entry in declared
  // order that matches wins — this mirrors the precedence already used
  // by resolve_navbar_keys(), so sidebar and navbar agree on ownership.
  function get_active_owner_key() {
    for (const cfg of SIDEBAR_CONFIG) {
      if (!parent_visible(cfg)) continue;

      if (cfg.parent_type === "type_3") {
        if (parent_route_is_active(cfg)) return cfg.key;
      } else if (cfg.parent_type === "type_1") {
        if (parent_route_is_active(cfg) || (cfg.children && cfg.children.some(key_is_active))) {
          return cfg.key;
        }
      } else if (cfg.parent_type === "type_2") {
        if (cfg.children && cfg.children.some(key_is_active)) return cfg.key;
      }
    }
    return null;
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 4 — EXPAND / COLLAPSE PERSISTENCE (single, exclusive)
  // ═══════════════════════════════════════════════════════════
  //
  // Only one type_2 dropdown is ever open at a time. The dropdown that
  // contains the active route always wins; otherwise we fall back to
  // whichever dropdown the user last opened manually.

  const STORAGE_KEY = "custom_nav_expanded_module";

  function load_expanded_key() {
    try { return localStorage.getItem(STORAGE_KEY) || null; }
    catch (e) { return null; }
  }

  function save_expanded_key(key) {
    try {
      if (key) localStorage.setItem(STORAGE_KEY, key);
      else localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  function route_forced_expand_key() {
    for (const cfg of SIDEBAR_CONFIG) {
      if (cfg.parent_type === "type_2" && cfg.children && cfg.children.some(key_is_active)) {
        return cfg.key;
      }
    }
    return null;
  }

  function compute_expanded_key() {
    return route_forced_expand_key() || load_expanded_key();
  }

  function should_expand(parent_cfg) {
    if (parent_cfg.parent_type !== "type_2") return false;
    return compute_expanded_key() === parent_cfg.key;
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 5 — NAVBAR LOGIC
  // ═══════════════════════════════════════════════════════════

  function resolve_navbar_keys() {
    for (const cfg of SIDEBAR_CONFIG) {
      if (!parent_visible(cfg)) continue;

      if (cfg.parent_type === "type_1") {
        if (parent_route_is_active(cfg) || (cfg.children && cfg.children.some(key_is_active))) {
          return visible_children(cfg);
        }
      }

      if (cfg.parent_type === "type_2") {
        if (cfg.children && cfg.children.some(key_is_active)) {
          const active = cfg.children.find(key_is_active);
          const context_keys = (active && NAVBAR_CONTEXT[active]) || [];
          return context_keys.filter(item_accessible);
        }
      }
    }
    return [];
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 6 — SIDEBAR DOM RENDERING
  // ═══════════════════════════════════════════════════════════

  const SIDEBAR_ID = "custom-nav-sidebar";

  // Build a Frappe SVG icon element (uses Frappe's sprite system)
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

  function build_sidebar_dom() {
    const wrap = document.createElement("div");
    wrap.id = SIDEBAR_ID;
    wrap.className = "custom-nav-sidebar";

    SIDEBAR_CONFIG.forEach(function (cfg) {
      if (!parent_visible(cfg)) return;
      if (cfg.parent_type === "type_3") { wrap.appendChild(make_type3_el(cfg)); return; }
      if (cfg.parent_type === "type_1") { wrap.appendChild(make_type1_el(cfg)); return; }
      if (cfg.parent_type === "type_2") { wrap.appendChild(make_type2_el(cfg)); return; }
    });

    return wrap;
  }

  // Helper: build the inner icon+label structure for any item row
  function make_item_inner(icon_id, label_text) {
    const icon_wrap = document.createElement("span");
    icon_wrap.className = "cn-item-icon";
    if (icon_id) icon_wrap.appendChild(make_icon(icon_id, "sm"));

    const label = document.createElement("span");
    label.className = "cn-item-label";
    label.textContent = label_text;

    return [icon_wrap, label];
  }

  // ── Type 3: single link ─────────────────────────────────
  function make_type3_el(cfg) {
    const a = document.createElement("a");
    a.className = "cn-item cn-parent-link" + (parent_route_is_active(cfg) ? " is-active" : "");
    a.href = cfg.route;
    a.dataset.parentKey = cfg.key;
    a.dataset.parentType = "type_3";

    make_item_inner(cfg.icon, cfg.label).forEach(function (el) { a.appendChild(el); });

    a.addEventListener("click", function (e) {
      e.preventDefault();
      spa_navigate(cfg.route);
    });
    return a;
  }

  // ── Type 1: redirect parent (no chevron, no children in sidebar) ─
  function make_type1_el(cfg) {
    const active_on_parent = parent_route_is_active(cfg);
    const is_owner = get_active_owner_key() === cfg.key;

    const wrap = document.createElement("div");
    wrap.className = "cn-group cn-group--type1" + (is_owner ? " has-active" : "");
    wrap.dataset.parentKey = cfg.key;

    const a = document.createElement("a");
    a.className = "cn-item cn-parent-link" + (active_on_parent ? " is-active" : "");
    a.href = cfg.route;
    a.dataset.parentKey = cfg.key;
    a.dataset.parentType = "type_1";

    make_item_inner(cfg.icon, cfg.label).forEach(function (el) { a.appendChild(el); });

    a.addEventListener("click", function (e) {
      e.preventDefault();
      spa_navigate(cfg.route);
    });

    wrap.appendChild(a);
    return wrap;
  }

  // ── Type 2: dropdown parent + children in sidebar ───────
  function make_type2_el(cfg) {
    const expanded = should_expand(cfg);
    const is_owner = get_active_owner_key() === cfg.key;
    const kids     = visible_children(cfg);

    const wrap = document.createElement("div");
    wrap.className = "cn-group cn-group--type2" + (expanded ? " is-expanded" : "");
    wrap.dataset.parentKey = cfg.key;

    // Toggle header
    const header = document.createElement("div");
    header.className = "cn-item cn-parent-toggle";
    header.dataset.parentKey = cfg.key;

    make_item_inner(cfg.icon, cfg.label).forEach(function (el) { header.appendChild(el); });

    // Chevron
    const chevron = document.createElement("span");
    chevron.className = "cn-chevron";
    chevron.innerHTML =
      '<svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
      + '<polyline points="4,6 8,10 12,6"/></svg>';
    header.appendChild(chevron);

    header.addEventListener("click", function (e) {
      e.stopPropagation();
      const is_open = wrap.classList.contains("is-expanded");

      // Accordion: at most one dropdown stays open. Collapse every
      // other type_2 group before opening/toggling this one.
      document.querySelectorAll(".cn-group--type2").forEach(function (other) {
        if (other !== wrap) other.classList.remove("is-expanded");
      });

      wrap.classList.toggle("is-expanded", !is_open);
      save_expanded_key(!is_open ? cfg.key : null);
    });

    wrap.appendChild(header);

    // Children list
    const ul = document.createElement("ul");
    ul.className = "cn-children";

    kids.forEach(function (child_key) {
      const item = NAV_ITEMS[child_key];
      if (!item) return;
      const li = document.createElement("li");
      const a  = document.createElement("a");
      a.className = "cn-item cn-child-link" + (is_owner && key_is_active(child_key) ? " is-active" : "");
      a.href = item.route;
      a.dataset.navKey = child_key;

      make_item_inner(item.icon, item.name).forEach(function (el) { a.appendChild(el); });

      a.addEventListener("click", function (e) {
        e.preventDefault();
        spa_navigate(item.route);
      });
      li.appendChild(a);
      ul.appendChild(li);
    });

    wrap.appendChild(ul);
    return wrap;
  }

  function mount_sidebar() {
    document.querySelectorAll(".layout-side-section").forEach(function (section) {
      if (section.querySelector("#" + SIDEBAR_ID)) return;
      section.appendChild(build_sidebar_dom());
    });
  }

  function refresh_sidebar_active() {
    const owner_key    = get_active_owner_key();
    const expanded_key = compute_expanded_key();

    // Parent links (type_1 own route, type_3) — exact-route match only.
    document.querySelectorAll(".cn-parent-link[data-parent-key]").forEach(function (el) {
      const cfg = SIDEBAR_CONFIG.find(c => c.key === el.dataset.parentKey);
      if (!cfg) return;
      el.classList.toggle("is-active", parent_route_is_active(cfg));
    });

    // has-active on type_1 groups — only the single resolved owner lights
    // up, even when another parent happens to list the same child route.
    document.querySelectorAll(".cn-group--type1[data-parent-key]").forEach(function (el) {
      el.classList.toggle("has-active", owner_key === el.dataset.parentKey);
    });

    // type_2 groups: child highlight (owner-gated) + exclusive expand state.
    document.querySelectorAll(".cn-group--type2[data-parent-key]").forEach(function (group) {
      const key      = group.dataset.parentKey;
      const is_owner = owner_key === key;

      group.querySelectorAll(".cn-child-link[data-nav-key]").forEach(function (el) {
        el.classList.toggle("is-active", is_owner && key_is_active(el.dataset.navKey));
      });

      group.classList.toggle("is-expanded", key === expanded_key);
    });
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 7 — NAVBAR DOM RENDERING
  // ═══════════════════════════════════════════════════════════

  const NAVBAR_ID = "custom-nav-navbar";

  // Navbar structure from actual Frappe HTML:
  //   header.navbar > div.container >
  //     a.navbar-brand
  //     ul#navbar-breadcrumbs            ← left of search
  //     div.collapse.navbar-collapse >
  //       form.form-inline (search)
  //       ul.navbar-nav    (icons)
  //
  // To center the navbar links we use absolute positioning on our bar
  // so it sits centered in the full .navbar width regardless of breadcrumb length.
  function mount_navbar() {
    const existing = document.getElementById(NAVBAR_ID);
    if (existing && document.body.contains(existing)) return;

    const bar = document.createElement("div");
    bar.id = NAVBAR_ID;
    bar.className = "custom-nav-navbar";

    // Append to header.navbar directly (not inside .container) so we can
    // use position:absolute to center across the full header width.
    const navbar_header = document.querySelector("header.navbar");
    if (navbar_header) {
      navbar_header.appendChild(bar);
      return;
    }

    // Fallback
    const collapse = document.querySelector("header.navbar .container .collapse.navbar-collapse");
    if (collapse) {
      const nav_ul = collapse.querySelector("ul.navbar-nav");
      nav_ul ? collapse.insertBefore(bar, nav_ul) : collapse.appendChild(bar);
    }
  }

  function render_navbar() {
    const bar = document.getElementById(NAVBAR_ID);
    if (!bar) return;

    const keys = resolve_navbar_keys();
    bar.innerHTML = "";

    if (!keys.length) {
      bar.classList.add("is-empty");
      return;
    }

    bar.classList.remove("is-empty");

    keys.forEach(function (key) {
      const item = NAV_ITEMS[key];
      if (!item) return;

      const a = document.createElement("a");
      a.className = "cn-navbar-link" + (key_is_active(key) ? " is-active" : "");
      a.href = item.route;
      a.dataset.navKey = key;

      // Icon + label so a quick link reads as "go to X", not a plain tag.
      if (item.icon) {
        const icon_wrap = document.createElement("span");
        icon_wrap.className = "cn-navbar-link-icon";
        icon_wrap.appendChild(make_icon(item.icon, "xs"));
        a.appendChild(icon_wrap);
      }

      const label = document.createElement("span");
      label.className = "cn-navbar-link-label";
      label.textContent = item.name;
      a.appendChild(label);

      a.addEventListener("click", function (e) {
        e.preventDefault();
        spa_navigate(item.route);
      });

      bar.appendChild(a);
    });
  }

  function refresh_navbar_active() {
    const bar = document.getElementById(NAVBAR_ID);
    if (!bar) return;

    const keys     = resolve_navbar_keys();
    const cur_keys = Array.from(bar.querySelectorAll(".cn-navbar-link")).map(a => a.dataset.navKey);

    if (keys.join(",") !== cur_keys.join(",")) {
      render_navbar();
      return;
    }

    bar.querySelectorAll(".cn-navbar-link").forEach(function (a) {
      a.classList.toggle("is-active", key_is_active(a.dataset.navKey));
    });
    bar.classList.toggle("is-empty", keys.length === 0);
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 8 — SPA NAVIGATION
  // ═══════════════════════════════════════════════════════════

  function spa_navigate(route) {
    if (window.frappe && frappe.set_route) {
      frappe.set_route(route.replace(/^\/app\//, ""));
    } else {
      window.location.href = route;
    }
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 9 — DEFAULT ROUTE (role-aware landing page)
  // ═══════════════════════════════════════════════════════════
  //
  // THREE escape hatches Frappe uses that bypass our route listener:
  //
  //  1. Logo click  → frappe.set_route("") → workspace
  //  2. Post-login  → frappe.boot.default_route or "" → workspace
  //  3. frappe.app.redirect_to_login_with_hash() on session boot
  //
  // FIX STRATEGY:
  //  A. get_first_accessible_route() — pure helper, no side-effects.
  //     Walks SIDEBAR_CONFIG and returns the first route the user
  //     can access. Returns null if nothing found.
  //
  //  B. resolve_default_route() — called on every route change.
  //     If current path is /app or empty, immediately redirects.
  //
  //  C. patch_frappe_default_route() — called once at init.
  //     Overrides frappe.boot.default_route and wraps
  //     frappe.set_route so calls with "" or "workspace" are
  //     intercepted before Frappe acts on them.
  //
  //  D. Logo click interception — delegated click listener on
  //     header.navbar that catches clicks on .navbar-home/.navbar-brand
  //     before Frappe's own handler.
  // ─────────────────────────────────────────────────────────────

  // Returns the first route the current user can access, or null.
  function get_first_accessible_route() {
    for (const cfg of SIDEBAR_CONFIG) {
      if (!parent_visible(cfg)) continue;

      if (cfg.parent_type === "type_3" || cfg.parent_type === "type_1") {
        return cfg.route;
      }

      if (cfg.parent_type === "type_2") {
        const kids = visible_children(cfg);
        if (kids.length) {
          const first_item = NAV_ITEMS[kids[0]];
          if (first_item) return first_item.route;
        }
      }
    }
    return null;
  }

  // Redirect away from bare /app if we have a better target.
  function resolve_default_route() {
    const path = current_path();
    // Only act on exactly /app or bare "" (hash-router empty state)
    if (path !== "/app" && path !== "") return;

    const target = get_first_accessible_route();
    if (target) spa_navigate(target);
  }

  // ── Patch Frappe internals so they never land on workspace ──
  // Called once during init(), after frappe is ready.
  function patch_frappe_default_route() {
    if (!window.frappe) return;

    // A) Override boot default_route so post-login redirect goes to our route
    const target = get_first_accessible_route();
    if (target) {
      // Frappe reads frappe.boot.default_route on startup to decide
      // where to land after login. Override it with our target.
      if (frappe.boot) {
        frappe.boot.default_route = target.replace(/^\/app\//, "");
      }
    }

    // B) Wrap frappe.set_route to intercept calls with "" or "workspace"
    //    (logo click, breadcrumb home, programmatic redirects).
    if (typeof frappe.set_route === "function" && !frappe.set_route.__cn_patched) {
      const _original_set_route = frappe.set_route.bind(frappe);

      frappe.set_route = function () {
        const args = Array.prototype.slice.call(arguments);
        const first = args[0];

        // Intercept bare home calls: "", "workspace", "/", or no args
        const is_home = (
          args.length === 0 ||
          first === "" ||
          first === "/" ||
          (typeof first === "string" && first.toLowerCase() === "workspace")
        );

        if (is_home) {
          const route = get_first_accessible_route();
          if (route) {
            // Call original with our target instead
            return _original_set_route(route.replace(/^\/app\//, ""));
          }
        }

        // Everything else passes through unchanged
        return _original_set_route.apply(frappe, args);
      };

      frappe.set_route.__cn_patched = true;
    }

    // C) Also patch frappe.router.push if it exists (Frappe v15+)
    if (frappe.router && typeof frappe.router.push === "function" && !frappe.router.push.__cn_patched) {
      const _original_push = frappe.router.push.bind(frappe.router);

      frappe.router.push = function (route) {
        const is_home = (
          !route ||
          route === "" ||
          route === "/" ||
          route === "/app" ||
          route === "/app/" ||
          (typeof route === "string" && route.toLowerCase().replace(/^\/app\//, "") === "workspace")
        );

        if (is_home) {
          const target = get_first_accessible_route();
          if (target) return _original_push(target);
        }

        return _original_push(route);
      };

      frappe.router.push.__cn_patched = true;
    }
  }

  // ── Logo / home link click interception ──
  // Frappe's logo <a class="navbar-home"> has its own click handler
  // that calls frappe.set_route(""). We intercept at the DOM level
  // with capture:true so we run before Frappe's listener.
  function patch_logo_click() {
    document.addEventListener("click", function (e) {
      const link = e.target.closest(".navbar-home, .navbar-brand");
      if (!link) return;

      const target = get_first_accessible_route();
      if (!target) return;

      // Stop Frappe's own listener from also firing
      e.preventDefault();
      e.stopImmediatePropagation();

      spa_navigate(target);
    }, true /* capture — runs before Frappe's bubble-phase handler */);
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 10 — ROUTE CHANGE HANDLER
  // ═══════════════════════════════════════════════════════════

  function on_route_change() {
    // Override default /app landing before doing anything else
    resolve_default_route();
    mount_sidebar();
    refresh_sidebar_active();
    mount_navbar();
    refresh_navbar_active();
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 10 — INIT
  // ═══════════════════════════════════════════════════════════

  function init() {
    // 1. Patch Frappe internals FIRST — before any navigation fires
    patch_frappe_default_route();

    // 2. Intercept logo/brand clicks at capture phase
    patch_logo_click();

    // 3. Redirect away from bare /app on this load
    resolve_default_route();

    mount_sidebar();
    mount_navbar();
    render_navbar();

    if (window.frappe) {
      if (frappe.router && typeof frappe.router.on === "function") {
        frappe.router.on("change", on_route_change);
      }
      $(document).on("page-change frappe:navigate frappe:route-change", on_route_change);
    }

    window.addEventListener("popstate", on_route_change);

    const observer = new MutationObserver(function () {
      const missing = document.querySelector(
        ".layout-side-section:not(:has(#" + SIDEBAR_ID + "))"
      );
      if (missing) mount_sidebar();

      // Re-mount navbar if Frappe destroyed it
      const nav_missing = !document.getElementById(NAVBAR_ID)
        || !document.body.contains(document.getElementById(NAVBAR_ID));
      if (nav_missing) { mount_navbar(); render_navbar(); }
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