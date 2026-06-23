frappe.listview_settings = frappe.listview_settings || {};

/* =========================
   CACHE SELECTORS (BIG WIN)
========================= */

const CACHE = {
	lastRoute: null,
	newButtonHiddenFor: null,
};

/* =========================
   WORKSPACE BUTTON
========================= */

function hide_workspace_new_button() {
	if (frappe.session.user === "Administrator") return;

	$(".workspace-footer .btn-new-workspace").hide();
}

/* =========================
   REPORT FOOTER (NEW ADDITION)
========================= */

function hide_report_things() {
	$(".report-footer").hide();
	$(".menu-btn-group").hide();
}

/* =========================
   ROUTE HELPERS
========================= */

function isFormRoute(route) {
	return route && route.length >= 2;
}

function isReportRoute(route) {
	return route && route[0] === "query-report";
}

function isWorkspaceRoute(route) {
	return route && route[0] === "Workspaces";
}

/* =========================
   ROUTE HANDLER (FILTERED)
========================= */

frappe.router.on("change", () => {
	const route = frappe.get_route();
	if (!route) return;

	const routeKey = route.join("/");

	if (CACHE.lastRoute === routeKey) return;
	CACHE.lastRoute = routeKey;

	CACHE.sidebarCleaned = false;
	CACHE.newButtonHiddenFor = null;

	requestIdleCallback(() => {
		if (isWorkspaceRoute(route)) {
			hide_workspace_new_button();
		}

		if (isReportRoute(route)) {
			hide_report_things();
		}
	});
});

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
]);

function hide_new_button(listview) {
	if (!listview) return;

	const doctype = listview.doctype;

	// prevent duplicate execution
	if (CACHE.newButtonHiddenFor === doctype) return;
	CACHE.newButtonHiddenFor = doctype;

	listview.page?.btn_primary?.hide();

	requestAnimationFrame(() => {
		listview.page?.wrapper?.querySelectorAll(".btn-new-doc")?.forEach((btn) => {
			btn.style.display = "none";
		});
	});
}

NO_NEW_DOCTYPES.forEach((doctype) => {
	frappe.listview_settings[doctype] = {
		onload(listview) {
			hide_new_button(listview);
		},
		refresh(listview) {
			hide_new_button(listview);
		},
	};
});

/* =========================
   MUTATION OBSERVER (SAFE)
========================= */

const observer = new MutationObserver(() => {
	const route = frappe.get_route();

	// REPORT CLEANING (STRICT SCOPE FIX)
	if (route && route[0] === "query-report") {
		hide_report_things();
	}
});

observer.observe(document.body, {
	childList: true,
	subtree: true,
});
