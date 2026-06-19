// // THREE PARENT TYPES:
// //   type_1 — redirect + navbar children
// //   type_2 — dropdown (no redirect) + per-child navbar context
// //   type_3 — single link, no children, no navbar
// //
// // VISIBILITY RULES:
// //   Administrator: skip ALL role and permission checks — sees everything
// //   Others — Parent: user must have module role; Child doctype: can_read(); Child report: free

// (function () {
//   "use strict";

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 1 — CONFIGURATION
//   // ═══════════════════════════════════════════════════════════

//   // icon: Frappe SVG sprite id (e.g. "icon-employee" → <use href="#icon-employee">)
//   const NAV_ITEMS = {
//     "role": {
//       name: "Role",
//       type: "doctype",
//       route: "/app/role",
//       doctype: "Role",
//       icon: "icon-quantity-1"
//     },
//     "permission-manager": {
//       name: "Permission Manager",
//       type: "report",
//       route: "/app/permission-manager",
//       icon: "icon-quantity-1"
//     },
//     "employee": {
//       name: "Employee",
//       type: "doctype",
//       route: "/app/employee",
//       doctype: "Employee",
//       icon: "icon-customer"
//     },
//     "department": {
//       name: "Department",
//       type: "doctype",
//       route: "/app/department",
//       doctype: "Department",
//       icon: "icon-tag"
//     },
//     "hierarchy": {
//       name: "Hierarchy",
//       type: "doctype",
//       route: "/app/hierarchy",
//       doctype: "Hierarchy",
//       icon: "icon-sort-ascending"
//     },
//     "erp-configuration": {
//       name: "ERP Settings",
//       type: "doctype",
//       route: "/app/erp-configuration/ERP Configuration",
//       doctype: "ERP Configuration",
//       icon: "icon-setting-gear"
//     },
//     "email-domain": {
//       name: "Email domain",
//       type: "doctype",
//       route: "/app/email-domain",
//       doctype: "Email Domain",
//       icon: "icon-mail"
//     },
//     "email-account": {
//       name: "Email Account",
//       type: "doctype",
//       route: "/app/email-account",
//       doctype: "Email Account",
//       icon: "icon-mail"
//     },
//     "pdf-agreement-template": {
//       name: "Pdf Agreement Template",
//       type: "doctype",
//       route: "/app/pdf-agreement-template",
//       doctype: "Pdf Agreement Template",
//       icon: "icon-pen"
//     },
//     "resume": {
//       name: "Resume",
//       type: "doctype",
//       route: "/app/resume",
//       doctype: "Resume",
//       icon: "icon-small-file"
//     },
//     "ruc": {
//       name: "RUC",
//       type: "doctype",
//       route: "/app/ruc",
//       doctype: "RUC",
//       icon: "icon-support"
//     },
//     "jdc": {
//       name: "JDC",
//       type: "doctype",
//       route: "/app/jdc",
//       doctype: "JDC",
//       icon: "icon-support"
//     },
//     "training": {
//       name: "Training",
//       type: "doctype",
//       route: "/app/training",
//       doctype: "Training",
//       icon: "icon-getting-started"
//     },
//     "cover-letter": {
//       name: "Cover Letter",
//       type: "doctype",
//       route: "/app/cover-letter",
//       doctype: "Cover Letter",
//       icon: "icon-folder-open"
//     },
//     "technical-other-services": {
//       name: "Tech Other Services",
//       type: "doctype",
//       route: "/app/technical-other-services",
//       doctype: "Technical Other Services",
//       icon: "icon-tool"
//     },
//     "interview": {
//       name: "Interview",
//       type: "doctype",
//       route: "/app/interview",
//       doctype: "Interview",
//       icon: "icon-list-alt"
//     },
//     "marketing-other-services": {
//       name: "Marketing Other Services",
//       type: "doctype",
//       route: "/app/marketing-other-services",
//       icon: "icon-milestone"
//     },
//     "report": {
//       name: "Reports",
//       type: "report",
//       route: "/app/report",
//       icon: "icon-file"
//     },
//     "opportunity": {
//       name: "Opportunity",
//       type: "doctype",
//       route: "/app/opportunity",
//       doctype: "Opportunity",
//       icon: "icon-assign"
//     },
//     "customer": {
//       name: "Customer",
//       type: "doctype",
//       route: "/app/customer",
//       doctype: "Customer",
//       icon: "icon-customer"
//     },
//     "company": {
//       name: "Company",
//       type: "doctype",
//       route: "/app/company",
//       doctype: "Company",
//       icon: "icon-organization"
//     },
//     "fiscal-year": {
//       name: "Fiscal Year",
//       type: "doctype",
//       route: "/app/fiscal-year",
//       doctype: "Fiscal Year",
//       icon: "icon-calendar"
//     },
//     "accounts-settings": {
//       name: "Accounts Settings",
//       type: "doctype",
//       route: "/app/accounts-settings/Accounts Settings",
//       doctype: "Accounts Settings",
//       icon: "icon-setting-gear"
//     },
//     "bank-account": {
//       name: "Bank Account",
//       type: "doctype",
//       route: "/app/bank-account",
//       doctype: "Bank Account",
//       icon: "icon-number-card"
//     },
//     "sales-order": {
//       name: "Sales Order",
//       type: "doctype",
//       route: "/app/sales-order",
//       doctype: "Sales Order",
//       icon: "icon-stock"
//     },
//     "sales-invoice": {
//       name: "Sales Invoice",
//       type: "doctype",
//       route: "/app/sales-invoice",
//       doctype: "Sales Invoice",
//       icon: "icon-expenses"
//     },
//     "purchase-order": {
//       name: "Purchase Order",
//       type: "doctype",
//       route: "/app/purchase-order",
//       doctype: "Purchase Order",
//       icon: "icon-stock"
//     },
//     "purchase-invoice": {
//       name: "Purchase Invoice",
//       type: "doctype",
//       route: "/app/purchase-invoice",
//       doctype: "Purchase Invoice",
//       icon: "icon-expenses"
//     },
//     "journal-entry": {
//       name: "Journal Entry",
//       type: "doctype",
//       route: "/app/journal-entry",
//       doctype: "Journal Entry",
//       icon: "icon-money-coins-1"
//     },
//     "payment-entry": {
//       name: "Payment Entry",
//       type: "doctype",
//       route: "/app/payment-entry",
//       doctype: "Payment Entry",
//       icon: "icon-money-coins-1"
//     },
//     "supplier": {
//       name: "Supplier",
//       type: "doctype",
//       route: "/app/supplier",
//       doctype: "Supplier",
//       icon: "icon-share"
//     },
//     "subscription": {
//       name: "Subscription",
//       type: "doctype",
//       route: "/app/subscription",
//       doctype: "Subscription",
//       icon: "icon-money-coins-1"
//     },
//     "subscription-plan": {
//       name: "Subscription Plan",
//       type: "doctype",
//       route: "/app/subscription-plan",
//       doctype: "Subscription Plan",
//       icon: "icon-money-coins-1"
//     },
//   };

//   // icon: Frappe SVG sprite id for the parent module header
//   const SIDEBAR_CONFIG = [
//     {
//       key: "setup",
//       label: "Setup Guide",
//       parent_type: "type_3",
//       route: "/app/setup",
//       role: "_show_setup",
//       icon: "icon-setting-gear"
//     },
//     {
//       key: "staffing-master",
//       label: "Staffing Master",
//       parent_type: "type_2",
//       role: "_show_staffing_master",
//       icon: "icon-keyboard",
//       children: ["department", "hierarchy", "erp-configuration", "email-domain", "email-account", "pdf-agreement-template"]
//     },
//     {
//       key: "item",
//       label: "Item",
//       parent_type: "type_3",
//       route: "/app/item",
//       role: "_show_item",
//       icon: "icon-stock"
//     },
//     {
//       key: "user",
//       label: "User",
//       parent_type: "type_1",
//       route: "/app/user",
//       role: "_show_employees",
//       icon: "icon-users",
//       children: ["role", "permission-manager"]
//     },
//     {
//       key: "employee",
//       label: "Employee",
//       parent_type: "type_1",
//       route: "/app/employee",
//       role: "_show_employees",
//       icon: "icon-users",
//       children: ["department", "hierarchy"]
//     },
//     {
//       key: "lead",
//       label: "Lead",
//       parent_type: "type_3",
//       route: "/app/lead",
//       role: "_show_lead",
//       icon: "icon-share"
//     },
//     {
//       key: "sales",
//       label: "Sales",
//       parent_type: "type_2",
//       role: "_show_sales",
//       icon: "icon-call",
//       children: ["opportunity", "customer", "sales-order"]
//     },
//     {
//       key: "technical",
//       label: "Technical",
//       parent_type: "type_2",
//       role: "_show_technical",
//       icon: "icon-website",
//       children: ["resume", "jdc", "ruc", "training", "cover-letter", "technical-other-services"]
//     },
//     {
//       key: "marketing",
//       label: "Marketing",
//       parent_type: "type_1",
//       route: "/app/marketing",
//       role: "_show_marketing",
//       icon: "icon-users",
//       children: ["interview", "marketing-other-services", "report"]
//     },
//     {
//       key: "other-services",
//       label: "Other Services",
//       parent_type: "type_3",
//       route: "/app/other-services",
//       role: "_show_other_service",
//       icon: "icon-setting-gear"
//     },
//     {
//       key: "onboardings",
//       label: "Onboarding",
//       parent_type: "type_3",
//       route: "/app/onboardings",
//       role: "_show_onboarding",
//       icon: "icon-branch"
//     },
//     {
//       key: "cr",
//       label: "CR",
//       parent_type: "type_3",
//       route: "/app/cr",
//       role: "_show_cr",
//       icon: "icon-assign"
//     },
//     {
//       key: "email-inbox",
//       label: "Email Inbox",
//       parent_type: "type_3",
//       route: "/app/email-inbox",
//       role: "_show_email_inbox",
//       icon: "icon-mail"
//     },
//     {
//       key: "e-sign",
//       label: "E Sign",
//       parent_type: "type_3",
//       route: "/app/e-sign",
//       role: "_show_e_sign",
//       icon: "icon-pen"
//     },
//     {
//       key: "account-master",
//       label: "Accounts Master",
//       parent_type: "type_2",
//       role: "_show_account_master",
//       icon: "icon-keyboard",
//       children: ["company", "fiscal-year", "accounts-settings", "bank-account"]
//     },
//     {
//       key: "coa",
//       label: "Charts of accounts",
//       parent_type: "type_3",
//       route: "/app/account/view/tree",
//       role: "_show_coa",
//       icon: "icon-stock"
//     },
//     {
//       key: "pe_request",
//       label: "Pending PE Request",
//       parent_type: "type_3",
//       route: "/app/pending-pe-request",
//       role: "_show_pe_request",
//       icon: "icon-expenses"
//     },
//     {
//       key: "accounting",
//       label: "Accounting",
//       parent_type: "type_2",
//       role: "_show_accounting",
//       icon: "icon-accounting",
//       children: [
//         "sales-order",
//         "sales-invoice",
//         "purchase-order",
//         "purchase-invoice",
//         "journal-entry",
//         "payment-entry",
//         "supplier",
//         "subscription",
//         "report",
//       ]
//     }
//   ];

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 2 — PERMISSION & ROLE HELPERS
//   // ═══════════════════════════════════════════════════════════

//   function is_administrator() {
//     if (!window.frappe) return false;
//     return (
//       frappe.session && frappe.session.user === "Administrator"
//     ) || (
//       frappe.user_roles && frappe.user_roles.includes("Administrator")
//     );
//   }

//   function user_has_role(role) {
//     if (is_administrator()) return true;
//     if (!window.frappe || !frappe.user_roles) return false;
//     return frappe.user_roles.includes(role);
//   }

//   function can_read(doctype) {
//     if (is_administrator()) return true;
//     if (!window.frappe) return false;
//     try {
//       return !!frappe.model.can_read(doctype);
//     } catch (e) {
//       return false;
//     }
//   }

//   function item_accessible(key) {
//     if (is_administrator()) return true;
//     const item = NAV_ITEMS[key];
//     if (!item) return false;
//     if (item.type === "doctype") return can_read(item.doctype);
//     return true;
//   }

//   function visible_children(parent_cfg) {
//     if (!parent_cfg.children) return [];
//     return parent_cfg.children.filter(item_accessible);
//   }

//   function parent_visible(parent_cfg) {
//     if (!user_has_role(parent_cfg.role)) return false;
//     if (parent_cfg.parent_type === "type_3") return item_accessible(parent_cfg.key);
//     return visible_children(parent_cfg).length > 0;
//   }

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 3 — ROUTE HELPERS
//   // ═══════════════════════════════════════════════════════════

//   function current_path() {
//     let path = window.location.pathname;
//     try {
//       path = decodeURIComponent(path);
//     } catch (e) {}
//     return path.replace(/\/+$/, "");
//   }

//   function key_is_active(key) {
//     const item = NAV_ITEMS[key];
//     if (!item) return false;
//     const route = item.route.replace(/\/+$/, "");
//     const path  = current_path();
//     return path === route || path.startsWith(route + "/");
//   }

//   function parent_route_is_active(parent_cfg) {
//     if (!parent_cfg.route) return false;
//     const route = parent_cfg.route.replace(/\/+$/, "");
//     const path  = current_path();
//     return path === route || path.startsWith(route + "/");
//   }

//   function get_active_owner_key() {
//     for (const cfg of SIDEBAR_CONFIG) {
//       if (!parent_visible(cfg)) continue;

//       if (cfg.parent_type === "type_3") {
//         if (parent_route_is_active(cfg)) return cfg.key;
//       } else if (cfg.parent_type === "type_1") {
//         if (parent_route_is_active(cfg) || (cfg.children && cfg.children.some(key_is_active))) {
//           return cfg.key;
//         }
//       } else if (cfg.parent_type === "type_2") {
//         if (cfg.children && cfg.children.some(key_is_active)) return cfg.key;
//       }
//     }
//     return null;
//   }

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 4 — EXPAND / COLLAPSE PERSISTENCE (single, exclusive)
//   // ═══════════════════════════════════════════════════════════

//   const STORAGE_KEY = "custom_nav_expanded_module";

//   function load_expanded_key() {
//     try { return localStorage.getItem(STORAGE_KEY) || null; }
//     catch (e) { return null; }
//   }

//   function save_expanded_key(key) {
//     try {
//       if (key) localStorage.setItem(STORAGE_KEY, key);
//       else localStorage.removeItem(STORAGE_KEY);
//     } catch (e) {}
//   }

//   function route_forced_expand_key() {
//     for (const cfg of SIDEBAR_CONFIG) {
//       if (cfg.parent_type === "type_2" && cfg.children && cfg.children.some(key_is_active)) {
//         return cfg.key;
//       }
//     }
//     return null;
//   }

//   function compute_expanded_key() {
//     return route_forced_expand_key() || load_expanded_key();
//   }

//   function should_expand(parent_cfg) {
//     if (parent_cfg.parent_type !== "type_2") return false;
//     return compute_expanded_key() === parent_cfg.key;
//   }

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 5 — SIDEBAR DOM RENDERING
//   // ═══════════════════════════════════════════════════════════

//   const SIDEBAR_ID = "custom-nav-sidebar";

//   function make_icon(icon_id, size) {
//     size = size || "sm";
//     const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
//     svg.setAttribute("class", "icon icon-" + size);
//     svg.setAttribute("aria-hidden", "true");
//     const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
//     use.setAttribute("href", "#" + icon_id);
//     svg.appendChild(use);
//     return svg;
//   }

//   function build_sidebar_dom() {
//     const wrap = document.createElement("div");
//     wrap.id = SIDEBAR_ID;
//     wrap.className = "custom-nav-sidebar";

//     SIDEBAR_CONFIG.forEach(function (cfg) {
//       if (!parent_visible(cfg)) return;
//       if (cfg.parent_type === "type_3") { wrap.appendChild(make_type3_el(cfg)); return; }
//       if (cfg.parent_type === "type_1") { wrap.appendChild(make_type1_el(cfg)); return; }
//       if (cfg.parent_type === "type_2") { wrap.appendChild(make_type2_el(cfg)); return; }
//     });

//     return wrap;
//   }

//   function make_item_inner(icon_id, label_text) {
//     const icon_wrap = document.createElement("span");
//     icon_wrap.className = "cn-item-icon";
//     if (icon_id) icon_wrap.appendChild(make_icon(icon_id, "sm"));

//     const label = document.createElement("span");
//     label.className = "cn-item-label";
//     label.textContent = label_text;

//     return [icon_wrap, label];
//   }

//   function make_type3_el(cfg) {
//     const a = document.createElement("a");
//     a.className = "cn-item cn-parent-link" + (parent_route_is_active(cfg) ? " is-active" : "");
//     a.href = cfg.route;
//     a.dataset.parentKey = cfg.key;
//     a.dataset.parentType = "type_3";

//     make_item_inner(cfg.icon, cfg.label).forEach(function (el) { a.appendChild(el); });

//     a.addEventListener("click", function (e) {
//       e.preventDefault();
//       spa_navigate(cfg.route);
//     });
//     return a;
//   }

//   function make_type1_el(cfg) {
//     const is_owner = get_active_owner_key() === cfg.key;

//     const wrap = document.createElement("div");
//     wrap.className = "cn-group cn-group--type1" + (is_owner ? " has-active" : "");
//     wrap.dataset.parentKey = cfg.key;

//     const a = document.createElement("a");
//     a.className = "cn-item cn-parent-link" + (parent_route_is_active(cfg) ? " is-active" : "");
//     a.href = cfg.route;
//     a.dataset.parentKey = cfg.key;
//     a.dataset.parentType = "type_1";

//     make_item_inner(cfg.icon, cfg.label).forEach(function (el) { a.appendChild(el); });

//     a.addEventListener("click", function (e) {
//       e.preventDefault();
//       spa_navigate(cfg.route);
//     });

//     wrap.appendChild(a);
//     return wrap;
//   }

//   function make_type2_el(cfg) {
//     const expanded = should_expand(cfg);
//     const is_owner = get_active_owner_key() === cfg.key;
//     const kids     = visible_children(cfg);

//     const wrap = document.createElement("div");
//     wrap.className = "cn-group cn-group--type2" + (expanded ? " is-expanded" : "");
//     wrap.dataset.parentKey = cfg.key;

//     const header = document.createElement("div");
//     header.className = "cn-item cn-parent-toggle";
//     header.dataset.parentKey = cfg.key;

//     make_item_inner(cfg.icon, cfg.label).forEach(function (el) { header.appendChild(el); });

//     const chevron = document.createElement("span");
//     chevron.className = "cn-chevron";
//     chevron.innerHTML =
//       '<svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
//       + '<polyline points="4,6 8,10 12,6"/></svg>';
//     header.appendChild(chevron);

//     header.addEventListener("click", function (e) {
//       e.stopPropagation();
//       const is_open = wrap.classList.contains("is-expanded");

//       document.querySelectorAll(".cn-group--type2").forEach(function (other) {
//         if (other !== wrap) other.classList.remove("is-expanded");
//       });

//       wrap.classList.toggle("is-expanded", !is_open);
//       save_expanded_key(!is_open ? cfg.key : null);
//     });

//     wrap.appendChild(header);

//     const ul = document.createElement("ul");
//     ul.className = "cn-children";

//     kids.forEach(function (child_key) {
//       const item = NAV_ITEMS[child_key];
//       if (!item) return;
//       const li = document.createElement("li");
//       const a  = document.createElement("a");
//       a.className = "cn-item cn-child-link" + (is_owner && key_is_active(child_key) ? " is-active" : "");
//       a.href = item.route;
//       a.dataset.navKey = child_key;

//       make_item_inner(item.icon, item.name).forEach(function (el) { a.appendChild(el); });

//       a.addEventListener("click", function (e) {
//         e.preventDefault();
//         spa_navigate(item.route);
//       });
//       li.appendChild(a);
//       ul.appendChild(li);
//     });

//     wrap.appendChild(ul);
//     return wrap;
//   }

//   function mount_sidebar() {
//     document.querySelectorAll(".layout-side-section").forEach(function (section) {
//       if (section.querySelector("#" + SIDEBAR_ID)) return;
//       section.appendChild(build_sidebar_dom());
//     });
//   }

//   function refresh_sidebar_active() {
//     const owner_key    = get_active_owner_key();
//     const expanded_key = compute_expanded_key();

//     document.querySelectorAll(".cn-parent-link[data-parent-key]").forEach(function (el) {
//       const cfg = SIDEBAR_CONFIG.find(c => c.key === el.dataset.parentKey);
//       if (!cfg) return;
//       el.classList.toggle("is-active", parent_route_is_active(cfg));
//     });

//     document.querySelectorAll(".cn-group--type1[data-parent-key]").forEach(function (el) {
//       el.classList.toggle("has-active", owner_key === el.dataset.parentKey);
//     });

//     document.querySelectorAll(".cn-group--type2[data-parent-key]").forEach(function (group) {
//       const key      = group.dataset.parentKey;
//       const is_owner = owner_key === key;

//       group.querySelectorAll(".cn-child-link[data-nav-key]").forEach(function (el) {
//         el.classList.toggle("is-active", is_owner && key_is_active(el.dataset.navKey));
//       });

//       group.classList.toggle("is-expanded", key === expanded_key);
//     });
//   }

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 6 — SPA NAVIGATION
//   // ═══════════════════════════════════════════════════════════

//   function spa_navigate(route) {
//     if (window.frappe && frappe.set_route) {
//       frappe.set_route(route.replace(/^\/app\//, ""));
//     } else {
//       window.location.href = route;
//     }
//   }

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 7 — DEFAULT ROUTE (role-aware landing page)
//   // ═══════════════════════════════════════════════════════════

//   function get_first_accessible_route() {
//     for (const cfg of SIDEBAR_CONFIG) {
//       if (!parent_visible(cfg)) continue;

//       if (cfg.parent_type === "type_3" || cfg.parent_type === "type_1") {
//         return cfg.route;
//       }

//       if (cfg.parent_type === "type_2") {
//         const kids = visible_children(cfg);
//         if (kids.length) {
//           const first_item = NAV_ITEMS[kids[0]];
//           if (first_item) return first_item.route;
//         }
//       }
//     }
//     return null;
//   }

//   function resolve_default_route() {
//     const path = current_path();
//     if (path !== "/app" && path !== "") return;
//     const target = get_first_accessible_route();
//     if (target) spa_navigate(target);
//   }

//   function patch_frappe_default_route() {
//     if (!window.frappe) return;

//     const target = get_first_accessible_route();
//     if (target && frappe.boot) {
//       frappe.boot.default_route = target.replace(/^\/app\//, "");
//     }

//     if (typeof frappe.set_route === "function" && !frappe.set_route.__cn_patched) {
//       const _original_set_route = frappe.set_route.bind(frappe);

//       frappe.set_route = function () {
//         const args = Array.prototype.slice.call(arguments);
//         const first = args[0];

//         const is_home = (
//           args.length === 0 ||
//           first === "" ||
//           first === "/" ||
//           (typeof first === "string" && first.toLowerCase() === "workspace")
//         );

//         if (is_home) {
//           const route = get_first_accessible_route();
//           if (route) return _original_set_route(route.replace(/^\/app\//, ""));
//         }

//         return _original_set_route.apply(frappe, args);
//       };

//       frappe.set_route.__cn_patched = true;
//     }

//     if (frappe.router && typeof frappe.router.push === "function" && !frappe.router.push.__cn_patched) {
//       const _original_push = frappe.router.push.bind(frappe.router);

//       frappe.router.push = function (route) {
//         const is_home = (
//           !route ||
//           route === "" ||
//           route === "/" ||
//           route === "/app" ||
//           route === "/app/" ||
//           (typeof route === "string" && route.toLowerCase().replace(/^\/app\//, "") === "workspace")
//         );

//         if (is_home) {
//           const target = get_first_accessible_route();
//           if (target) return _original_push(target);
//         }

//         return _original_push(route);
//       };

//       frappe.router.push.__cn_patched = true;
//     }
//   }

//   function patch_logo_click() {
//     document.addEventListener("click", function (e) {
//       const link = e.target.closest(".navbar-home, .navbar-brand");
//       if (!link) return;

//       const target = get_first_accessible_route();
//       if (!target) return;

//       e.preventDefault();
//       e.stopImmediatePropagation();

//       spa_navigate(target);
//     }, true);
//   }

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 8 — ROUTE CHANGE HANDLER
//   // ═══════════════════════════════════════════════════════════

//   function on_route_change() {
//     resolve_default_route();
//     mount_sidebar();
//     refresh_sidebar_active();
//   }

//   // ═══════════════════════════════════════════════════════════
//   // SECTION 9 — INIT
//   // ═══════════════════════════════════════════════════════════

//   function init() {
//     patch_frappe_default_route();
//     patch_logo_click();
//     resolve_default_route();

//     mount_sidebar();

//     if (window.frappe) {
//       if (frappe.router && typeof frappe.router.on === "function") {
//         frappe.router.on("change", on_route_change);
//       }
//       $(document).on("page-change frappe:navigate frappe:route-change", on_route_change);
//     }

//     window.addEventListener("popstate", on_route_change);

//     const observer = new MutationObserver(function () {
//       const missing = document.querySelector(
//         ".layout-side-section:not(:has(#" + SIDEBAR_ID + "))"
//       );
//       if (missing) mount_sidebar();
//     });
//     observer.observe(document.body, { childList: true, subtree: true });
//   }

//   if (window.frappe && typeof frappe.ready === "function") {
//     frappe.ready(init);
//   } else if (document.readyState === "complete" || document.readyState === "interactive") {
//     init();
//   } else {
//     document.addEventListener("DOMContentLoaded", init);
//   }

// })();

//  Config is fetched from the "Sidebar Master" DocType (field: config_json)
//  using a two-step lookup:
//    1. Look for a doc where sidebar_owner = current user  → use it
//    2. Fall back to the doc where sidebar_owner = "Master"
//
//  THREE PARENT TYPES:
//    type_1 — redirect + always-visible children (no toggle)
//    type_2 — dropdown group, no redirect, SPA toggle (zero page reload)
//    type_3 — single link, no children
//
//  SHORTCUT SUPPORT:
//    Each item may carry a `shortcut` field (e.g. "J", "J+E", "Alt+P").
//    The sidebar registers these as global keydown handlers that SPA-navigate
//    to the relevant route when matched. "N" alone is reserved.
//
//  FEATURES:
//    ✓ type_2 toggle is pure DOM/CSS — zero page reload
//    ✓ "+" quick-create button on every doctype link
//    ✓ Config cached in localStorage (TTL 5 min) per user
//    ✓ Logo + home navigation redirected to first accessible route
// ═══════════════════════════════════════════════════════════════════════════

(function () {
	"use strict";

	// ─── CACHE ────────────────────────────────────────────────────────────────
	// Keyed per user so different users sharing a browser don't cross-pollinate
	function cache_key() {
		return "csb_config_" + ((frappe.session && frappe.session.user) || "guest");
	}
	function cache_ts_key() {
		return "csb_ts_" + ((frappe.session && frappe.session.user) || "guest");
	}
	const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

	let SIDEBAR_CONFIG = []; // [{key, label, icon, parent_type, route?, shortcut?, children?}]
	let NAV_ITEMS = {}; // key → {name, type, route, doctype?, icon, shortcut?}

	// ─── PERMISSIONS ──────────────────────────────────────────────────────────

	function is_administrator() {
		if (!window.frappe) return false;
		return (
			(frappe.session && frappe.session.user === "Administrator") ||
			(frappe.user_roles && frappe.user_roles.includes("Administrator"))
		);
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
		if (item.type === "doctype" && item.doctype) return can_read(item.doctype);
		return true;
	}

	function visible_children(parent_cfg) {
		return (parent_cfg.children || []).filter((c) => item_accessible(c.key));
	}

	function parent_visible(cfg) {
		if (cfg.parent_type === "type_3") {
			if (cfg.link_type === "doctype" && cfg.doctype) return can_read(cfg.doctype);
			return true;
		}
		return visible_children(cfg).length > 0;
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

	// ─── SHORTCUT BADGE on sidebar items ─────────────────────────────────────
	//  Tiny visual badge showing the assigned shortcut (e.g. "J+E")

	function make_shortcut_badge(shortcut) {
		if (!shortcut) return null;
		const span = document.createElement("span");
		span.className = "cn-shortcut-badge";
		span.textContent = shortcut;
		span.title = "Shortcut: " + shortcut;
		return span;
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

		return wrap;
	}

	function make_type3_el(cfg) {
		const a = document.createElement("a");
		a.className = "cn-item cn-parent-link" + (parent_route_is_active(cfg) ? " is-active" : "");
		a.href = cfg.route || "#";
		a.dataset.parentKey = cfg.key;
		a.dataset.parentType = "type_3";

		make_item_inner(cfg.icon, cfg.label).forEach((el) => a.appendChild(el));

		if (cfg.link_type === "doctype" && cfg.doctype && !cfg.issingle) {
			a.appendChild(make_plus_btn(cfg.doctype));
		}
		const badge = make_shortcut_badge(cfg.shortcut);
		if (badge) a.appendChild(badge);

		a.addEventListener("click", function (e) {
			e.preventDefault();
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
		const badge = make_shortcut_badge(cfg.shortcut);
		if (badge) a.appendChild(badge);

		a.addEventListener("click", function (e) {
			e.preventDefault();
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

				if (item.type === "doctype" && item.doctype && !item.issingle) {
					ca.appendChild(make_plus_btn(item.doctype));
				}
				const cb = make_shortcut_badge(item.shortcut);
				if (cb) ca.appendChild(cb);

				ca.addEventListener("click", function (e) {
					e.preventDefault();
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

		const badge = make_shortcut_badge(cfg.shortcut);
		if (badge) header.appendChild(badge);

		const chevron = document.createElement("span");
		chevron.className = "cn-chevron";
		chevron.innerHTML =
			'<svg viewBox="0 0 16 16" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4,6 8,10 12,6"/></svg>';
		header.appendChild(chevron);

		function toggle_group(e) {
			e.stopPropagation();
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

			if (item.type === "doctype" && item.doctype && !item.issingle) {
				a.appendChild(make_plus_btn(item.doctype));
			}
			const cb = make_shortcut_badge(item.shortcut);
			if (cb) a.appendChild(cb);

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
	//  Registers global keydown handler for all shortcut-carrying items.
	//  Supports: single key ("J"), chord ("J+E" — J pressed then E within 1s),
	//            Alt+key ("Alt+P"), Ctrl+key ("Ctrl+P").

	let _sc_chord_first = null;
	let _sc_chord_timer = null;
	const SC_CHORD_MS = 1000;

	// Build a flat map: normalised_shortcut → route
	function build_shortcut_map() {
		const map = {};
		function add(shortcut, route) {
			if (shortcut && route) map[shortcut.toLowerCase()] = route;
		}
		SIDEBAR_CONFIG.forEach(function (cfg) {
			if (cfg.parent_type === "type_3" || cfg.parent_type === "type_1")
				add(cfg.shortcut, cfg.route);
			if (cfg.parent_type === "type_2") add(cfg.shortcut, null); // group — no nav target
			(cfg.children || []).forEach(function (c) {
				const item = NAV_ITEMS[c.key];
				if (item) add(item.shortcut, item.route);
			});
		});
		return map;
	}

	function register_shortcuts() {
		// Remove previous listener if re-registered
		if (window._csb_key_handler) {
			document.removeEventListener("keydown", window._csb_key_handler, true);
		}

		const map = build_shortcut_map();
		if (!Object.keys(map).length) return;

		const MODS = new Set(["Alt", "Control", "Shift", "Meta", "CapsLock", "Tab"]);

		function handler(e) {
			// Don't fire while user is typing in an input/textarea/contenteditable
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
				// Plain key or chord
				if (_sc_chord_first) {
					// Second key of chord
					candidate = _sc_chord_first + "+" + raw.toLowerCase();
					clearTimeout(_sc_chord_timer);
					_sc_chord_first = null;
					_sc_chord_timer = null;
				} else {
					// First key — check immediately as single, but also start chord window
					const single = raw.toLowerCase();
					if (map[single]) {
						// Start chord timer; if nothing comes, fire the single
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
						return; // don't navigate yet — wait for possible second key
					} else {
						// First key of potential chord but no single match — wait for second
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

	// ─── CONFIG LOADING ───────────────────────────────────────────────────────
	//  Two-step: user doc first → Master fallback.
	//  Results cached in localStorage per user with 5-min TTL.

	function load_from_cache() {
		try {
			const ts = parseInt(localStorage.getItem(cache_ts_key()) || "0", 10);
			if (Date.now() - ts < CACHE_TTL_MS) {
				const raw = localStorage.getItem(cache_key());
				if (raw) return JSON.parse(raw);
			}
		} catch (e) {}
		return null;
	}

	function save_to_cache(config) {
		try {
			localStorage.setItem(cache_key(), JSON.stringify(config));
			localStorage.setItem(cache_ts_key(), String(Date.now()));
		} catch (e) {}
	}

	function apply_config(config_array) {
		SIDEBAR_CONFIG = config_array;
		NAV_ITEMS = {};
		config_array.forEach(function (cfg) {
			// type_3 top-level links go into the flat map
			if (cfg.parent_type === "type_3") {
				NAV_ITEMS[cfg.key] = {
					name: cfg.label,
					type: cfg.link_type || "doctype",
					route: cfg.route || "/app/" + cfg.key,
					doctype: cfg.doctype || null,
					icon: cfg.icon,
					shortcut: cfg.shortcut || "",
					issingle: !!(
						cfg.route && cfg.route.includes("/" + encodeURIComponent(cfg.label))
					),
				};
			}
			// Children of type_1 / type_2
			(cfg.children || []).forEach(function (c) {
				NAV_ITEMS[c.key] = {
					name: c.name,
					type: c.type || "doctype",
					route: c.route,
					doctype: c.doctype || null,
					icon: c.icon || "icon-setting-gear",
					shortcut: c.shortcut || "",
					issingle: !!(c.route && c.route.includes("/" + encodeURIComponent(c.name))),
				};
			});
		});
	}

	async function fetch_config_json() {
		const current_user =
			(frappe.session && frappe.session.user) ||
			(frappe.boot && frappe.boot.user && frappe.boot.user.name);

		if (current_user) {
			try {
				const user_res = await frappe.call({
					method: "frappe.client.get_value",
					args: {
						doctype: "Sidebar Master",
						fieldname: "config_json",
						filters: { sidebar_owner: current_user },
					},
				});
				const raw = user_res && user_res.message && user_res.message.config_json;
				if (raw) return JSON.parse(raw);
			} catch (e) {
				console.error("Custom Sidebar: user config fetch failed", e);
			}
		}

		try {
			const master_res = await frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Sidebar Master",
					fieldname: "config_json",
					filters: { sidebar_owner: "Master" },
				},
			});
			const raw = master_res && master_res.message && master_res.message.config_json;
			if (raw) return JSON.parse(raw);
		} catch (e) {
			console.error("Custom Sidebar: failed to load Master config", e);
		}

		return null;
	}

	async function load_config() {
		// 1. Cache hit
		const cached = load_from_cache();
		if (cached) {
			apply_config(cached);
			return;
		}

		// 2. Fetch
		if (!window.frappe || typeof frappe.call !== "function") return;

		const parsed = await fetch_config_json();
		if (parsed) {
			apply_config(parsed);
			save_to_cache(parsed);
		} else {
			console.warn("Custom Sidebar: no config found for user or Master.");
		}
	}

	// Expose a method to force-refresh (call from console or after saving config)
	window.csb_reload = async function () {
		try {
			localStorage.removeItem(cache_key());
			localStorage.removeItem(cache_ts_key());
		} catch (e) {}
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
      .cn-item.cn-child-link { position:relative; padding-right:28px !important; }

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

      /* ── Shortcut badge ── */
      .cn-shortcut-badge {
        display:inline-flex; align-items:center;
        margin-left:auto; margin-right:28px;
        padding:1px 5px; border-radius:4px;
        background:var(--control-bg,rgba(0,0,0,.06));
        border:1px solid var(--border-color,rgba(0,0,0,.1));
        font-size:9px; font-weight:700; font-family:monospace;
        color:var(--text-muted,#888); letter-spacing:.03em;
        flex-shrink:0; white-space:nowrap; pointer-events:none;
      }
      .is-active .cn-shortcut-badge { background:rgba(255,255,255,.18); border-color:rgba(255,255,255,.3); color:inherit; }

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

		// Re-mount if Frappe swaps the layout DOM
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
