// frappe.listview_settings = frappe.listview_settings || {};

// /* =========================
//    LIST VIEW (LIGHTWEIGHT)
// ========================= */

// frappe.views.ListView = class CustomListView extends frappe.views.ListView {
// 	render() {
// 		super.render();

// 		requestIdleCallback(() => {
// 			this.remove_default_filters();
// 		});
// 	}

// 	remove_default_filters() {
// 		const $sidebar = $("body .layout-side-section");
// 		if (!$sidebar.length) return;

// 		$sidebar.find(".group-by-field").hide();
// 		$sidebar.find(".add-group-by").hide();
// 		$sidebar.find(".save-filter-section").hide();
// 	}
// };

// /* =========================
//    CACHE SELECTORS (BIG WIN)
// ========================= */

// const CACHE = {
// 	formSidebar: null,
// 	sidebarCleaned: false,
// 	lastRoute: null,
// };

// /* =========================
//    CLEANERS
// ========================= */

// function cleanSidebarOnce() {
// 	if (CACHE.sidebarCleaned) return;

// 	const $sidebar = $(".form-sidebar");
// 	if (!$sidebar.length) return;

// 	CACHE.formSidebar = $sidebar;

// 	$sidebar.find(".form-follow").hide();

// 	$sidebar.find("*").each(function () {
// 		const text = this.textContent?.trim();
// 		if (!text) return;

// 		if (
// 			text.includes("Assigned") ||
// 			text.includes("Share") ||
// 			text.includes("Attachment")
// 		) {
// 			$(this).hide();
// 		}
// 	});

// 	CACHE.sidebarCleaned = true;
// }

// /* =========================
//    WORKSPACE BUTTON
// ========================= */

// function hide_workspace_new_button() {
// 	if (frappe.session.user === "Administrator") return;

// 	$(".workspace-footer .btn-new-workspace").hide();
// }

// /* =========================
//    REPORT FOOTER (NEW ADDITION)
// ========================= */

// function hide_report_things() {
// 	$(".report-footer").hide();
// 	$(".menu-btn-group").hide();
// }

// /* =========================
//    ROUTE HELPERS
// ========================= */

// function isFormRoute(route) {
// 	return route && route.length >= 2;
// }

// function isReportRoute(route) {
// 	return route && route[0] === "query-report";
// }

// function isWorkspaceRoute(route) {
// 	return route && route[0] === "Workspaces";
// }

// /* =========================
//    ROUTE HANDLER (FILTERED)
// ========================= */

// frappe.router.on("change", () => {
// 	const route = frappe.get_route();
// 	if (!route) return;

// 	const routeKey = route.join("/");

// 	if (CACHE.lastRoute === routeKey) return;
// 	CACHE.lastRoute = routeKey;

// 	// reset form cache only when leaving/entering
// 	CACHE.sidebarCleaned = false;

// 	requestIdleCallback(() => {
// 		// workspace cleanup
// 		if (isWorkspaceRoute(route)) {
// 			hide_workspace_new_button();
// 		}

// 		// report cleanup
// 		if (isReportRoute(route)) {
// 			hide_report_things();
// 		}

// 		// form cleanup
// 		if (isFormRoute(route) && cur_frm) {
// 			cleanSidebarOnce();
// 		}
// 	});
// });

// /* =========================
//    MUTATION OBSERVER (SAFE)
// ========================= */

// const observer = new MutationObserver(() => {
// 	const route = frappe.get_route();

// 	// FORM CLEANING (only when needed)
// 	if (!CACHE.sidebarCleaned) {
// 		cleanSidebarOnce();
// 	}

// 	// REPORT CLEANING (STRICT SCOPE FIX)
// 	if (route && route[0] === "query-report") {
// 		hide_report_things();
// 	}
// });

// observer.observe(document.body, {
// 	childList: true,
// 	subtree: true,
// });