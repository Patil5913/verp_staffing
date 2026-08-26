// // Gantt + Calendar view customization for Interview.

// // Registers the Interview calendar/gantt event source, field mapping,
// // and eventRender/eventAfterRender hooks used by FullCalendar.
// frappe.views.calendar["Interview"] = {
// 	field_map: {
// 		start: "start",
// 		end: "end",
// 		id: "name",
// 		title: "subject",
// 		allDay: "allDay",
// 		status: "status",
// 		color: "color",
// 	},
// 	filters: [
// 		{ fieldtype: "Data", fieldname: "company", label: __("Company") },
// 		{ fieldtype: "Data", fieldname: "role", label: __("Role") },
// 		{
// 			fieldtype: "Link",
// 			fieldname: "status",
// 			label: __("Status"),
// 			options: "Interview Status",
// 		},
// 	],
// 	get_events_method:
// 		"verp_staffing.marketing.doctype.interview.interview.get_interview_round_events",
// 	options: {
// 		eventRender: function (event, element, view) {
// 			render_interview_calendar_card(event, element, view);
// 		},
// 		eventAfterRender: function (event, element, view) {
// 			adjust_interview_calendar_card_density(element);
// 		},
// 	},
// };

// // Adds Gantt-specific field mapping to the Interview calendar config.
// frappe.views.calendar["Interview"] = Object.assign({}, frappe.views.calendar["Interview"], {
// 	gantt: {
// 		field_map: {
// 			start: "start",
// 			end: "end",
// 			id: "name",
// 			title: "subject",
// 			progress: "progress",
// 		},
// 	},
// });

// window.__interviewGanttMap = window.__interviewGanttMap || {};

// // Returns frappe.get_route() safely, defaulting to [] if the router
// // hasn't committed a route yet (avoids "route is null" during bootstrap).
// function ivw_safe_get_route() {
// 	try {
// 		const route = frappe.get_route ? frappe.get_route() : [];
// 		return Array.isArray(route) ? route : [];
// 	} catch (e) {
// 		return [];
// 	}
// }

// function ivw_on_interview_gantt_route() {
// 	const route = ivw_safe_get_route();
// 	return route[0] === "List" && route[1] === "Interview" && route[2] === "Gantt";
// }

// function ivw_on_interview_calendar_route() {
// 	const route = ivw_safe_get_route();
// 	return route[0] === "List" && route[1] === "Interview" && route[2] === "Calendar";
// }

// function ivw_on_any_interview_route() {
// 	const route = ivw_safe_get_route();
// 	return route[0] === "List" && route[1] === "Interview";
// }

// // Reads the currently selected marketing_link.
// function ivw_get_marketing_param() {
// 	return window.InterviewMarketingFilter.get();
// }

// // Resolves a default marketing_link on landing on any Interview route
// // (route change or first page load) and nudges Calendar's FullCalendar
// // instance to refetch once one is resolved.
// (function ensure_default_customer_on_interview_route() {
// 	function try_resolve() {
// 		if (!ivw_on_any_interview_route()) return;
// 		window.ivw_ensure_marketing_param().then((param) => {
// 			if (!param) return;
// 			const $fc = $(".fc").first();
// 			if ($fc.length) {
// 				try {
// 					$fc.fullCalendar("refetchEvents");
// 				} catch (e) {}
// 			}
// 		});
// 	}

// 	frappe.router.on("change", try_resolve);
// 	try_resolve();
// })();

// // Injects the Gantt bar card CSS (per-status colours, today marker, card layout) once.
// (function inject_interview_gantt_styles() {
// 	if (document.getElementById("interview-gantt-styles")) return;
// 	const style = document.createElement("style");
// 	style.id = "interview-gantt-styles";

// 	let status_rules = "";
// 	Object.keys(window.STATUS_INDICATOR_MAP).forEach((status) => {
// 		const key = ivw_status_key(status);
// 		const c = ivw_color_for_status(status);
// 		status_rules += `
// 			.ivw-card.ivw-status-${key} { background: ${c.bg}; border-left: 3px solid ${c.accent}; }
// 			.ivw-card.ivw-status-${key} .ivw-dot { background: ${c.accent}; }
// 			.ivw-card.ivw-status-${key} .ivw-company,
// 			.ivw-card.ivw-status-${key} .ivw-status-text { color: ${c.text}; }
// 		`;
// 	});

// 	style.textContent = `
// 		/* hide the default frappe-gantt bar + label — we render our own card */
// 		.gantt .bar-wrapper .bar { opacity: 0; }
// 		.gantt .bar-wrapper .bar-label { display: none; }
// 		.gantt .bar-wrapper { cursor: pointer; }

// 		.gantt .today-highlight {
// 			background: rgba(255, 82, 82, 0.08) !important;
// 			border-left: 2px solid #ff5252 !important;
// 			border-right: 2px solid #ff5252 !important;
// 		}

// 		.ivw-card {
// 			width: 100%;
// 			height: 100%;
// 			display: flex;
// 			flex-direction: column;
// 			justify-content: center;
// 			gap: 1px;
// 			padding: 2px 8px;
// 			box-sizing: border-box;
// 			border-radius: 4px;
// 			background: #F1F1F1;
// 			overflow: hidden;
// 			box-shadow: 0 1px 2px rgba(0,0,0,.08);
// 			transition: box-shadow .12s ease, transform .12s ease;
// 		}
// 		.ivw-card:hover { box-shadow: 0 2px 6px rgba(0,0,0,.18); transform: translateY(-1px); }

// 		.ivw-line1 { display: flex; align-items: baseline; gap: 6px; min-width: 0; line-height: 1.15; }
// 		.ivw-company {
// 			font-weight: 600; font-size: 11.5px; color: #1c1c1c;
// 			white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
// 		}
// 		.ivw-role {
// 			font-size: 10.5px; color: #5c5c5c; min-width: 0;
// 			white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
// 		}

// 		.ivw-line2, .ivw-line3 {
// 			display: flex; align-items: center; gap: 5px;
// 			font-size: 10px; line-height: 1.15; color: #6b6b6b;
// 			white-space: nowrap; overflow: hidden;
// 		}
// 		.ivw-dot { width: 5px; height: 5px; border-radius: 50%; flex: none; background: #8D99A6; }
// 		.ivw-status-text { font-weight: 600; overflow: hidden; text-overflow: ellipsis; }
// 		.ivw-sep { opacity: .5; }
// 		.ivw-time { flex: none; }
// 		.ivw-tz { flex: none; font-weight: 600; opacity: .75; }
// 		${status_rules}
// 	`;
// 	document.head.appendChild(style);
// })();

// // Watches for newly rendered Gantt bars and overlays a rich HTML card
// // (company/role/round/status/date) onto each, sized to the row's actual pitch.
// (function watch_interview_gantt_bars() {
// 	if (window.__interviewGanttObserver) return;

// 	const MIN_CARD_WIDTH = 220;
// 	const MIN_CARD_HEIGHT_FALLBACK = 42;

// 	// Renders one overlay card for a single Gantt bar element.
// 	function render_card(bar) {
// 		const id = bar.getAttribute("data-id");
// 		if (!id) return;
// 		const info = window.__interviewGanttMap[id];
// 		if (!info) return;
// 		if (bar.querySelector(".ivw-fo")) return;

// 		const rect = bar.querySelector(".bar");
// 		if (!rect) return;

// 		const rect_x = parseFloat(rect.getAttribute("x")) || 0;
// 		const rect_y = parseFloat(rect.getAttribute("y")) || 0;
// 		const rect_w = parseFloat(rect.getAttribute("width")) || 0;
// 		const rect_h = parseFloat(rect.getAttribute("height")) || 0;

// 		const svg = bar.closest("svg");
// 		const grid_row = svg ? svg.querySelector(".grid-row") : null;
// 		const row_pitch = grid_row ? parseFloat(grid_row.getAttribute("height")) : 0;
// 		const ROW_INSET = 4;

// 		const width = Math.max(rect_w, MIN_CARD_WIDTH);
// 		const height =
// 			row_pitch > 0 ? row_pitch - ROW_INSET : Math.max(rect_h, MIN_CARD_HEIGHT_FALLBACK);
// 		const x = rect_x;
// 		const y = rect_y - (height - rect_h) / 2;

// 		const status = info.status || "Scheduled";
// 		const status_key = ivw_status_key(status);
// 		const date_display = info.date_of_interview
// 			? frappe.datetime.str_to_user
// 				? frappe.datetime.str_to_user(info.date_of_interview)
// 				: info.date_of_interview
// 			: "";

// 		let time_range = "";
// 		if (info.from_time) {
// 			time_range = String(info.from_time).slice(0, 5);
// 			if (info.to_time) time_range += " – " + String(info.to_time).slice(0, 5);
// 			if (info.edt_est) time_range += ` (${info.edt_est})`;
// 		}

// 		const fo = document.createElementNS("http://www.w3.org/2000/svg", "foreignObject");
// 		fo.setAttribute("class", "ivw-fo");
// 		fo.setAttribute("x", x);
// 		fo.setAttribute("y", y);
// 		fo.setAttribute("width", width);
// 		fo.setAttribute("height", height);
// 		fo.style.overflow = "visible";

// 		const wrapper = document.createElementNS("http://www.w3.org/1999/xhtml", "div");
// 		wrapper.className = `ivw-card ivw-status-${status_key}`;
// 		wrapper.title = [
// 			`${info.company || ""} — ${info.role || ""}`,
// 			`Round ${info.round || ""} · ${status}`,
// 			[date_display, time_range].filter(Boolean).join(" · "),
// 		].join("\n");

// 		const esc = frappe.utils.escape_html;
// 		wrapper.innerHTML = `
// 			<div class="ivw-line1">
// 				<span class="ivw-company">${esc(info.company || "")}</span>
// 				<span class="ivw-role">${esc(info.role || "")}</span>
// 			</div>
// 			<div class="ivw-line2">
// 				<span>Round ${esc(String(info.round || ""))}</span>
// 				<span class="ivw-sep">·</span>
// 				<span class="ivw-dot"></span>
// 				<span class="ivw-status-text">${esc(status)}</span>
// 			</div>
// 			<div class="ivw-line3">
// 				${date_display ? `<span class="ivw-time">${esc(date_display)}</span>` : ""}
// 				${time_range ? `<span class="ivw-sep">·</span><span class="ivw-time">${esc(time_range)}</span>` : ""}
// 			</div>
// 		`;

// 		fo.appendChild(wrapper);
// 		bar.appendChild(fo);
// 	}

// 	const observer = new MutationObserver((mutations) => {
// 		if (!ivw_on_interview_gantt_route()) return;

// 		for (const m of mutations) {
// 			m.addedNodes.forEach((node) => {
// 				if (!(node instanceof Element)) return;
// 				const bars = node.matches?.(".bar-wrapper")
// 					? [node]
// 					: Array.from(node.querySelectorAll?.(".bar-wrapper") || []);
// 				bars.forEach(render_card);
// 			});
// 		}
// 	});

// 	observer.observe(document.body, { childList: true, subtree: true });
// 	window.__interviewGanttObserver = observer;
// })();

// // Intercepts clicks on Gantt bars and routes to the parent Interview form.
// (function patch_interview_gantt_click() {
// 	if (window.__interviewGanttClickPatched) return;
// 	window.__interviewGanttClickPatched = true;

// 	document.addEventListener(
// 		"click",
// 		(e) => {
// 			if (!ivw_on_interview_gantt_route()) return;
// 			const bar = e.target.closest?.(".bar-wrapper");
// 			if (!bar) return;
// 			const id = bar.getAttribute("data-id");
// 			if (!id) return;
// 			const info = window.__interviewGanttMap[id];
// 			if (!info) return;

// 			e.preventDefault();
// 			e.stopPropagation();
// 			frappe.set_route("Form", "Interview", info.interview);
// 		},
// 		true,
// 	);
// })();

// // Recolors the Gantt "today" marker to a higher-contrast accent whenever it's rendered.
// (function watch_interview_gantt_today_marker() {
// 	if (window.__interviewGanttTodayObserver) return;

// 	function recolor_today_marker() {
// 		if (!ivw_on_interview_gantt_route()) return;

// 		document
// 			.querySelectorAll(
// 				".gantt .today-highlight, .gantt rect.today-highlight, .gantt .holiday-highlight.today, svg .today-highlight",
// 			)
// 			.forEach((el) => {
// 				el.style.setProperty("fill", "rgba(118, 51, 233, 0.14)", "important");
// 				el.style.setProperty("stroke", "#7b36f4", "important");
// 				el.style.setProperty("stroke-width", "2", "important");
// 			});
// 	}

// 	const observer = new MutationObserver(() => recolor_today_marker());
// 	observer.observe(document.body, { childList: true, subtree: true });
// 	window.__interviewGanttTodayObserver = observer;
// })();

// // Rewrites the Gantt "no results" message and hides the "new doc" button for Interview.
// (function watch_interview_gantt_empty_state() {
// 	if (window.__interviewGanttEmptyObserver) return;

// 	function customize_empty_state() {
// 		if (!ivw_on_interview_gantt_route()) return;

// 		document.querySelectorAll(".no-result, .msg-box").forEach((box) => {
// 			if (box.dataset.ivwEmptyPatched) return;
// 			if (!(box.textContent || "").includes("No Interview found")) return;

// 			box.dataset.ivwEmptyPatched = "1";

// 			const message_el = box.querySelector("p");
// 			if (message_el) {
// 				message_el.textContent = __(
// 					"No interview rounds found for the selected customer.",
// 				);
// 			}

// 			box.querySelectorAll(".btn-new-doc").forEach((btn) => {
// 				btn.style.display = "none";
// 			});
// 		});
// 	}

// 	const observer = new MutationObserver(() => customize_empty_state());
// 	observer.observe(document.body, { childList: true, subtree: true });
// 	window.__interviewGanttEmptyObserver = observer;
// })();

// // Patches GanttView.render_gantt to catch the vendor library's crash on
// // an empty task list, showing a fallback empty-state message instead.
// (function patch_gantt_empty_state_crash() {
// 	function apply_patch() {
// 		const proto = frappe.views && frappe.views.GanttView && frappe.views.GanttView.prototype;
// 		if (!proto || typeof proto.render_gantt !== "function" || proto.render_gantt.__ivw_patched) {
// 			return false;
// 		}

// 		const original_render_gantt = proto.render_gantt;
// 		proto.render_gantt = function (...args) {
// 			try {
// 				return original_render_gantt.apply(this, args);
// 			} catch (e) {
// 				console.warn(
// 					"[Interview Gantt] vendor gantt library failed (likely zero-task edge case) — showing fallback empty state instead of throwing.",
// 					e
// 				);
// 				if (this.$result) {
// 					this.$result.html(`
// 						<div class="text-muted text-center mt-5">
// 							${__("No interview rounds found for the selected customer.")}
// 						</div>
// 					`);
// 				}
// 			}
// 		};
// 		proto.render_gantt.__ivw_patched = true;
// 		return true;
// 	}

// 	if (!apply_patch()) {
// 		const interval = setInterval(() => {
// 			if (apply_patch()) clearInterval(interval);
// 		}, 300);
// 		setTimeout(() => clearInterval(interval), 5000);
// 	}
// })();

// // Forces a FullCalendar refetch whenever on the Calendar route and the
// // selected customer differs from what's currently rendered.
// (function force_interview_calendar_refetch_on_route() {
// 	if (window.__interviewCalendarRefetchObserver) return;

// 	let last_fetched_marketing = null;

// 	function try_refetch() {
// 		if (!ivw_on_interview_calendar_route()) return;

// 		window.ivw_ensure_marketing_param().then((current) => {
// 			if (!current || current === last_fetched_marketing) return;

// 			const $fc = $(".fc").first();
// 			if (!$fc.length) return;

// 			try {
// 				$fc.fullCalendar("refetchEvents");
// 				last_fetched_marketing = current;
// 			} catch (e) {}
// 		});
// 	}

// 	const observer = new MutationObserver(() => try_refetch());
// 	observer.observe(document.body, { childList: true, subtree: true });
// 	window.__interviewCalendarRefetchObserver = observer;

// 	frappe.router.on("change", () => {
// 		if (!ivw_on_interview_calendar_route()) {
// 			last_fetched_marketing = null;
// 		}
// 	});
// })();

// // Formats a "from – to (tz)" time-range string for a calendar event card.
// function ivwc_format_when(from_time, to_time, edt_est) {
// 	if (!from_time) return "";
// 	let range = String(from_time).slice(0, 5);
// 	if (to_time) range += " – " + String(to_time).slice(0, 5);
// 	if (edt_est) range += ` (${edt_est})`;
// 	return range;
// }

// // Renders a FullCalendar event's card markup (company/role/round/status/time).
// function render_interview_calendar_card(event, element, view) {
// 	const props = event.extendedProps || event;

// 	const status = props.status || "Scheduled";
// 	const status_key = ivw_status_key(status);
// 	const company = props.company || "";
// 	const role = props.role || "";
// 	const round_no = props.round || "";
// 	const when = ivwc_format_when(props.from_time, props.to_time, props.edt_est);

// 	const view_name = (view && view.name) || "";
// 	const is_compact = view_name === "month" || element.hasClass?.("fc-day-grid-event");

// 	element.addClass(`ivwc-event ivwc-status-${status_key}`);

// 	const esc = frappe.utils.escape_html;
// 	const $el = $(element);
// 	$el.empty();

// 	const card_html = `
// 		<div class="ivwc-card ${is_compact ? "ivwc-compact" : "ivwc-full"}">
// 			<div class="ivwc-row ivwc-row-company">
// 				<span class="ivwc-company">${esc(company)}</span>
// 			</div>
// 			<div class="ivwc-row ivwc-row-role">
// 				<span class="ivwc-role">${esc(role)}</span>
// 			</div>
// 			<div class="ivwc-row ivwc-row-status">
// 				<span class="ivwc-round-badge">Round ${esc(String(round_no))}</span>
// 				<span class="ivwc-dot"></span>
// 				<span class="ivwc-status-text">${esc(status)}</span>
// 			</div>
// 			${
// 				when
// 					? `
// 			<div class="ivwc-row ivwc-row-time">
// 				<span class="ivwc-time">${esc(when)}</span>
// 			</div>`
// 					: ""
// 			}
// 		</div>
// 	`;

// 	$el.html(card_html);
// }

// // Applies narrow/short/tall density classes based on the event element's
// // actual rendered size (only known post-layout).
// function adjust_interview_calendar_card_density(element) {
// 	const $el = $(element);
// 	const el = $el.get(0);
// 	if (!el) return;

// 	const width = el.offsetWidth;
// 	const height = el.offsetHeight;

// 	$el.toggleClass("ivwc-narrow", width > 0 && width < 130);
// 	$el.toggleClass("ivwc-short", height > 0 && height < 46);
// 	$el.toggleClass("ivwc-tall", height >= 90);
// }

// // Injects the Calendar event card CSS (per-status colours, density variants) once.
// (function inject_interview_calendar_styles() {
// 	if (document.getElementById("interview-calendar-styles")) return;
// 	const style = document.createElement("style");
// 	style.id = "interview-calendar-styles";

// 	let status_rules = "";
// 	Object.keys(window.STATUS_INDICATOR_MAP).forEach((status) => {
// 		const key = ivw_status_key(status);
// 		const c = ivw_color_for_status(status);
// 		status_rules += `
// 			.ivwc-event.ivwc-status-${key} { background: ${c.bg} !important; border: none !important; }
// 			.ivwc-event.ivwc-status-${key} .ivwc-dot { background: ${c.accent}; }
// 			.ivwc-event.ivwc-status-${key} .ivwc-company,
// 			.ivwc-event.ivwc-status-${key} .ivwc-status-text { color: ${c.text}; }
// 			.ivwc-event.ivwc-status-${key} .ivwc-full,
// 			.ivwc-event.ivwc-status-${key} .ivwc-compact { border-left: 3px solid ${c.accent}; }
// 		`;
// 	});

// 	style.textContent = `
// 		.ivwc-event {
// 			border-radius: 4px;
// 			overflow: hidden;
// 			padding: 0 !important;
// 		}

// 		.ivwc-card {
// 			width: 100%;
// 			box-sizing: border-box;
// 			overflow: hidden;
// 			display: flex;
// 			flex-direction: column;
// 		}
// 		.ivwc-row {
// 			white-space: nowrap;
// 			overflow: hidden;
// 			text-overflow: ellipsis;
// 		}
// 		.ivwc-row-status {
// 			display: flex;
// 			align-items: center;
// 			gap: 5px;
// 		}
// 		.ivwc-dot { width: 6px; height: 6px; border-radius: 50%; flex: none; background: #8D99A6; }
// 		.ivwc-sep { opacity: .5; flex: none; }

// 		.fc-day-grid-event.ivwc-event {
// 			white-space: normal !important;
// 			height: auto !important;
// 			padding: 0 !important;
// 			margin-bottom: 2px !important;
// 		}
// 		.ivwc-compact {
// 			gap: 1px;
// 			padding: 3px 6px;
// 			line-height: 1.25;
// 		}
// 		.ivwc-compact .ivwc-company { font-weight: 600; font-size: 10.5px; }
// 		.ivwc-compact .ivwc-role { font-size: 9.5px; opacity: .8; }
// 		.ivwc-compact .ivwc-round-badge { font-size: 9px; font-weight: 700; opacity: .75; }
// 		.ivwc-compact .ivwc-status-text { font-size: 9px; font-weight: 600; }
// 		.ivwc-compact .ivwc-time { font-size: 9px; opacity: .65; font-weight: 600; }

// 		.ivwc-full {
// 			gap: 3px;
// 			padding: 6px 10px;
// 			height: 100%;
// 			justify-content: center;
// 		}
// 		.ivwc-full .ivwc-company { font-weight: 600; font-size: 12.5px; }
// 		.ivwc-full .ivwc-role { font-size: 11px; opacity: .75; }
// 		.ivwc-full .ivwc-round-badge { font-size: 11px; opacity: .85; }
// 		.ivwc-full .ivwc-status-text { font-size: 11px; font-weight: 600; }
// 		.ivwc-full .ivwc-time { font-size: 11px; opacity: .75; }

// 		.fc-time-grid .fc-event.ivwc-event {
// 			box-sizing: border-box !important;
// 			box-shadow: inset 0 0 0 1px rgba(255,255,255,.9);
// 		}

// 		.ivwc-narrow.ivwc-full { padding: 3px 5px; gap: 0; }
// 		.ivwc-narrow.ivwc-full .ivwc-row-role { display: none; }
// 		.ivwc-narrow.ivwc-full .ivwc-company { font-size: 10px; }
// 		.ivwc-narrow.ivwc-full .ivwc-round-badge,
// 		.ivwc-narrow.ivwc-full .ivwc-status-text,
// 		.ivwc-narrow.ivwc-full .ivwc-time { font-size: 9px; }

// 		.ivwc-short.ivwc-full { padding: 2px 6px; gap: 0; }
// 		.ivwc-short.ivwc-full .ivwc-row-time { display: none; }

// 		.ivwc-tall.ivwc-full { gap: 5px; padding: 8px 12px; }
// 		.ivwc-tall.ivwc-full .ivwc-company { font-size: 14px; }
// 		.ivwc-tall.ivwc-full .ivwc-role { font-size: 12px; }
// 		.ivwc-tall.ivwc-full .ivwc-round-badge,
// 		.ivwc-tall.ivwc-full .ivwc-status-text { font-size: 12px; }
// 		.ivwc-tall.ivwc-full .ivwc-time { font-size: 12px; font-weight: 600; }

// 		${status_rules}
// 	`;
// 	document.head.appendChild(style);
// })();

// ---------------------------------------------------------------------
// interview_calendar.js
//
// Gantt + Calendar view customization for Interview.
//
// Requires interview_common.js loaded first. No functional changes were
// needed here for multi-customer support: this file never reads
// InterviewMarketingFilter directly for filtering purposes — it always
// goes through window.ivw_ensure_marketing_param(), which now resolves
// to an array, and the shared frappe.call gate in interview_common.js is
// what actually turns that array into an IN(...) filter before every
// fetch. Gantt/Calendar have a bounded date range already (no infinite
// load), so "all rounds across all selected customers in this range" is
// just "the IN filter applies", nothing else to add.
// ---------------------------------------------------------------------

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

// interview_calendar.js
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

// ---------------------------------------------------------------------
// Resolve the selected customer LIST proactively on landing on Gantt or
// Calendar (route change or first page load), rather than waiting for
// the first fetch to discover nothing is selected.
// ---------------------------------------------------------------------
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

// ---- Inject card + status-colour CSS once ----
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
			.ivw-card.ivw-status-${key} .ivw-company,
			.ivw-card.ivw-status-${key} .ivw-status-text { color: ${c.text}; }
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
    color: #7b36f4;
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

// ---- Render a full-info card into each bar as frappe-gantt draws it ----
(function watch_interview_gantt_bars() {
	if (window.__interviewGanttObserver) return;

	const MIN_CARD_WIDTH = 220;
	const MIN_CARD_HEIGHT_FALLBACK = 42;

	function render_card(bar) {
		const id = bar.getAttribute("data-id");
		if (!id) return;
		const info = window.__interviewGanttMap[id];
		if (!info) return;
		if (bar.querySelector(".ivw-fo")) return;

		const rect = bar.querySelector(".bar");
		if (!rect) return;

		const rect_x = parseFloat(rect.getAttribute("x")) || 0;
		const rect_y = parseFloat(rect.getAttribute("y")) || 0;
		const rect_w = parseFloat(rect.getAttribute("width")) || 0;
		const rect_h = parseFloat(rect.getAttribute("height")) || 0;

		const svg = bar.closest("svg");
		const grid_row = svg ? svg.querySelector(".grid-row") : null;
		const row_pitch = grid_row ? parseFloat(grid_row.getAttribute("height")) : 0;
		const ROW_INSET = 4;

		const width = Math.max(rect_w, MIN_CARD_WIDTH);
		const height =
			row_pitch > 0 ? row_pitch - ROW_INSET : Math.max(rect_h, MIN_CARD_HEIGHT_FALLBACK);
		const x = rect_x;
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
			`${info.company || ""} — ${info.role || ""}`,
			`Round ${info.round || ""} · ${status}`,
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
			if (!info) return;

			e.preventDefault();
			e.stopPropagation();
			frappe.set_route("Form", "Interview", info.interview);
		},
		true,
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

// interview_calendar.js

(function scroll_interview_gantt_to_today_on_render() {
	if (window.__interviewGanttTodayScrollObserver) return;

	let last_svg_el = null;

	function try_scroll_to_today() {
		if (!ivw_on_interview_gantt_route()) return;

		const svg_el = document.querySelector(".gantt svg");
		if (!svg_el) return;

		// frappe-gantt tears down and rebuilds the <svg> node on every
		// refresh, filter change, or view-mode switch. Only schedule once
		// per distinct svg instance.
		if (svg_el === last_svg_el) return;
		last_svg_el = svg_el;

		// frappe-gantt runs its own "scroll to first task" AFTER it finishes
		// laying out bars, on a later tick than this mutation callback. If we
		// scroll immediately, that native scroll fires afterwards and
		// silently overwrites ours — landing the user on the first task
		// instead of today. Deferring lets us go last and win.
		setTimeout(() => {
			const today_el = svg_el.querySelector(".today-highlight");
			const $container = $(svg_el).closest(".gantt-container");
			if (!today_el || !$container.length) return;

			try {
				const bbox = today_el.getBBox();
				const container_width = $container.width();
				const target_scroll = Math.max(0, bbox.x - container_width / 2 + bbox.width / 2);
				$container.scrollLeft(target_scroll);
			} catch (e) {
				// getBBox can throw if not laid out yet; harmless no-op.
			}
		}, 120);
	}

	const observer = new MutationObserver(() => try_scroll_to_today());
	observer.observe(document.body, { childList: true, subtree: true });
	window.__interviewGanttTodayScrollObserver = observer;
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

// ---------------------------------------------------------------------
// Force a genuine refetch when the Calendar route is active and the
// selected customer LIST differs from what's currently rendered.
// ---------------------------------------------------------------------
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
            <span class="ivwc-round-badge">Round ${esc(String(round_no))}</span>
            <span class="ivwc-dot"></span>
            <span class="ivwc-status-text">${esc(status)}</span>
        </div>
        ${when ? `<div class="ivwc-row ivwc-row-time"><span class="ivwc-time">${esc(when)}</span></div>` : ""}
    </div>
`;

	$el.html(card_html);
}

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
