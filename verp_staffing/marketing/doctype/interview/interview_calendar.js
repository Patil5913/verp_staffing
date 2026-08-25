// ---------------------------------------------------------------------
// Shared marketing_link filter persistence — identical block exists in
// the sibling file (interview_list.js / interview_calendar.js). Guarded
// so whichever loads first initializes it.
//
// WHY: Frappe's List/Kanban/Gantt/Calendar view-switcher changes the URL
// PATH (.../view/kanban/Interview vs .../view/list/Interview) but does
// NOT preserve the existing query string. Reading marketing_link purely
// from window.location.search — which every prior version of this logic
// did — silently returns null the moment the user switches view type,
// even though their selected customer never changed. This adds a
// sessionStorage fallback so the value survives that URL loss, and syncs
// the URL back from storage whenever possible so deep-linking still works.
// ---------------------------------------------------------------------
if (!window.InterviewMarketingFilter) {
	const STORAGE_KEY = "interview_marketing_link";

	window.InterviewMarketingFilter = {
		get() {
			const from_url = new URLSearchParams(window.location.search).get("marketing_link");
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
}

frappe.views.calendar["Interview"] = {
	field_map: {
		start: "start",
		end: "end",
		id: "name",
		title: "subject",
		allDay: "allDay",
		status: "status",
		color: "color",
	},
	filters: [
		{ fieldtype: "Data", fieldname: "company", label: __("Company") },
		{ fieldtype: "Data", fieldname: "role", label: __("Role") },
		{
			fieldtype: "Link",
			fieldname: "status",
			label: __("Status"),
			options: "Interview Status",
		},
	],
	get_events_method:
		"verp_staffing.marketing.doctype.interview.interview.get_interview_round_events",
	// NEW — passed straight through to FullCalendar by Frappe's calendar
	// wrapper. This is the supported extension point for customizing how
	// an event renders, unlike Gantt (which has no equivalent hook and
	// needed the MutationObserver approach instead).
	options: {
		eventRender: function (event, element, view) {
			render_interview_calendar_card(event, element, view);
		},
		// eventRender fires before FullCalendar finishes laying out
		// concurrent/overlapping events, so the element's real width isn't
		// known yet at that point — two rounds at the same time slot only
		// get their final (halved) width applied afterward. This second
		// hook measures the settled size and applies density classes so
		// the CSS can adapt instead of the card overflowing its neighbor.
		eventAfterRender: function (event, element, view) {
			adjust_interview_calendar_card_density(element);
		},
	},
};

frappe.views.calendar["Interview"] = Object.assign({}, frappe.views.calendar["Interview"], {
	gantt: {
		field_map: {
			start: "start",
			end: "end",
			id: "name",
			title: "subject",
			progress: "progress",
		},
	},
});

window.__interviewGanttMap = window.__interviewGanttMap || {};

const STATUS_INDICATOR_MAP = {
	Scheduled: "cyan",
	Today: "yellow",
	Completed: "blue",
	Cancelled: "gray",
	Rescheduled: "orange",
	"Get The Offer": "green",
	Rejected: "red",
};

// indicator colour name -> card background / accent / text colours
const INDICATOR_COLOR_HEX = {
	cyan: { bg: "#E3FBFC", accent: "#00B0C7", text: "#0B5B66" },
	yellow: { bg: "#FFF8DE", accent: "#E8B900", text: "#6B5300" },
	blue: { bg: "#E5F1FF", accent: "#2490EF", text: "#0B4A8C" },
	gray: { bg: "#F1F1F1", accent: "#8D99A6", text: "#4B4B4B" },
	orange: { bg: "#FFF0E1", accent: "#FF9A2E", text: "#8A4B00" },
	green: { bg: "#E7F9EE", accent: "#22C55E", text: "#166534" },
	red: { bg: "#FDE8E8", accent: "#F04438", text: "#912018" },
};

function ivw_status_key(status) {
	return frappe.scrub(status || "scheduled");
}

function ivw_color_for_status(status) {
	const indicator = STATUS_INDICATOR_MAP[status] || "gray";
	return INDICATOR_COLOR_HEX[indicator] || INDICATOR_COLOR_HEX.gray;
}

function ivw_on_interview_gantt_route() {
	const route = frappe.get_route ? frappe.get_route() : [];
	return route[0] === "List" && route[1] === "Interview" && route[2] === "Gantt";
}

// ---- Inject card + status-colour CSS once ----
(function inject_interview_gantt_styles() {
	if (document.getElementById("interview-gantt-styles")) return;
	const style = document.createElement("style");
	style.id = "interview-gantt-styles";

	let status_rules = "";
	Object.keys(STATUS_INDICATOR_MAP).forEach((status) => {
		const key = ivw_status_key(status);
		const c = ivw_color_for_status(status);
		status_rules += `
			.ivw-card.ivw-status-${key} { background: ${c.bg}; border-left: 3px solid ${c.accent}; }
			.ivw-card.ivw-status-${key} .ivw-dot { background: ${c.accent}; }
			.ivw-card.ivw-status-${key} .ivw-company,
			.ivw-card.ivw-status-${key} .ivw-status-text { color: ${c.text}; }
		`;
	});

	style.textContent = `
		/* hide the default frappe-gantt bar + label — we render our own card */
		.gantt .bar-wrapper .bar { opacity: 0; }
		.gantt .bar-wrapper .bar-label { display: none; }
		.gantt .bar-wrapper { cursor: pointer; }

		/* Today marker — the default is a very light yellow band that's easy
		   to miss against the row's own alternating background. Give it a
		   solid, higher-contrast accent line instead. */
		.gantt .today-highlight {
			background: rgba(255, 82, 82, 0.08) !important;
			border-left: 2px solid #ff5252 !important;
			border-right: 2px solid #ff5252 !important;
		}

		.ivw-card {
			width: 100%;
			height: 100%;
			display: flex;
			flex-direction: column;
			justify-content: center;
			gap: 1px;
			padding: 2px 8px;
			box-sizing: border-box;
			border-radius: 4px;
			background: #F1F1F1;
			overflow: hidden;
			box-shadow: 0 1px 2px rgba(0,0,0,.08);
			transition: box-shadow .12s ease, transform .12s ease;
		}
		.ivw-card:hover { box-shadow: 0 2px 6px rgba(0,0,0,.18); transform: translateY(-1px); }

		.ivw-line1 { display: flex; align-items: baseline; gap: 6px; min-width: 0; line-height: 1.15; }
		.ivw-company {
			font-weight: 600; font-size: 11.5px; color: #1c1c1c;
			white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		}
		.ivw-role {
			font-size: 10.5px; color: #5c5c5c; min-width: 0;
			white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		}

		.ivw-line2, .ivw-line3 {
			display: flex; align-items: center; gap: 5px;
			font-size: 10px; line-height: 1.15; color: #6b6b6b;
			white-space: nowrap; overflow: hidden;
		}
		.ivw-dot { width: 5px; height: 5px; border-radius: 50%; flex: none; background: #8D99A6; }
		.ivw-status-text { font-weight: 600; overflow: hidden; text-overflow: ellipsis; }
		.ivw-sep { opacity: .5; }
		.ivw-time { flex: none; }
		.ivw-tz { flex: none; font-weight: 600; opacity: .75; }
		${status_rules}
	`;
	document.head.appendChild(style);
})();

// ---- Render a full-info card into each bar as frappe-gantt draws it ----
(function watch_interview_gantt_bars() {
	if (window.__interviewGanttObserver) return;

	// Interview rounds are usually an hour or two long against a month-wide
	// timeline, so the underlying bar rect is only a few px wide/tall.
	// The old plain-text label got away with this because SVG <text> isn't
	// clipped by its container. A foreignObject card IS clipped, so we give
	// it a real minimum footprint instead of matching that tiny rect —
	// anchored at the same start x/y the bar would have used.
	const MIN_CARD_WIDTH = 220;
	const MIN_CARD_HEIGHT_FALLBACK = 42;

	function render_card(bar) {
		const id = bar.getAttribute("data-id");
		if (!id) return;
		const info = window.__interviewGanttMap[id];
		if (!info) return;
		if (bar.querySelector(".ivw-fo")) return; // already rendered for this bar

		const rect = bar.querySelector(".bar");
		if (!rect) return;

		const rect_x = parseFloat(rect.getAttribute("x")) || 0;
		const rect_y = parseFloat(rect.getAttribute("y")) || 0;
		const rect_w = parseFloat(rect.getAttribute("width")) || 0;
		const rect_h = parseFloat(rect.getAttribute("height")) || 0;

		// Read the ACTUAL row slot height from the grid rather than assuming
		// a fixed pixel value — Frappe Gantt's row pitch differs by zoom
		// level (Quarter Day / Week / Month / Year all draw different row
		// heights), so a hardcoded MIN_CARD_HEIGHT will fit at one zoom and
		// overlap at another. A small inset keeps a hairline gap between
		// stacked rows instead of touching edge-to-edge.
		const svg = bar.closest("svg");
		const grid_row = svg ? svg.querySelector(".grid-row") : null;
		const row_pitch = grid_row ? parseFloat(grid_row.getAttribute("height")) : 0;
		const ROW_INSET = 4;

		const width = Math.max(rect_w, MIN_CARD_WIDTH);
		const height =
			row_pitch > 0 ? row_pitch - ROW_INSET : Math.max(rect_h, MIN_CARD_HEIGHT_FALLBACK);
		const x = rect_x; // keep the same left edge / start position
		const y = rect_y - (height - rect_h) / 2; // grow evenly, stay centred in the row

		const status = info.status || "Scheduled";
		const status_key = ivw_status_key(status);
		const date_display = info.date_of_interview
			? frappe.datetime.str_to_user
				? frappe.datetime.str_to_user(info.date_of_interview)
				: info.date_of_interview
			: "";

		// Build "from – to (EDT/EST)" — falls back gracefully if either
		// piece is missing rather than showing a dangling separator.
		let time_range = "";
		if (info.from_time) {
			time_range = String(info.from_time).slice(0, 5);
			if (info.to_time) time_range += " – " + String(info.to_time).slice(0, 5);
			if (info.edt_est) time_range += ` (${info.edt_est})`;
		}

		const fo = document.createElementNS("http://www.w3.org/2000/svg", "foreignObject");
		fo.setAttribute("class", "ivw-fo");
		fo.setAttribute("x", x);
		fo.setAttribute("y", y);
		fo.setAttribute("width", width);
		fo.setAttribute("height", height);
		fo.style.overflow = "visible";

		const wrapper = document.createElementNS("http://www.w3.org/1999/xhtml", "div");
		wrapper.className = `ivw-card ivw-status-${status_key}`;
		wrapper.title = [
			`${info.company || ""} — ${info.role || ""}`,
			`Round ${info.round || ""} · ${status}`,
			[date_display, time_range].filter(Boolean).join(" · "),
		].join("\n");

		const esc = frappe.utils.escape_html;
		wrapper.innerHTML = `
			<div class="ivw-line1">
				<span class="ivw-company">${esc(info.company || "")}</span>
				<span class="ivw-role">${esc(info.role || "")}</span>
			</div>
			<div class="ivw-line2">
				<span>Round ${esc(String(info.round || ""))}</span>
				<span class="ivw-sep">·</span>
				<span class="ivw-dot"></span>
				<span class="ivw-status-text">${esc(status)}</span>
			</div>
			<div class="ivw-line3">
				${date_display ? `<span class="ivw-time">${esc(date_display)}</span>` : ""}
				${time_range ? `<span class="ivw-sep">·</span><span class="ivw-time">${esc(time_range)}</span>` : ""}
			</div>
		`;

		fo.appendChild(wrapper);
		bar.appendChild(fo);
	}

	const observer = new MutationObserver((mutations) => {
		if (!ivw_on_interview_gantt_route()) return;

		for (const m of mutations) {
			m.addedNodes.forEach((node) => {
				if (!(node instanceof Element)) return;
				const bars = node.matches?.(".bar-wrapper")
					? [node]
					: Array.from(node.querySelectorAll?.(".bar-wrapper") || []);
				bars.forEach(render_card);
			});
		}
	});

	observer.observe(document.body, { childList: true, subtree: true });
	window.__interviewGanttObserver = observer;
})();

(function patch_interview_gantt_click() {
	if (window.__interviewGanttClickPatched) return;
	window.__interviewGanttClickPatched = true;

	document.addEventListener(
		"click",
		(e) => {
			if (!ivw_on_interview_gantt_route()) return;
			const bar = e.target.closest?.(".bar-wrapper");
			if (!bar) return;
			const id = bar.getAttribute("data-id");
			if (!id) return;
			const info = window.__interviewGanttMap[id];
			if (!info) return; // unknown id: let default behaviour happen, don't break silently

			e.preventDefault();
			e.stopPropagation();
			frappe.set_route("Form", "Interview", info.interview);
		},
		true, // capture phase: run before Gantt's own click handler
	);
})();

(function watch_interview_gantt_today_marker() {
	if (window.__interviewGanttTodayObserver) return;

	function recolor_today_marker() {
		if (!ivw_on_interview_gantt_route()) return;

		document
			.querySelectorAll(
				".gantt .today-highlight, .gantt rect.today-highlight, .gantt .holiday-highlight.today, svg .today-highlight",
			)
			.forEach((el) => {
				el.style.setProperty("fill", "rgba(118, 51, 233, 0.14)", "important");
				el.style.setProperty("stroke", "#7b36f4", "important");
				el.style.setProperty("stroke-width", "2", "important");
			});
	}

	const observer = new MutationObserver(() => recolor_today_marker());
	observer.observe(document.body, { childList: true, subtree: true });
	window.__interviewGanttTodayObserver = observer;
})();

(function watch_interview_gantt_empty_state() {
	if (window.__interviewGanttEmptyObserver) return;

	function customize_empty_state() {
		if (!ivw_on_interview_gantt_route()) return;

		document.querySelectorAll(".no-result, .msg-box").forEach((box) => {
			if (box.dataset.ivwEmptyPatched) return;
			if (!(box.textContent || "").includes("No Interview found")) return;

			box.dataset.ivwEmptyPatched = "1";

			const message_el = box.querySelector("p");
			if (message_el) {
				message_el.textContent = __(
					"No interview rounds found for the selected customer.",
				);
			}

			box.querySelectorAll(".btn-new-doc").forEach((btn) => {
				btn.style.display = "none";
			});
		});
	}

	const observer = new MutationObserver(() => customize_empty_state());
	observer.observe(document.body, { childList: true, subtree: true });
	window.__interviewGanttEmptyObserver = observer;
})();

// ---------------------------------------------------------------------
// frappe-gantt (vendor library, not our code) throws when given a
// genuinely empty task list — it tries to compute the timeline's date
// range from the min/max task dates, gets null, and calls .getFullYear()
// on it without a guard. This is a real bug in the third-party library,
// triggered exactly when a filtered Gantt view correctly has zero rows
// (e.g. a customer with no interview rounds yet).
//
// Left unhandled, this uncaught exception aborts whatever
// frappe.run_serially chain is currently running, which can leave later
// steps in that same navigation cycle (including other views' init code)
// in a partially-run state. Wrapping render_gantt in try/catch contains
// the failure to Gantt's own rendering step and shows our own empty
// message instead of letting it escape and disrupt anything downstream.
// ---------------------------------------------------------------------
(function patch_gantt_empty_state_crash() {
	function apply_patch() {
		const proto = frappe.views && frappe.views.GanttView && frappe.views.GanttView.prototype;
		if (!proto || typeof proto.render_gantt !== "function" || proto.render_gantt.__ivw_patched) {
			return false;
		}

		const original_render_gantt = proto.render_gantt;
		proto.render_gantt = function (...args) {
			try {
				return original_render_gantt.apply(this, args);
			} catch (e) {
				console.warn(
					"[Interview Gantt] vendor gantt library failed (likely zero-task edge case) — showing fallback empty state instead of throwing.",
					e
				);
				if (this.$result) {
					this.$result.html(`
						<div class="text-muted text-center mt-5">
							${__("No interview rounds found for the selected customer.")}
						</div>
					`);
				}
			}
		};
		proto.render_gantt.__ivw_patched = true;
		return true;
	}

	// GanttView's class may not be loaded/registered yet at the moment
	// this script evaluates — retry briefly rather than assuming timing.
	if (!apply_patch()) {
		const interval = setInterval(() => {
			if (apply_patch()) clearInterval(interval);
		}, 300);
		setTimeout(() => clearInterval(interval), 5000);
	}
})();


function ivw_on_interview_calendar_route() {
	const route = frappe.get_route ? frappe.get_route() : [];
	return route[0] === "List" && route[1] === "Interview" && route[2] === "Calendar";
}

// ---------------------------------------------------------------------
// Force a genuine refetch when the Calendar route is active and the
// selected customer differs from what's currently rendered.
//
// WHY A PERSISTENT MutationObserver (not a route-change poll): the
// customer can also change via the "Select Customer" dialog while
// already sitting on Calendar — no route change fires in that case, so
// anything keyed only off frappe.router "change" would miss it. An
// observer watching the whole document catches every DOM update
// regardless of what triggered it, same pattern already proven for the
// Gantt bar renderer and today-marker recolor in this file.
//
// WHY TARGET ".fc" SPECIFICALLY: FullCalendar's jQuery plugin attaches
// its own "fc" class to whichever exact element .fullCalendar() was
// called on. Calling .fullCalendar(method) on any other element (a
// wrapper, a parent, a guessed class name) either throws or silently
// no-ops — it will never find the plugin instance. ".fc" is guaranteed
// present on that exact element across FullCalendar v3 installs,
// unlike wrapper class names which can vary by Frappe version.
// ---------------------------------------------------------------------
(function force_interview_calendar_refetch_on_route() {
	if (window.__interviewCalendarRefetchObserver) return;

	let last_fetched_marketing = null;

	function try_refetch() {
		if (!ivw_on_interview_calendar_route()) return;

		const current = ivw_get_marketing_param();
		if (current === last_fetched_marketing) return; // nothing actually changed

		const $fc = $(".fc").first();
		if (!$fc.length) return; // plugin not mounted on this pass yet

		try {
			$fc.fullCalendar("refetchEvents");
			last_fetched_marketing = current;
		} catch (e) {
			// Plugin present in DOM but not yet initialized — next
			// mutation will retry.
		}
	}

	const observer = new MutationObserver(() => try_refetch());
	observer.observe(document.body, { childList: true, subtree: true });
	window.__interviewCalendarRefetchObserver = observer;

	// Also reset the "last known" value the instant we leave the route,
	// so returning to Calendar later always re-checks rather than
	// trusting a stale comparison from a previous visit.
	frappe.router.on("change", () => {
		if (!ivw_on_interview_calendar_route()) {
			last_fetched_marketing = null;
		}
	});
})();

function ivw_get_marketing_param() {
	return window.InterviewMarketingFilter.get();
}

// Frappe's Calendar `filters` config only knows about fields you declare
// in frappe.views.calendar[...].filters (company/role/status here) — it
// has no concept of marketing_link, so it never includes it in the
// payload sent to get_events_method, regardless of what's in the URL.
// This merges it in unconditionally, right before the request goes out,
// so correctness never depends on Frappe's own filter bookkeeping.
function ivw_merge_marketing_filter(existing_filters) {
	let filters = existing_filters;
	try {
		filters = typeof filters === "string" ? JSON.parse(filters) : filters || [];
	} catch (e) {
		filters = [];
	}
	if (!Array.isArray(filters)) filters = [];

	const param = ivw_get_marketing_param();
	if (!param) return filters;

	const already_has = filters.some(
		(f) => Array.isArray(f) && (f[0] === "marketing_link" || f[1] === "marketing_link"),
	);
	return already_has ? filters : filters.concat([["marketing_link", "=", param]]);
}

function ivw_normalize_call_args(call_args) {
	// frappe.call supports two invocation styles — object-style and
	// positional-style. Different Frappe view classes use different
	// ones internally (this is the exact same ambiguity that broke
	// get_list_settings earlier). Detecting only one style is why the
	// Gantt branch worked while the Calendar branch silently never
	// matched at all.
	const first = call_args[0];
	if (first && typeof first === "object" && !Array.isArray(first)) {
		return { style: "object", opts: first, method: first.method, args: first.args, callback: first.callback };
	}
	if (typeof first === "string") {
		return { style: "positional", opts: null, method: first, args: call_args[1], callback: call_args[2] };
	}
	return { style: "unknown", opts: null, method: null, args: null, callback: null };
}

(function override_interview_gantt_fetch() {
	if (frappe.__interview_gantt_call_patched) return;
	frappe.__interview_gantt_call_patched = true;

	const original_call = frappe.call;

	frappe.call = function (...call_args) {
		const { method, args, callback } = ivw_normalize_call_args(call_args);

		// ---- Calendar: get_interview_round_events ----
		if (method === "verp_staffing.marketing.doctype.interview.interview.get_interview_round_events") {
			const merged_args = Object.assign({}, args, {
				filters: JSON.stringify(ivw_merge_marketing_filter(args && args.filters)),
			});
			const param = ivw_get_marketing_param();
			if (param) merged_args.marketing_link = param; // explicit, unambiguous — independent of filters shape

			return original_call.call(frappe, { method, args: merged_args, callback });
		}

		// ---- Gantt: the doomed reportview.get call (unchanged logic,
		// now reachable regardless of calling convention) ----
		const is_doomed_reportview_call =
			method === "frappe.desk.reportview.get" &&
			args &&
			args.doctype === "Interview" &&
			typeof args.order_by === "string" &&
			args.order_by.indexOf("`start`") !== -1;

		if (ivw_on_interview_gantt_route() && is_doomed_reportview_call) {
			const merged_filters = ivw_merge_marketing_filter(args.filters);

			return original_call
				.call(frappe, {
					method: "verp_staffing.marketing.doctype.interview.interview.get_interview_gantt_rows",
					args: { filters: JSON.stringify(merged_filters) },
				})
				.then((r) => {
					const rows = r.message || [];
					window.__interviewGanttMap = {};
					rows.forEach((row) => {
						window.__interviewGanttMap[row.name] = {
							interview: row.interview, company: row.company, role: row.role,
							round: row.round, status: row.status,
							date_of_interview: row.date_of_interview,
							from_time: row.from_time, to_time: row.to_time, edt_est: row.edt_est,
						};
					});
					const result = { message: rows };
					if (callback) callback(result);
					return result;
				});
		}

		// ---- Pass-through: forward every other call in the app exactly
		// as originally invoked, untouched. ----
		return original_call.apply(frappe, call_args);
	};
})();

// ---------------------------------------------------------------------
// Calendar view — richer event cards via FullCalendar's eventRender hook
// ---------------------------------------------------------------------

function ivwc_format_when(from_time, to_time, edt_est) {
	if (!from_time) return "";
	let range = String(from_time).slice(0, 5);
	if (to_time) range += " – " + String(to_time).slice(0, 5);
	if (edt_est) range += ` (${edt_est})`;
	return range;
}

function render_interview_calendar_card(event, element, view) {
	const props = event.extendedProps || event;

	const status = props.status || "Scheduled";
	const status_key = ivw_status_key(status);
	const company = props.company || "";
	const role = props.role || "";
	const round_no = props.round || "";
	const when = ivwc_format_when(props.from_time, props.to_time, props.edt_est);

	const view_name = (view && view.name) || "";
	const is_compact = view_name === "month" || element.hasClass?.("fc-day-grid-event");

	element.addClass(`ivwc-event ivwc-status-${status_key}`);

	const esc = frappe.utils.escape_html;
	const $el = $(element);
	$el.empty();

	// One shared structure for every view — four clean, separate rows.
	// Month/Week/Day only differ by density class (ivwc-compact vs
	// ivwc-full), which the CSS uses to resize/spacing, never by markup.
	const card_html = `
		<div class="ivwc-card ${is_compact ? "ivwc-compact" : "ivwc-full"}">
			<div class="ivwc-row ivwc-row-company">
				<span class="ivwc-company">${esc(company)}</span>
			</div>
			<div class="ivwc-row ivwc-row-role">
				<span class="ivwc-role">${esc(role)}</span>
			</div>
			<div class="ivwc-row ivwc-row-status">
				<span class="ivwc-round-badge">Round ${esc(String(round_no))}</span>
				<span class="ivwc-dot"></span>
				<span class="ivwc-status-text">${esc(status)}</span>
			</div>
			${
				when
					? `
			<div class="ivwc-row ivwc-row-time">
				<span class="ivwc-time">${esc(when)}</span>
			</div>`
					: ""
			}
		</div>
	`;

	$el.html(card_html);
}

// Applies density classes based on the element's ACTUAL rendered size
// (only known post-layout, not at eventRender time). The CSS in
// inject_interview_calendar_styles reads these classes to decide how much
// content to show and how generously to space it.
function adjust_interview_calendar_card_density(element) {
	const $el = $(element);
	const el = $el.get(0);
	if (!el) return;

	const width = el.offsetWidth;
	const height = el.offsetHeight;

	// Narrow: two+ rounds overlapping the same time slot in Week/Day view
	// halve (or worse) the available width — drop secondary lines rather
	// than let them collide with the neighboring card.
	$el.toggleClass("ivwc-narrow", width > 0 && width < 130);

	// Short: a very brief or zero-duration round gets a tiny slot height —
	// collapse to essentials only.
	$el.toggleClass("ivwc-short", height > 0 && height < 46);

	// Tall: plenty of vertical room (a longer round, or a wide-open Day
	// view slot) — use it, rather than leaving the block half-empty.
	$el.toggleClass("ivwc-tall", height >= 90);
}

(function inject_interview_calendar_styles() {
	if (document.getElementById("interview-calendar-styles")) return;
	const style = document.createElement("style");
	style.id = "interview-calendar-styles";

	let status_rules = "";
	Object.keys(STATUS_INDICATOR_MAP).forEach((status) => {
		const key = ivw_status_key(status);
		const c = ivw_color_for_status(status);
		status_rules += `
			.ivwc-event.ivwc-status-${key} { background: ${c.bg} !important; border: none !important; }
			.ivwc-event.ivwc-status-${key} .ivwc-dot { background: ${c.accent}; }
			.ivwc-event.ivwc-status-${key} .ivwc-company,
			.ivwc-event.ivwc-status-${key} .ivwc-status-text { color: ${c.text}; }
			.ivwc-event.ivwc-status-${key} .ivwc-full,
			.ivwc-event.ivwc-status-${key} .ivwc-compact { border-left: 3px solid ${c.accent}; }
		`;
	});

	style.textContent = `
		.ivwc-event {
			border-radius: 4px;
			overflow: hidden;
			padding: 0 !important;
		}

		.ivwc-card {
			width: 100%;
			box-sizing: border-box;
			overflow: hidden;
			display: flex;
			flex-direction: column;
		}
		.ivwc-row {
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.ivwc-row-status {
			display: flex;
			align-items: center;
			gap: 5px;
		}
		.ivwc-dot { width: 6px; height: 6px; border-radius: 50%; flex: none; background: #8D99A6; }
		.ivwc-sep { opacity: .5; flex: none; }

		/* ---- Month view: compact but every row still present ---- */
		.fc-day-grid-event.ivwc-event {
			white-space: normal !important;
			height: auto !important;
			padding: 0 !important;
			margin-bottom: 2px !important;
		}
		.ivwc-compact {
			gap: 1px;
			padding: 3px 6px;
			line-height: 1.25;
		}
		.ivwc-compact .ivwc-company { font-weight: 600; font-size: 10.5px; }
		.ivwc-compact .ivwc-role { font-size: 9.5px; opacity: .8; }
		.ivwc-compact .ivwc-round-badge { font-size: 9px; font-weight: 700; opacity: .75; }
		.ivwc-compact .ivwc-status-text { font-size: 9px; font-weight: 600; }
		.ivwc-compact .ivwc-time { font-size: 9px; opacity: .65; font-weight: 600; }

		/* ---- Week/Day view: same rows, more room to breathe ---- */
		.ivwc-full {
			gap: 3px;
			padding: 6px 10px;
			height: 100%;
			justify-content: center;
		}
		.ivwc-full .ivwc-company { font-weight: 600; font-size: 12.5px; }
		.ivwc-full .ivwc-role { font-size: 11px; opacity: .75; }
		.ivwc-full .ivwc-round-badge { font-size: 11px; opacity: .85; }
		.ivwc-full .ivwc-status-text { font-size: 11px; font-weight: 600; }
		.ivwc-full .ivwc-time { font-size: 11px; opacity: .75; }

		.fc-time-grid .fc-event.ivwc-event {
			box-sizing: border-box !important;
			box-shadow: inset 0 0 0 1px rgba(255,255,255,.9);
		}

		/* ---- Narrow (overlapping events shrank the width) ---- */
		.ivwc-narrow.ivwc-full { padding: 3px 5px; gap: 0; }
		.ivwc-narrow.ivwc-full .ivwc-row-role { display: none; }
		.ivwc-narrow.ivwc-full .ivwc-company { font-size: 10px; }
		.ivwc-narrow.ivwc-full .ivwc-round-badge,
		.ivwc-narrow.ivwc-full .ivwc-status-text,
		.ivwc-narrow.ivwc-full .ivwc-time { font-size: 9px; }

		/* ---- Short (very brief slot): essentials only ---- */
		.ivwc-short.ivwc-full { padding: 2px 6px; gap: 0; }
		.ivwc-short.ivwc-full .ivwc-row-time { display: none; }

		/* ---- Tall (plenty of vertical room, e.g. Day view) ---- */
		.ivwc-tall.ivwc-full { gap: 5px; padding: 8px 12px; }
		.ivwc-tall.ivwc-full .ivwc-company { font-size: 14px; }
		.ivwc-tall.ivwc-full .ivwc-role { font-size: 12px; }
		.ivwc-tall.ivwc-full .ivwc-round-badge,
		.ivwc-tall.ivwc-full .ivwc-status-text { font-size: 12px; }
		.ivwc-tall.ivwc-full .ivwc-time { font-size: 12px; font-weight: 600; }

		${status_rules}
	`;
	document.head.appendChild(style);
})();
