// // Persists the selected marketing_link across view switches (URL <-> sessionStorage).
// window.InterviewMarketingFilter =
// 	window.InterviewMarketingFilter ||
// 	(function () {
// 		const STORAGE_KEY = "interview_marketing_link";

// 		return {
// 			get() {
// 				const from_url = new URLSearchParams(window.location.search).get(
// 					"marketing_link",
// 				);
// 				if (from_url) {
// 					try {
// 						sessionStorage.setItem(STORAGE_KEY, from_url);
// 					} catch (e) {}
// 					return from_url;
// 				}

// 				let from_storage = null;
// 				try {
// 					from_storage = sessionStorage.getItem(STORAGE_KEY);
// 				} catch (e) {}
// 				if (from_storage) {
// 					window.InterviewMarketingFilter.set(from_storage);
// 				}
// 				return from_storage;
// 			},

// 			set(value) {
// 				if (!value) return;
// 				try {
// 					sessionStorage.setItem(STORAGE_KEY, value);
// 				} catch (e) {}
// 				const url = new URL(window.location.href);
// 				url.searchParams.set("marketing_link", value);
// 				window.history.replaceState({}, "", url);
// 			},
// 		};
// 	})();

// window.STATUS_INDICATOR_MAP = window.STATUS_INDICATOR_MAP || {
// 	Scheduled: "cyan",
// 	Today: "yellow",
// 	Completed: "blue",
// 	Cancelled: "gray",
// 	Rescheduled: "orange",
// 	"Get The Offer": "green",
// 	Rejected: "red",
// };

// window.INDICATOR_COLOR_HEX = window.INDICATOR_COLOR_HEX || {
// 	cyan: { bg: "#E3FBFC", accent: "#00B0C7", text: "#0B5B66" },
// 	yellow: { bg: "#FFF8DE", accent: "#E8B900", text: "#6B5300" },
// 	blue: { bg: "#E5F1FF", accent: "#2490EF", text: "#0B4A8C" },
// 	gray: { bg: "#F1F1F1", accent: "#8D99A6", text: "#4B4B4B" },
// 	orange: { bg: "#FFF0E1", accent: "#FF9A2E", text: "#8A4B00" },
// 	green: { bg: "#E7F9EE", accent: "#22C55E", text: "#166534" },
// 	red: { bg: "#FDE8E8", accent: "#F04438", text: "#912018" },
// };

// // Returns a scrubbed (lowercase, underscored) key for a status, for CSS class names.
// window.ivw_status_key =
// 	window.ivw_status_key ||
// 	function (status) {
// 		return frappe.scrub(status || "scheduled");
// 	};

// // Returns the { bg, accent, text } colour set for a given status.
// window.ivw_color_for_status =
// 	window.ivw_color_for_status ||
// 	function (status) {
// 		const indicator = window.STATUS_INDICATOR_MAP[status] || "gray";
// 		return window.INDICATOR_COLOR_HEX[indicator] || window.INDICATOR_COLOR_HEX.gray;
// 	};

// // Returns the currently selected marketing_link, resolving and persisting a
// // default via the server when nothing is selected yet. Concurrent callers
// // within the same tick share one in-flight request.
// window.__ivwResolvePromise = null;

// window.ivw_ensure_marketing_param = function () {
// 	const existing = window.InterviewMarketingFilter.get();
// 	if (existing) return Promise.resolve(existing);

// 	if (window.__ivwResolvePromise) return window.__ivwResolvePromise;

// 	window.__ivwResolvePromise = frappe
// 		.call({
// 			method:
// 				"verp_staffing.marketing.doctype.interview.interview.get_default_marketing_customer_options",
// 			args: { param: "" },
// 		})
// 		.then((r) => {
// 			window.__ivwResolvePromise = null;
// 			const options = r.message || [];
// 			if (!options.length) return null;
// 			const value = options[0].value;
// 			window.InterviewMarketingFilter.set(value);
// 			return value;
// 		})
// 		.catch(() => {
// 			window.__ivwResolvePromise = null;
// 			return null;
// 		});

// 	return window.__ivwResolvePromise;
// };

// // Normalizes frappe.call's object-style and positional-style invocations
// // into a single { method, args, callback } shape.
// function ivw_normalize_call_args(call_args) {
// 	const first = call_args[0];
// 	if (first && typeof first === "object" && !Array.isArray(first)) {
// 		return { method: first.method, args: first.args, callback: first.callback };
// 	}
// 	if (typeof first === "string") {
// 		return { method: first, args: call_args[1], callback: call_args[2] };
// 	}
// 	return { method: null, args: null, callback: null };
// }

// // Adds a marketing_link filter to an existing filters payload (parsing it
// // first if it's a JSON string) unless one is already present.
// function ivw_merge_marketing_filter(existing_filters, param) {
// 	let filters = existing_filters;
// 	try {
// 		filters = typeof filters === "string" ? JSON.parse(filters) : filters || [];
// 	} catch (e) {
// 		filters = [];
// 	}
// 	if (!Array.isArray(filters)) filters = [];
// 	if (!param) return filters;

// 	const already_has = filters.some(
// 		(f) => Array.isArray(f) && (f[0] === "marketing_link" || f[1] === "marketing_link"),
// 	);
// 	return already_has ? filters : filters.concat([["marketing_link", "=", param]]);
// }

// // Wraps frappe.call so every Interview-fetching call (List, Kanban, Report
// // view, Gantt, Calendar) resolves a marketing_link and injects it into the
// // request. Gantt's reportview.get shape is rerouted to
// // get_interview_gantt_rows and its results cached into window.__interviewGanttMap.
// (function patch_frappe_call_for_interview() {
// 	if (frappe.__interview_call_patched) return;
// 	frappe.__interview_call_patched = true;

// 	const original_call = frappe.call;

// 	frappe.call = function (...call_args) {
// 		const { method, args, callback } = ivw_normalize_call_args(call_args);

// 		const is_calendar_events =
// 			method ===
// 			"verp_staffing.marketing.doctype.interview.interview.get_interview_round_events";

// 		const is_interview_doctype_fetch =
// 			args &&
// 			args.doctype === "Interview" &&
// 			(method === "frappe.desk.reportview.get" ||
// 				method === "frappe.client.get_list" ||
// 				method === "frappe.client.get_count");

// 		const is_gantt_reportview =
// 			is_interview_doctype_fetch &&
// 			typeof args.order_by === "string" &&
// 			args.order_by.indexOf("`start`") !== -1;

// 		if (!is_calendar_events && !is_interview_doctype_fetch) {
// 			return original_call.apply(frappe, call_args);
// 		}

// 		return window.ivw_ensure_marketing_param().then((param) => {
// 			if (!param) {
// 				frappe.show_alert(
// 					{
// 						message: __("Select a customer to view interviews."),
// 						indicator: "orange",
// 					},
// 					4,
// 				);
// 				const empty = { message: [] };
// 				if (callback) callback(empty);
// 				return empty;
// 			}

// 			if (is_calendar_events) {
// 				const merged_args = Object.assign({}, args, {
// 					filters: JSON.stringify(
// 						ivw_merge_marketing_filter(args && args.filters, param),
// 					),
// 					marketing_link: param,
// 				});
// 				return original_call.call(frappe, { method, args: merged_args, callback });
// 			}

// 			const merged_filters = JSON.stringify(
// 				ivw_merge_marketing_filter(args.filters, param),
// 			);

// 			if (is_gantt_reportview) {
// 				return original_call
// 					.call(frappe, {
// 						method: "verp_staffing.marketing.doctype.interview.interview.get_interview_gantt_rows",
// 						args: { filters: merged_filters },
// 					})
// 					.then((r) => {
// 						const rows = r.message || [];
// 						window.__interviewGanttMap = {};
// 						rows.forEach((row) => {
// 							window.__interviewGanttMap[row.name] = {
// 								interview: row.interview,
// 								company: row.company,
// 								role: row.role,
// 								round: row.round,
// 								status: row.status,
// 								date_of_interview: row.date_of_interview,
// 								from_time: row.from_time,
// 								to_time: row.to_time,
// 								edt_est: row.edt_est,
// 							};
// 						});
// 						const result = { message: rows };
// 						if (callback) callback(result);
// 						return result;
// 					});
// 			}

// 			return original_call.call(frappe, {
// 				method,
// 				args: Object.assign({}, args, { filters: merged_filters }),
// 				callback,
// 			});
// 		});
// 	};
// })();



// ---------------------------------------------------------------------
// interview_common.js
//
// Single source of truth shared by interview_list.js and
// interview_calendar.js. Load this FIRST (hooks.py app_include_js).
//
// BREAKING CHANGE from the single-customer version: the selected
// customer is now an ARRAY of Marketing names, not one value. The
// sessionStorage key was renamed (interview_marketing_links) so a
// leftover single-value session from before this update can't be
// misread as a one-item array by accident. The URL query param name is
// kept as `marketing_link` for bookmark compatibility, but its value is
// now a comma-separated list.
// ---------------------------------------------------------------------

// interview_common.js
window.InterviewMarketingFilter =
	window.InterviewMarketingFilter ||
	(function () {
		// Renamed from "marketing_link" to "ivw_customers". The old name
		// collided with the real Interview.marketing_link field, which
		// Frappe's own list/gantt/calendar controllers ALSO serialize into
		// the URL (in a totally different JSON shape) any time a filter
		// exists on that field. Two writers fighting over one query key,
		// in two incompatible formats, is what produced the nested
		// ["in",[...]] garbage you're seeing in the address bar.
		const STORAGE_KEY = "interview_marketing_links_v2";
		const URL_PARAM = "ivw_customers";

		function encode_list(list) {
			return list.map(encodeURIComponent).join(",");
		}
		function decode_list(str) {
			// If it looks like JSON, it isn't ours. Refuse to comma-split
			// it instead of shredding it into garbage fragments.
			if (!str || str.trim().startsWith("[") || str.trim().startsWith("{")) return [];
			return str
				.split(",")
				.map((s) => decodeURIComponent(s.trim()))
				.filter(Boolean);
		}

		return {
			get() {
				const from_url = new URLSearchParams(window.location.search).get(URL_PARAM);
				if (from_url) {
					const list = decode_list(from_url);
					if (list.length) {
						try {
							sessionStorage.setItem(STORAGE_KEY, JSON.stringify(list));
						} catch (e) {}
						return list;
					}
				}

				let from_storage = [];
				try {
					const raw = sessionStorage.getItem(STORAGE_KEY);
					from_storage = raw ? JSON.parse(raw) : [];
					if (!Array.isArray(from_storage)) from_storage = [];
				} catch (e) {
					from_storage = [];
				}
				if (from_storage.length) {
					window.InterviewMarketingFilter.set(from_storage);
				}
				return from_storage;
			},

			set(list) {
				if (!Array.isArray(list) || !list.length) return;
				try {
					sessionStorage.setItem(STORAGE_KEY, JSON.stringify(list));
				} catch (e) {}
				const url = new URL(window.location.href);
				url.searchParams.set(URL_PARAM, encode_list(list));
				window.history.replaceState({}, "", url);
			},
		};
	})();

window.STATUS_INDICATOR_MAP = window.STATUS_INDICATOR_MAP || {
	Scheduled: "cyan",
	Today: "yellow",
	Completed: "blue",
	Cancelled: "gray",
	Rescheduled: "orange",
	"Get The Offer": "green",
	Rejected: "red",
};

window.INDICATOR_COLOR_HEX = window.INDICATOR_COLOR_HEX || {
	cyan: { bg: "#E3FBFC", accent: "#00B0C7", text: "#0B5B66" },
	yellow: { bg: "#FFF8DE", accent: "#E8B900", text: "#6B5300" },
	blue: { bg: "#E5F1FF", accent: "#2490EF", text: "#0B4A8C" },
	gray: { bg: "#F1F1F1", accent: "#8D99A6", text: "#4B4B4B" },
	orange: { bg: "#FFF0E1", accent: "#FF9A2E", text: "#8A4B00" },
	green: { bg: "#E7F9EE", accent: "#22C55E", text: "#166534" },
	red: { bg: "#FDE8E8", accent: "#F04438", text: "#912018" },
};

window.ivw_status_key =
	window.ivw_status_key ||
	function (status) {
		return frappe.scrub(status || "scheduled");
	};

window.ivw_color_for_status =
	window.ivw_color_for_status ||
	function (status) {
		const indicator = window.STATUS_INDICATOR_MAP[status] || "gray";
		return window.INDICATOR_COLOR_HEX[indicator] || window.INDICATOR_COLOR_HEX.gray;
	};

// ---------------------------------------------------------------------
// Resolves the selected customer LIST no matter which view asks first.
//
// Default when nothing is selected yet: ALL customers the user is
// assigned to (a true "select all"), fetched from
// get_assigned_marketing_customers — the same endpoint that populates
// the multi-select dialog's checkbox list. This replaces the old
// "just pick the most-recently-created one" default.
// ---------------------------------------------------------------------
window.__ivwResolvePromise = null;

window.ivw_ensure_marketing_param = function () {
	const existing = window.InterviewMarketingFilter.get();
	if (existing && existing.length) return Promise.resolve(existing);

	if (window.__ivwResolvePromise) return window.__ivwResolvePromise;

	window.__ivwResolvePromise = frappe
		.call({
			method:
				"verp_staffing.marketing.doctype.interview.interview.get_assigned_marketing_customers",
		})
		.then((r) => {
			window.__ivwResolvePromise = null;
			const options = r.message || [];
			if (!options.length) return [];
			const values = options.map((o) => o.value);
			window.InterviewMarketingFilter.set(values);
			return values;
		})
		.catch(() => {
			window.__ivwResolvePromise = null;
			return [];
		});

	return window.__ivwResolvePromise;
};

function ivw_normalize_call_args(call_args) {
	const first = call_args[0];
	if (first && typeof first === "object" && !Array.isArray(first)) {
		return { method: first.method, args: first.args, callback: first.callback };
	}
	if (typeof first === "string") {
		return { method: first, args: call_args[1], callback: call_args[2] };
	}
	return { method: null, args: null, callback: null };
}

// Merges an IN-list marketing_link filter into an existing filters
// payload, REPLACING any prior marketing_link filter rather than
// skipping when one is already present — the selection can change
// between calls (user checks/unchecks customers), so the freshest
// selection must always win, not the first one seen.
function ivw_merge_marketing_filter(existing_filters, param_list) {
	let filters = existing_filters;
	try {
		filters = typeof filters === "string" ? JSON.parse(filters) : filters || [];
	} catch (e) {
		filters = [];
	}
	if (!Array.isArray(filters)) filters = [];
	if (!param_list || !param_list.length) return filters;

	filters = filters.filter(
		(f) => !(Array.isArray(f) && (f[0] === "marketing_link" || f[1] === "marketing_link")),
	);
	filters.push(["marketing_link", "in", param_list]);
	return filters;
}

function ivw_is_kanban_route() {
	const route = (frappe.get_route && frappe.get_route()) || [];
	return route[0] === "List" && route[1] === "Interview" && route[2] === "Kanban";
}

// ---------------------------------------------------------------------
// ONE frappe.call gate for every Interview-fetching call, regardless of
// which view issued it. See prior version's comments for why doctype-
// based matching (not order_by fingerprinting) is what makes this cover
// List/Kanban/Report/Gantt/Calendar uniformly.
//
// Kanban-specific addition: the very FIRST load on the Kanban route gets
// its order forced to `creation desc` and its page size capped, so the
// board opens already populated but bounded — interview_list.js's
// per-column scroll listeners take over from there for further pages.
// ---------------------------------------------------------------------
(function patch_frappe_call_for_interview() {
	if (frappe.__interview_call_patched) return;
	frappe.__interview_call_patched = true;

	const KANBAN_INITIAL_PAGE_LENGTH = 100;

	const original_call = frappe.call;

	frappe.call = function (...call_args) {
		const { method, args, callback } = ivw_normalize_call_args(call_args);

		const is_calendar_events =
			method ===
			"verp_staffing.marketing.doctype.interview.interview.get_interview_round_events";

		const is_interview_doctype_fetch =
			args &&
			args.doctype === "Interview" &&
			(method === "frappe.desk.reportview.get" ||
				method === "frappe.client.get_list" ||
				method === "frappe.client.get_count");

		const is_gantt_reportview =
			is_interview_doctype_fetch &&
			typeof args.order_by === "string" &&
			args.order_by.indexOf("`start`") !== -1;

		if (!is_calendar_events && !is_interview_doctype_fetch) {
			return original_call.apply(frappe, call_args);
		}

		return window.ivw_ensure_marketing_param().then((param_list) => {
			if (!param_list || !param_list.length) {
				frappe.show_alert(
					{
						message: __("Select at least one customer to view interviews."),
						indicator: "orange",
					},
					4,
				);
				const empty = { message: [] };
				if (callback) callback(empty);
				return empty;
			}

			if (is_calendar_events) {
				const merged_args = Object.assign({}, args, {
					filters: JSON.stringify(
						ivw_merge_marketing_filter(args && args.filters, param_list),
					),
					marketing_link: JSON.stringify(param_list),
				});
				return original_call.call(frappe, { method, args: merged_args, callback });
			}

			const merged_filters_array = ivw_merge_marketing_filter(args.filters, param_list);
			const merged_filters = JSON.stringify(merged_filters_array);

			if (is_gantt_reportview) {
				return original_call
					.call(frappe, {
						method: "verp_staffing.marketing.doctype.interview.interview.get_interview_gantt_rows",
						args: { filters: merged_filters },
					})
					.then((r) => {
						const rows = r.message || [];
						window.__interviewGanttMap = {};
						rows.forEach((row) => {
							window.__interviewGanttMap[row.name] = {
								interview: row.interview,
								company: row.company,
								role: row.role,
								round: row.round,
								status: row.status,
								date_of_interview: row.date_of_interview,
								from_time: row.from_time,
								to_time: row.to_time,
								edt_est: row.edt_est,
							};
						});
						const result = { message: rows };
						if (callback) callback(result);
						return result;
					});
			}

			const merged_args = Object.assign({}, args, { filters: merged_filters });

			// First Kanban load only — bound it and sort it, so the board
			// opens already showing the latest cards per column instead of
			// whatever Frappe's own default ordering/limit would return.
			// Subsequent per-column pages are fetched separately by
			// interview_list.js's scroll listeners via frappe.client.get_list
			// with an explicit limit_start, bypassing this branch (that
			// call already carries its own order_by/limit_page_length).
			if (ivw_is_kanban_route() && !("limit_start" in (args || {}))) {
				merged_args.order_by = "creation desc";
				merged_args.page_length = KANBAN_INITIAL_PAGE_LENGTH;
				merged_args.limit_page_length = KANBAN_INITIAL_PAGE_LENGTH;
			}

			return original_call.call(frappe, { method, args: merged_args, callback });
		});
	};
})();