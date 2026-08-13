frappe.views.calendar["Interview"] = {
	field_map: {
		start: "start", end: "end", id: "name", title: "subject",
		allDay: "allDay", status: "status", color: "color",
	},
	filters: [
		{ fieldtype: "Data", fieldname: "company", label: __("Company") },
		{ fieldtype: "Data", fieldname: "role", label: __("Role") },
		{ fieldtype: "Link", fieldname: "status", label: __("Status"), options: "Interview Status" },
	],
	get_events_method:
		"verp_staffing.marketing.doctype.interview.interview.get_interview_round_events",
};

frappe.views.calendar["Interview"] = Object.assign({}, frappe.views.calendar["Interview"], {
	gantt: {
		field_map: { start: "start", end: "end", id: "name", title: "subject", progress: "progress" },
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
	cyan:   { bg: "#E3FBFC", accent: "#00B0C7", text: "#0B5B66" },
	yellow: { bg: "#FFF8DE", accent: "#E8B900", text: "#6B5300" },
	blue:   { bg: "#E5F1FF", accent: "#2490EF", text: "#0B4A8C" },
	gray:   { bg: "#F1F1F1", accent: "#8D99A6", text: "#4B4B4B" },
	orange: { bg: "#FFF0E1", accent: "#FF9A2E", text: "#8A4B00" },
	green:  { bg: "#E7F9EE", accent: "#22C55E", text: "#166534" },
	red:    { bg: "#FDE8E8", accent: "#F04438", text: "#912018" },
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

function ivw_format_when(date_str, from_time) {
	if (!date_str) return "";
	const d = frappe.datetime.str_to_user ? frappe.datetime.str_to_user(date_str) : date_str;
	if (from_time) {
		return `${d} · ${String(from_time).slice(0, 5)}`;
	}
	return d;
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

		.ivw-card {
			width: 100%;
			height: 100%;
			display: flex;
			flex-direction: column;
			justify-content: center;
			gap: 1px;
			padding: 3px 8px;
			box-sizing: border-box;
			border-radius: 4px;
			background: #F1F1F1;
			overflow: hidden;
			box-shadow: 0 1px 2px rgba(0,0,0,.08);
			transition: box-shadow .12s ease, transform .12s ease;
		}
		.ivw-card:hover { box-shadow: 0 2px 6px rgba(0,0,0,.18); transform: translateY(-1px); }

		.ivw-line1 { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
		.ivw-company {
			font-weight: 600; font-size: 12px; color: #1c1c1c;
			white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		}
		.ivw-role {
			font-size: 11px; color: #5c5c5c; min-width: 0;
			white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		}

		.ivw-line2 {
			display: flex; align-items: center; gap: 5px;
			font-size: 10.5px; color: #6b6b6b;
			white-space: nowrap; overflow: hidden;
		}
		.ivw-dot { width: 6px; height: 6px; border-radius: 50%; flex: none; background: #8D99A6; }
		.ivw-status-text { font-weight: 600; overflow: hidden; text-overflow: ellipsis; }
		.ivw-sep { opacity: .5; }
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
	const MIN_CARD_HEIGHT = 42;

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

		const width = Math.max(rect_w, MIN_CARD_WIDTH);
		const height = Math.max(rect_h, MIN_CARD_HEIGHT);
		const x = rect_x; // keep the same left edge / start position
		const y = rect_y - (height - rect_h) / 2; // grow evenly, stay centred in the row

		const status = info.status || "Scheduled";
		const status_key = ivw_status_key(status);
		const when = ivw_format_when(info.date_of_interview, info.from_time);

		const fo = document.createElementNS("http://www.w3.org/2000/svg", "foreignObject");
		fo.setAttribute("class", "ivw-fo");
		fo.setAttribute("x", x);
		fo.setAttribute("y", y);
		fo.setAttribute("width", width);
		fo.setAttribute("height", height);
		fo.style.overflow = "visible";

		const wrapper = document.createElementNS("http://www.w3.org/1999/xhtml", "div");
		wrapper.className = `ivw-card ivw-status-${status_key}`;
		// native title kept only as an accessibility fallback (screen readers / very narrow bars)
		wrapper.title = `${info.company} — ${info.role}\nRound ${info.round} · ${status}\n${info.date_of_interview}`;

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
				${when ? `<span class="ivw-sep">·</span><span>${esc(when)}</span>` : ""}
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

// ---- Click routing: a Round's id is not a real Interview document, so
// intercept clicks on cards (capture phase) and route to the parent
// Interview ourselves. ----
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
		true // capture phase: run before Gantt's own click handler
	);
})();

// ---- Data-fetch override — also carries from_time so the card can
// show a time alongside the date. ----
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
			return original_call.call(frappe, {
				method:
					"verp_staffing.marketing.doctype.interview.interview.get_interview_gantt_rows",
				args: { filters: JSON.stringify(args.filters || []) },
			}).then((r) => {
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