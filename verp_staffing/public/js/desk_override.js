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

  // ═══════════════════════════════════════════════════════════
  // SECTION 2 — PERMISSION & ROLE HELPERS
  // ═══════════════════════════════════════════════════════════

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

  function current_path() {
    let path = window.location.pathname;
    try {
      path = decodeURIComponent(path);
    } catch (e) {}
    return path.replace(/\/+$/, "");
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
  // SECTION 5 — SIDEBAR DOM RENDERING
  // ═══════════════════════════════════════════════════════════

  const SIDEBAR_ID = "custom-nav-sidebar";

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

  function make_item_inner(icon_id, label_text) {
    const icon_wrap = document.createElement("span");
    icon_wrap.className = "cn-item-icon";
    if (icon_id) icon_wrap.appendChild(make_icon(icon_id, "sm"));

    const label = document.createElement("span");
    label.className = "cn-item-label";
    label.textContent = label_text;

    return [icon_wrap, label];
  }

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

  function make_type1_el(cfg) {
    const is_owner = get_active_owner_key() === cfg.key;

    const wrap = document.createElement("div");
    wrap.className = "cn-group cn-group--type1" + (is_owner ? " has-active" : "");
    wrap.dataset.parentKey = cfg.key;

    const a = document.createElement("a");
    a.className = "cn-item cn-parent-link" + (parent_route_is_active(cfg) ? " is-active" : "");
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

  function make_type2_el(cfg) {
    const expanded = should_expand(cfg);
    const is_owner = get_active_owner_key() === cfg.key;
    const kids     = visible_children(cfg);

    const wrap = document.createElement("div");
    wrap.className = "cn-group cn-group--type2" + (expanded ? " is-expanded" : "");
    wrap.dataset.parentKey = cfg.key;

    const header = document.createElement("div");
    header.className = "cn-item cn-parent-toggle";
    header.dataset.parentKey = cfg.key;

    make_item_inner(cfg.icon, cfg.label).forEach(function (el) { header.appendChild(el); });

    const chevron = document.createElement("span");
    chevron.className = "cn-chevron";
    chevron.innerHTML =
      '<svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
      + '<polyline points="4,6 8,10 12,6"/></svg>';
    header.appendChild(chevron);

    header.addEventListener("click", function (e) {
      e.stopPropagation();
      const is_open = wrap.classList.contains("is-expanded");

      document.querySelectorAll(".cn-group--type2").forEach(function (other) {
        if (other !== wrap) other.classList.remove("is-expanded");
      });

      wrap.classList.toggle("is-expanded", !is_open);
      save_expanded_key(!is_open ? cfg.key : null);
    });

    wrap.appendChild(header);

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

    document.querySelectorAll(".cn-parent-link[data-parent-key]").forEach(function (el) {
      const cfg = SIDEBAR_CONFIG.find(c => c.key === el.dataset.parentKey);
      if (!cfg) return;
      el.classList.toggle("is-active", parent_route_is_active(cfg));
    });

    document.querySelectorAll(".cn-group--type1[data-parent-key]").forEach(function (el) {
      el.classList.toggle("has-active", owner_key === el.dataset.parentKey);
    });

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
  // SECTION 6 — SPA NAVIGATION
  // ═══════════════════════════════════════════════════════════

  function spa_navigate(route) {
    if (window.frappe && frappe.set_route) {
      frappe.set_route(route.replace(/^\/app\//, ""));
    } else {
      window.location.href = route;
    }
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 7 — DEFAULT ROUTE (role-aware landing page)
  // ═══════════════════════════════════════════════════════════

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

  function resolve_default_route() {
    const path = current_path();
    if (path !== "/app" && path !== "") return;
    const target = get_first_accessible_route();
    if (target) spa_navigate(target);
  }

  function patch_frappe_default_route() {
    if (!window.frappe) return;

    const target = get_first_accessible_route();
    if (target && frappe.boot) {
      frappe.boot.default_route = target.replace(/^\/app\//, "");
    }

    if (typeof frappe.set_route === "function" && !frappe.set_route.__cn_patched) {
      const _original_set_route = frappe.set_route.bind(frappe);

      frappe.set_route = function () {
        const args = Array.prototype.slice.call(arguments);
        const first = args[0];

        const is_home = (
          args.length === 0 ||
          first === "" ||
          first === "/" ||
          (typeof first === "string" && first.toLowerCase() === "workspace")
        );

        if (is_home) {
          const route = get_first_accessible_route();
          if (route) return _original_set_route(route.replace(/^\/app\//, ""));
        }

        return _original_set_route.apply(frappe, args);
      };

      frappe.set_route.__cn_patched = true;
    }

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

  function patch_logo_click() {
    document.addEventListener("click", function (e) {
      const link = e.target.closest(".navbar-home, .navbar-brand");
      if (!link) return;

      const target = get_first_accessible_route();
      if (!target) return;

      e.preventDefault();
      e.stopImmediatePropagation();

      spa_navigate(target);
    }, true);
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 8 — ROUTE CHANGE HANDLER
  // ═══════════════════════════════════════════════════════════

  function on_route_change() {
    resolve_default_route();
    mount_sidebar();
    refresh_sidebar_active();
  }

  // ═══════════════════════════════════════════════════════════
  // SECTION 9 — INIT
  // ═══════════════════════════════════════════════════════════

  function init() {
    patch_frappe_default_route();
    patch_logo_click();
    resolve_default_route();

    mount_sidebar();

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