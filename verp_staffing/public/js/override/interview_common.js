// Persists the selected marketing_link across view switches (URL <-> sessionStorage).
window.InterviewMarketingFilter =
	window.InterviewMarketingFilter ||
	(function () {
		const STORAGE_KEY = "interview_marketing_link";

		return {
			get() {
				const from_url = new URLSearchParams(window.location.search).get(
					"marketing_link",
				);
				if (from_url) {
					try {
						sessionStorage.setItem(STORAGE_KEY, from_url);
					} catch (e) {}
					return from_url;
				}

				let from_storage = null;
				try {
					from_storage = sessionStorage.getItem(STORAGE_KEY);
				} catch (e) {}
				if (from_storage) {
					window.InterviewMarketingFilter.set(from_storage);
				}
				return from_storage;
			},

			set(value) {
				if (!value) return;
				try {
					sessionStorage.setItem(STORAGE_KEY, value);
				} catch (e) {}
				const url = new URL(window.location.href);
				url.searchParams.set("marketing_link", value);
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

// Returns a scrubbed (lowercase, underscored) key for a status, for CSS class names.
window.ivw_status_key =
	window.ivw_status_key ||
	function (status) {
		return frappe.scrub(status || "scheduled");
	};

// Returns the { bg, accent, text } colour set for a given status.
window.ivw_color_for_status =
	window.ivw_color_for_status ||
	function (status) {
		const indicator = window.STATUS_INDICATOR_MAP[status] || "gray";
		return window.INDICATOR_COLOR_HEX[indicator] || window.INDICATOR_COLOR_HEX.gray;
	};

// Returns the currently selected marketing_link, resolving and persisting a
// default via the server when nothing is selected yet. Concurrent callers
// within the same tick share one in-flight request.
window.__ivwResolvePromise = null;

window.ivw_ensure_marketing_param = function () {
	const existing = window.InterviewMarketingFilter.get();
	if (existing) return Promise.resolve(existing);

	if (window.__ivwResolvePromise) return window.__ivwResolvePromise;

	window.__ivwResolvePromise = frappe
		.call({
			method:
				"verp_staffing.marketing.doctype.interview.interview.get_default_marketing_customer_options",
			args: { param: "" },
		})
		.then((r) => {
			window.__ivwResolvePromise = null;
			const options = r.message || [];
			if (!options.length) return null;
			const value = options[0].value;
			window.InterviewMarketingFilter.set(value);
			return value;
		})
		.catch(() => {
			window.__ivwResolvePromise = null;
			return null;
		});

	return window.__ivwResolvePromise;
};

// Normalizes frappe.call's object-style and positional-style invocations
// into a single { method, args, callback } shape.
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

// Adds a marketing_link filter to an existing filters payload (parsing it
// first if it's a JSON string) unless one is already present.
function ivw_merge_marketing_filter(existing_filters, param) {
	let filters = existing_filters;
	try {
		filters = typeof filters === "string" ? JSON.parse(filters) : filters || [];
	} catch (e) {
		filters = [];
	}
	if (!Array.isArray(filters)) filters = [];
	if (!param) return filters;

	const already_has = filters.some(
		(f) => Array.isArray(f) && (f[0] === "marketing_link" || f[1] === "marketing_link"),
	);
	return already_has ? filters : filters.concat([["marketing_link", "=", param]]);
}

// Wraps frappe.call so every Interview-fetching call (List, Kanban, Report
// view, Gantt, Calendar) resolves a marketing_link and injects it into the
// request. Gantt's reportview.get shape is rerouted to
// get_interview_gantt_rows and its results cached into window.__interviewGanttMap.
(function patch_frappe_call_for_interview() {
	if (frappe.__interview_call_patched) return;
	frappe.__interview_call_patched = true;

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

		return window.ivw_ensure_marketing_param().then((param) => {
			if (!param) {
				frappe.show_alert(
					{
						message: __("Select a customer to view interviews."),
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
						ivw_merge_marketing_filter(args && args.filters, param),
					),
					marketing_link: param,
				});
				return original_call.call(frappe, { method, args: merged_args, callback });
			}

			const merged_filters = JSON.stringify(
				ivw_merge_marketing_filter(args.filters, param),
			);

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

			return original_call.call(frappe, {
				method,
				args: Object.assign({}, args, { filters: merged_filters }),
				callback,
			});
		});
	};
})();