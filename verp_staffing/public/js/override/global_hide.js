frappe.listview_settings = frappe.listview_settings || {};

const CACHE = {
	lastRoute: null,
	newButtonHiddenFor: null,
};

function hide_report_things() {
	$(".report-footer").hide();
	$(".menu-btn-group").hide();
}

function isFormRoute(route) {
	return route && route.length >= 2;
}

function isReportRoute(route) {
	return route && route[0] === "query-report";
}

function isWorkspaceRoute(route) {
	return route && route[0] === "Workspaces";
}

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
			$(".workspace-footer")
				.find(".btn-new-workspace, .btn-edit-workspace")
				.hide();
		}

		if (isReportRoute(route)) {
			hide_report_things();
		}
	});
});

const NO_PLUS_BUTTON_DISPLAY_DOCTYPES = new Set([
	"OnboardiBUTTON_DISPLAY_ngs",
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

NO_PLUS_BUTTON_DISPLAY_DOCTYPES.forEach((doctype) => {
	frappe.listview_settings[doctype] = {
		onload(listview) {
			hide_new_button(listview);
		},
		refresh(listview) {
			hide_new_button(listview);
		},
	};
});

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
