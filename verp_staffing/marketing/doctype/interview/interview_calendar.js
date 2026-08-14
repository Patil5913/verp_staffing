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

(function override_interview_gantt_fetch() {
	if (frappe.__interview_gantt_call_patched) return;
	frappe.__interview_gantt_call_patched = true;

	const original_call = frappe.call;

	frappe.call = function (...call_args) {
		const opts = call_args[0];
		const is_object_call = opts && typeof opts === "object" && !Array.isArray(opts);
		const method = is_object_call ? opts.method : null;
		const args = is_object_call ? opts.args : null;

		const is_doomed_reportview_call =
			method === "frappe.desk.reportview.get" &&
			args &&
			args.doctype === "Interview" &&
			typeof args.order_by === "string" &&
			args.order_by.indexOf("`start`") !== -1;

		if (ivw_on_interview_gantt_route() && is_doomed_reportview_call) {
			return original_call
				.call(frappe, {
					method: "verp_staffing.marketing.doctype.interview.interview.get_interview_gantt_rows",
					args: { filters: JSON.stringify(args.filters || []) },
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
					if (opts.callback) opts.callback(result);
					return result;
				});
		}

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
			${when ? `
			<div class="ivwc-row ivwc-row-time">
				<span class="ivwc-time">${esc(when)}</span>
			</div>` : ""}
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
