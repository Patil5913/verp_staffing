window.InterviewMarketingFilter =
	window.InterviewMarketingFilter ||
	(function () {
		const STORAGE_KEY = "interview_marketing_links";
		const URL_PARAM = "marketing_link";

		// Serializes a list of customer values into the same ["in", [...]] shape
		function encode_list(list) {
			return JSON.stringify(["in", list]);
		}

		function decode_list(str) {
			if (!str) return [];
			let parsed;
			try {
				parsed = JSON.parse(str);
			} catch (e) {
				return [];
			}
			if (Array.isArray(parsed) && parsed.length === 2 && Array.isArray(parsed[1])) {
				return parsed[1].filter((v) => typeof v === "string" && v);
			}
			if (Array.isArray(parsed)) {
				return parsed.filter((v) => typeof v === "string" && v);
			}
			return [];
		}

		return {
			// Resolves the current selection, preferring the URL param, falling
			// back to sessionStorage, and re-syncing whichever source wins back
			// into the other so both stay consistent.
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

			// Replaces the current selection in both sessionStorage and the URL
			// with the given list, so exactly one selection ever exists at a time.
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

// Looks up the bg/accent/text color set for a given status via the indicator-color map.
window.ivw_color_for_status =
	window.ivw_color_for_status ||
	function (status) {
		const indicator = window.STATUS_INDICATOR_MAP[status] || "gray";
		return window.INDICATOR_COLOR_HEX[indicator] || window.INDICATOR_COLOR_HEX.gray;
	};

window.__ivwResolvePromise = null;

// Resolves the selected-customer list for any caller: returns the existing
// selection immediately if one is set, otherwise fetches every customer the
// user is assigned to, stores it as the default selection, and returns that
// — deduplicating concurrent callers onto a single in-flight request.
window.ivw_ensure_marketing_param = function () {
	const existing = window.InterviewMarketingFilter.get();
	if (existing && existing.length) return Promise.resolve(existing);

	if (window.__ivwResolvePromise) return window.__ivwResolvePromise;

	window.__ivwResolvePromise = frappe
		.call({
			method: "verp_staffing.marketing.doctype.interview.interview.get_assigned_marketing_customers",
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

// Normalizes the different call signatures frappe.call() accepts (a single
// options object, or positional method/args/callback arguments) into one
// consistent { method, args, callback } shape.
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

// Returns a copy of the given filters with any existing marketing_link
// filter replaced by an IN filter for the current customer selection.
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

// Returns true when the current route is the Interview Kanban view.
function ivw_is_kanban_route() {
	const route = (frappe.get_route && frappe.get_route()) || [];
	return route[0] === "List" && route[1] === "Interview" && route[2] === "Kanban";
}

// Installs a one-time patch on frappe.call so every Interview-fetching
// request (list/report views, counts, calendar events, and the gantt
// report-view) is routed through the current customer selection: it waits
// for the selection to resolve, injects it as an IN filter (or blocks the
// request with a prompt if nothing is selected), redirects gantt-ordered
// report-view calls to the dedicated gantt-rows endpoint, and applies a
// bounded initial page size for the first Kanban load.
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
								time_zone: row.time_zone,
								customer: row.customer,
							};
						});
						const result = { message: rows };
						if (callback) callback(result);
						return result;
					});
			}

			const merged_args = Object.assign({}, args, { filters: merged_filters });

			if (ivw_is_kanban_route() && !("limit_start" in (args || {}))) {
				merged_args.order_by = "creation desc";
				merged_args.page_length = KANBAN_INITIAL_PAGE_LENGTH;
				merged_args.limit_page_length = KANBAN_INITIAL_PAGE_LENGTH;
			}

			return original_call.call(frappe, { method, args: merged_args, callback });
		});
	};
})();