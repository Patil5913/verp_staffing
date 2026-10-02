// Gantt + Calendar view customization

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

	options: {
	eventRender: function (event, element, view) {
		render_interview_calendar_card(event, element, view);
	},
	// Position must be corrected BEFORE density classes are computed —
	// otherwise adjust_interview_calendar_card_density reads FullCalendar's
	// native (too-short) height and wrongly marks short interviews as
	// "ivwc-short", hiding the time row that we're about to make room for.
	eventAfterRender: function (event, element, view) {
		correct_interview_calendar_time_position(event, element, view);
		adjust_interview_calendar_card_density(element);
	},
},
};

// Reads a .fc-slats <tr>'s data-time attribute ("HH:MM:SS") as seconds.
function ivwc_slot_seconds(tr) {
	const t = tr.getAttribute("data-time");
	if (!t) return null;
	const [hh, mm, ss] = t.split(":").map(Number);
	return (hh || 0) * 3600 + (mm || 0) * 60 + (ss || 0);
}

// Measures real px-per-second scale of the current time-grid from its own
// slot rows, entirely independent of whatever (possibly TZ-shifted) dates
// FullCalendar itself parsed for event.start/end.
function ivwc_measure_time_grid_scale(time_grid) {
	const rows = Array.from(time_grid.querySelectorAll(".fc-slats tr[data-time]"));
	if (rows.length < 2) return null;

	const first = rows[0];
	const last = rows[rows.length - 1];
	const t0 = ivwc_slot_seconds(first);
	const t1 = ivwc_slot_seconds(last);
	if (t0 === null || t1 === null || t1 === t0) return null;

	const y0 = first.getBoundingClientRect().top;
	const y1 = last.getBoundingClientRect().top;

	return { t0, y0, px_per_sec: (y1 - y0) / (t1 - t0) };
}

function ivwc_time_str_to_seconds(time_str) {
	if (!time_str) return null;
	const [hh, mm, ss] = String(time_str).split(":").map(Number);
	return (hh || 0) * 3600 + (mm || 0) * 60 + (ss || 0);
}

// Overrides the event element's top/height using the RAW (un-converted)
// from_time/to_time, so the box lands on the correct hour row regardless
// of any timezone conversion FullCalendar/Frappe applied to event.start/end.
function correct_interview_calendar_time_position(event, element, view) {
	const view_name = (view && view.name) || "";
	const is_time_grid = view_name === "agendaWeek" || view_name === "agendaDay";
	if (!is_time_grid) return; // month view is date-only, no hour row to fix

	const el = element && element.jquery ? element[0] : element;
	if (!el) return;

	const props = event.extendedProps || event;
	const from_sec = ivwc_time_str_to_seconds(props.from_time);
	if (from_sec === null) return; // nothing to correct for all-day events

	const to_sec = ivwc_time_str_to_seconds(props.to_time);

	const time_grid = el.closest(".fc-time-grid");
	if (!time_grid) return;

	function apply() {
		const scale = ivwc_measure_time_grid_scale(time_grid);
		if (!scale) return false;

		const parent = el.offsetParent || time_grid;
		const parent_top = parent.getBoundingClientRect().top;

		const start_y = scale.y0 + (from_sec - scale.t0) * scale.px_per_sec;
		const end_y =
			to_sec !== null
				? scale.y0 + (to_sec - scale.t0) * scale.px_per_sec
				: start_y + 30 * 60 * scale.px_per_sec; // default 30 min if no to_time

		const duration_height = end_y - start_y;

		const prev_height = el.style.height;
		el.style.height = "auto";
		const content_height = el.scrollHeight;
		el.style.height = prev_height;

		const height = Math.max(duration_height, content_height, 18);

		try {
			el.style.top = start_y - parent_top + "px";
			el.style.height = height + "px";
		} catch (e) {
			return false;
		}
		return true;
	}

	if (apply()) return;

	let tries = 0;
	const MAX_TRIES = 6;
	const RETRY_DELAY_MS = 50;
	const retry = () => {
		tries += 1;
		if (apply() || tries >= MAX_TRIES) return;
		setTimeout(retry, RETRY_DELAY_MS);
	};
	setTimeout(retry, RETRY_DELAY_MS);
}

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

function ivw_on_interview_gantt_route() {
	const route = (frappe.get_route && frappe.get_route()) || [];
	return route[0] === "List" && route[1] === "Interview" && route[2] === "Gantt";
}

function ivw_on_interview_calendar_route() {
	const route = (frappe.get_route && frappe.get_route()) || [];
	return route[0] === "List" && route[1] === "Interview" && route[2] === "Calendar";
}

function ivw_on_any_interview_route() {
	const route = (frappe.get_route && frappe.get_route()) || [];
	return route[0] === "List" && route[1] === "Interview";
}

// Resolves the customer selection whenever an Interview route is entered
// (on load and on every route change) and, once resolved, forces the
// FullCalendar instance to refetch its events so it reflects that selection.
(function ensure_default_customer_on_interview_route() {
	function try_resolve() {
		if (!ivw_on_any_interview_route()) return;
		window.ivw_ensure_marketing_param().then((param_list) => {
			if (!param_list || !param_list.length) return;
			const $fc = $(".fc").first();
			if ($fc.length) {
				try {
					$fc.fullCalendar("refetchEvents");
				} catch (e) {}
			}
		});
	}

	frappe.router.on("change", try_resolve);
	try_resolve();
})();

// Injects the Gantt bar/card and per-status color CSS into the document
// head once, generating a status rule block from STATUS_INDICATOR_MAP.
(function inject_interview_gantt_styles() {
	if (document.getElementById("interview-gantt-styles")) return;
	const style = document.createElement("style");
	style.id = "interview-gantt-styles";

	let status_rules = "";
	Object.keys(window.STATUS_INDICATOR_MAP).forEach((status) => {
		const key = ivw_status_key(status);
		const c = ivw_color_for_status(status);
		status_rules += `
			.ivw-card.ivw-status-${key} { background: ${c.bg}; border-left: 3px solid ${c.accent}; }
			.ivw-card.ivw-status-${key} .ivw-dot { background: ${c.accent}; }
			.ivw-card.ivw-status-${key} .ivw-company { color: ${c.accent}; }
			.ivw-card.ivw-status-${key} .ivw-status-text { color: ${c.text}; }
			.ivw-card.ivw-status-${key} .ivw-line0 { color: ${c.text}; }
		`;
	});

	style.textContent = `
		.gantt .bar-wrapper .bar { opacity: 0; }
		.gantt .bar-wrapper .bar-label { display: none; }
		.gantt .bar-wrapper { cursor: pointer; }

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

		.ivw-line0 {
			font-size: 9.5px;
			font-weight: 700;
			text-transform: uppercase;
			letter-spacing: .03em;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
			line-height: 1.1;
		}

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

const IVW_MONTH_NAMES = [
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
];

// Finds the x-coordinate of a given calendar day's upper-text label
// (e.g. "27 August") in the Gantt chart's own SVG. Matches both
// zero-padded ("07 August") and unpadded ("7 August") forms since
// different frappe-gantt builds format the day number differently.
function ivw_find_day_center_x(svg, day_date) {
	const day = day_date.getDate();
	const month = IVW_MONTH_NAMES[day_date.getMonth()];
	const padded = `${String(day).padStart(2, "0")} ${month}`;
	const unpadded = `${day} ${month}`;

	const upper_texts = Array.from(svg.querySelectorAll("text.upper-text"));
	const match = upper_texts.find((t) => {
		const txt = t.textContent.trim();
		return txt === padded || txt === unpadded;
	});

	return match ? parseFloat(match.getAttribute("x")) : null;
}

// Computes the CORRECT x pixel for a given date + "HH:MM:SS" time,
// entirely independent of frappe-gantt's own (buggy) internal parsing —
// derived purely from real tick-label positions already in the DOM.
// Returns null if the relevant day label isn't currently rendered (e.g.
// zoomed out to Month view, where sub-day precision isn't meaningful
// anyway) — callers should fall back to the native rect x in that case.
function ivw_compute_correct_x(svg, date_of_interview, time_str) {
	if (!date_of_interview) return null;

	const [y, m, d] = date_of_interview.split("-").map(Number);
	if (!y || !m || !d) return null;

	const day_date = new Date(y, m - 1, d);
	const today_center = ivw_find_day_center_x(svg, day_date);
	if (today_center === null) return null;

	// Day width = spacing between two consecutive day-center labels.
	// This is measured directly from the DOM, so it's automatically
	// correct for whatever the current zoom level actually is (Quarter
	// Day, Half Day, Day, Week...) without us having to assume how many
	// sub-ticks exist per day.
	const next_center = ivw_find_day_center_x(svg, new Date(y, m - 1, d + 1));
	const prev_center = ivw_find_day_center_x(svg, new Date(y, m - 1, d - 1));

	let day_width;
	if (next_center !== null) {
		day_width = next_center - today_center;
	} else if (prev_center !== null) {
		day_width = today_center - prev_center;
	} else {
		return null; // can't determine scale — let caller fall back
	}

	const day_start_x = today_center - day_width / 2;
	const px_per_hour = day_width / 24;

	const [hh, mm, ss] = (time_str || "00:00:00").split(":").map(Number);
	const hours_into_day = (hh || 0) + (mm || 0) / 60 + (ss || 0) / 3600;

	return day_start_x + hours_into_day * px_per_hour;
}

// Watches the DOM for newly-rendered Gantt bars and, for each one, builds
// and injects a rich foreignObject card (customer/company/role/round/status/
// time) sized and positioned over the underlying bar/grid-row geometry.
(function watch_interview_gantt_bars() {
	if (window.__interviewGanttObserver) return;

	const MIN_CARD_WIDTH = 220;
	const MIN_CARD_HEIGHT_FALLBACK = 42;

	// Builds and appends the info card for a single Gantt bar element, based
	// on its matching entry in window.__interviewGanttMap.
	function render_card(bar) {
		const id = bar.getAttribute("data-id");
		if (!id) return;
		const info = window.__interviewGanttMap[id];
		if (!info) return;
		if (bar.querySelector(".ivw-fo")) return;

		const rect = bar.querySelector(".bar");
		if (!rect) return;

		// const rect_x = parseFloat(rect.getAttribute("x")) || 0;
		const rect_y = parseFloat(rect.getAttribute("y")) || 0;
		const rect_w = parseFloat(rect.getAttribute("width")) || 0;
		const rect_h = parseFloat(rect.getAttribute("height")) || 0;

		// row_pitch measurement (unchanged) ...
		const svg = bar.closest("svg");
		const grid_row = svg ? svg.querySelector(".grid-row") : null;
		const row_pitch = grid_row ? parseFloat(grid_row.getAttribute("height")) : 0;
		const ROW_INSET = 4;

		// --- corrected positioning (this is the actual fix) ---
		const computed_start_x = svg
			? ivw_compute_correct_x(svg, info.date_of_interview, info.from_time)
			: null;
		const computed_end_x = svg
			? ivw_compute_correct_x(svg, info.date_of_interview, info.to_time)
			: null;

		const rect_x = parseFloat(rect.getAttribute("x")) || 0; // fallback only

		const x = computed_start_x !== null ? computed_start_x : rect_x;
		const computed_width =
			computed_start_x !== null && computed_end_x !== null
				? computed_end_x - computed_start_x
				: rect_w;

		const width = Math.max(computed_width, MIN_CARD_WIDTH);
		const height =
			row_pitch > 0 ? row_pitch - ROW_INSET : Math.max(rect_h, MIN_CARD_HEIGHT_FALLBACK);
		const y = rect_y - (height - rect_h) / 2;

		const status = info.status || "Scheduled";
		const status_key = ivw_status_key(status);
		const date_display = info.date_of_interview
			? frappe.datetime.str_to_user
				? frappe.datetime.str_to_user(info.date_of_interview)
				: info.date_of_interview
			: "";

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
			info.customer || "",
			`${info.company || ""} — ${info.role || ""}`,
			`${info.round || ""} · ${status}`,
			[date_display, time_range].filter(Boolean).join(" · "),
		].join("\n");

		const esc = frappe.utils.escape_html;
		wrapper.innerHTML = `
    <div class="ivw-line0">
        <span class="ivw-customer">${esc(info.customer || "")}</span>
    </div>
    <div class="ivw-line1">
        <span class="ivw-company">${esc(info.company || "")}</span>
        <span class="ivw-role">${esc(info.role || "")}</span>
    </div>
    <div class="ivw-line2">
        <span>${esc(String(info.round || ""))}</span>
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

// Intercepts clicks on Gantt bars and navigates to the corresponding
// Interview form instead of the vendor library's default bar-click handling.
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
			if (!info) return;

			e.preventDefault();
			e.stopPropagation();
			frappe.set_route("Form", "Interview", info.interview);
		},
		true,
	);
})();

// Watches the DOM for the Gantt's today-marker elements and recolors them
// to the app's accent color whenever they (re)appear.
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

// Watches Gantt renders and repeatedly re-applies a scroll to the
// today-marker for about a second, so this scroll wins the race against
// the vendor library's own async "scroll to first task" behavior.
(function scroll_interview_gantt_to_today_on_render() {
	if (window.__interviewGanttTodayScrollObserver) return;

	let last_svg_el = null;
	let retry_count = 0;
	const MAX_RETRIES = 6;
	const RETRY_DELAY_MS = 150;

	// Scrolls the Gantt container so the today-marker is centered, once.
	function scroll_to_today_once() {
		if (!ivw_on_interview_gantt_route()) return false;

		const svg_el = document.querySelector(".gantt svg");
		if (!svg_el) return false;

		const today_el = svg_el.querySelector(".today-highlight");
		const $container = $(svg_el).closest(".gantt-container");
		if (!today_el || !$container.length) return false;

		try {
			const bbox = today_el.getBBox();
			const container_width = $container.width();
			const target_scroll = Math.max(0, bbox.x - container_width / 2 + bbox.width / 2);
			$container.scrollLeft(target_scroll);
			return true;
		} catch (e) {
			return false;
		}
	}

	// Schedules repeated attempts (up to MAX_RETRIES) to scroll to today,
	// resetting the retry count whenever a new Gantt SVG element appears.
	function try_scroll_to_today() {
		if (!ivw_on_interview_gantt_route()) return;

		const svg_el = document.querySelector(".gantt svg");
		if (!svg_el) return;

		if (svg_el !== last_svg_el) {
			last_svg_el = svg_el;
			retry_count = 0;
		}

		if (retry_count >= MAX_RETRIES) return;

		setTimeout(() => {
			retry_count += 1;
			scroll_to_today_once();
			try_scroll_to_today();
		}, RETRY_DELAY_MS);
	}

	const observer = new MutationObserver(() => try_scroll_to_today());
	observer.observe(document.body, { childList: true, subtree: true });
	window.__interviewGanttTodayScrollObserver = observer;

	frappe.router.on("change", () => {
		last_svg_el = null;
		retry_count = 0;
	});
})();

// Watches the DOM for the Gantt's native "No Interview found" empty state
// and replaces its message with a customer-scoped one, hiding the
// create-new-doc button.
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
					"No interview rounds found for the selected customers.",
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

// Patches GanttView.render_gantt so that a vendor-library crash on the
// zero-task edge case is caught and replaced with a friendly empty-state
// message instead of throwing, retrying the patch until the prototype exists.
(function patch_gantt_empty_state_crash() {
	function apply_patch() {
		const proto = frappe.views && frappe.views.GanttView && frappe.views.GanttView.prototype;
		if (
			!proto ||
			typeof proto.render_gantt !== "function" ||
			proto.render_gantt.__ivw_patched
		) {
			return false;
		}

		const original_render_gantt = proto.render_gantt;
		proto.render_gantt = function (...args) {
			try {
				return original_render_gantt.apply(this, args);
			} catch (e) {
				console.warn(
					"[Interview Gantt] vendor gantt library failed (likely zero-task edge case) — showing fallback empty state instead of throwing.",
					e,
				);
				if (this.$result) {
					this.$result.html(`
						<div class="text-muted text-center mt-5">
							${__("No interview rounds found for the selected customers.")}
						</div>
					`);
				}
			}
		};
		proto.render_gantt.__ivw_patched = true;
		return true;
	}

	if (!apply_patch()) {
		const interval = setInterval(() => {
			if (apply_patch()) clearInterval(interval);
		}, 300);
		setTimeout(() => clearInterval(interval), 5000);
	}
})();

// Watches the DOM while on the Calendar route and triggers a genuine
// FullCalendar refetch whenever the resolved customer selection differs
// from whichever selection was last fetched.
(function force_interview_calendar_refetch_on_route() {
	if (window.__interviewCalendarRefetchObserver) return;

	let last_fetched_key = null;

	function try_refetch() {
		if (!ivw_on_interview_calendar_route()) return;

		window.ivw_ensure_marketing_param().then((current_list) => {
			if (!current_list || !current_list.length) return;
			const key = current_list.slice().sort().join(",");
			if (key === last_fetched_key) return;

			const $fc = $(".fc").first();
			if (!$fc.length) return;

			try {
				$fc.fullCalendar("refetchEvents");
				last_fetched_key = key;
			} catch (e) {}
		});
	}

	const observer = new MutationObserver(() => try_refetch());
	observer.observe(document.body, { childList: true, subtree: true });
	window.__interviewCalendarRefetchObserver = observer;

	frappe.router.on("change", () => {
		if (!ivw_on_interview_calendar_route()) {
			last_fetched_key = null;
		}
	});
})();

// Formats a from/to time range (with optional timezone label) into a single
// display string, e.g. "09:00 – 09:30 (EST)".
function ivwc_format_when(from_time, to_time, edt_est) {
	if (!from_time) return "";
	let range = String(from_time).slice(0, 5);
	if (to_time) range += " – " + String(to_time).slice(0, 5);
	if (edt_est) range += ` (${edt_est})`;
	return range;
}

// Replaces a FullCalendar event element's content with a custom card
// showing customer, company, role, round, status, and time, sized for
// either the compact (month-grid) or full event layout.
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

	const card_html = `
    <div class="ivwc-card ${is_compact ? "ivwc-compact" : "ivwc-full"}">
        <div class="ivwc-row ivwc-row-customer">
            <span class="ivwc-customer">${esc(props.customer || "")}</span>
        </div>
        <div class="ivwc-row ivwc-row-company">
            <span class="ivwc-company">${esc(company)}</span>
        </div>
        <div class="ivwc-row ivwc-row-role">
            <span class="ivwc-role">${esc(role)}</span>
        </div>
        <div class="ivwc-row ivwc-row-status">
            <span class="ivwc-round-badge">${esc(String(round_no))}</span>
            <span class="ivwc-dot"></span>
            <span class="ivwc-status-text">${esc(status)}</span>
        </div>
        ${when ? `<div class="ivwc-row ivwc-row-time"><span class="ivwc-time">${esc(when)}</span></div>` : ""}
    </div>
`;

	$el.html(card_html);
}

// Toggles an event card's narrow/short/tall density classes based on its
// rendered element size, so the card layout adapts to the available space.
function adjust_interview_calendar_card_density(element) {
	const $el = $(element);
	const el = $el.get(0);
	if (!el) return;

	const width = el.offsetWidth;
	const height = el.offsetHeight;

	$el.toggleClass("ivwc-narrow", width > 0 && width < 130);
	$el.toggleClass("ivwc-short", height > 0 && height < 46);
	$el.toggleClass("ivwc-tall", height >= 90);
}

// Injects the Calendar event-card and per-status color CSS into the
// document head once, generating a status rule block from STATUS_INDICATOR_MAP.
(function inject_interview_calendar_styles() {
	if (document.getElementById("interview-calendar-styles")) return;
	const style = document.createElement("style");
	style.id = "interview-calendar-styles";

	let status_rules = "";
	Object.keys(window.STATUS_INDICATOR_MAP).forEach((status) => {
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
		.ivwc-customer {
			font-weight: 700;
			text-transform: uppercase;
			letter-spacing: .03em;
			opacity: .85;
		}
		.ivwc-compact .ivwc-customer { font-size: 8.5px; }
		.ivwc-full .ivwc-customer { font-size: 10px; }

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

		.ivwc-narrow.ivwc-full { padding: 3px 5px; gap: 0; }
		.ivwc-narrow.ivwc-full .ivwc-row-role { display: none; }
		.ivwc-narrow.ivwc-full .ivwc-company { font-size: 10px; }
		.ivwc-narrow.ivwc-full .ivwc-round-badge,
		.ivwc-narrow.ivwc-full .ivwc-status-text,
		.ivwc-narrow.ivwc-full .ivwc-time { font-size: 9px; }

		.ivwc-short.ivwc-full { padding: 2px 6px; gap: 0; }
		.ivwc-short.ivwc-full .ivwc-row-time { display: none; }

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
