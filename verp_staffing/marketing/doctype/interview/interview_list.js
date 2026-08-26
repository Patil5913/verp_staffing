// // List + Kanban view customization for Interview. Requires

// (function () {
// 	"use strict";

// 	const ROUND_SUMMARY_METHOD =
// 		"verp_staffing.marketing.doctype.interview.interview.get_round_summary_for_kanban";
// 	const UPDATE_STATUS_METHOD =
// 		"verp_staffing.marketing.doctype.interview.interview.update_interview_status_from_kanban";
// 	const MARKETING_OPTIONS_METHOD =
// 		"verp_staffing.marketing.doctype.interview.interview.get_default_marketing_customer_options";
// 	const MARKETING_SEARCH_METHOD =
// 		"verp_staffing.marketing.doctype.interview.interview.search_marketing_customers";

// 	const CANCELLED_LIKE_STATUSES = new Set(["Cancelled", "Rescheduled"]);
// 	const FINAL_ROUND_STATUSES = new Set(["Cancelled", "Rescheduled", "Completed"]);

// 	const ROUND_PREVIEW_LIMIT = 5;

// 	const state = {
// 		marketingAppliedValue: null,
// 		marketingIsSetting: false,
// 		kanbanObserver: null,
// 		kanbanObservedEl: null,
// 		refreshTimer: null,
// 		kanbanStyleInjected: false,
// 		roundCache: new Map(),
// 		roundInFlight: new Set(),
// 		renderScheduled: false,
// 		routeCleanupBound: false,
// 		cardColumnState: new Map(),
// 		pendingStatusChange: new Set(),
// 		currentListview: null,
// 		isDragging: false,
// 		expandedCards: new Set(),
// 		fieldSelectPatched: false,
// 		marketingFieldBlockerBound: false,
// 		pendingTodayUpdate: new Set(),
// 	};

// 	frappe.listview_settings["Interview"] = {
// 		// Registers the Interview breadcrumb on first load.
// 		onload(listview) {
// 			frappe.breadcrumbs.all[frappe.get_route_str()] = {
// 				workspace: "Interviews",
// 				doctype: listview.doctype,
// 				type: "List",
// 			};
// 			frappe.breadcrumbs.update();
// 		},

// 		// Applies marketing-customer scoping, Kanban overrides, and the
// 		// filter-UI lock on every list refresh.
// 		refresh(listview) {
// 			const page = listview.page;
// 			if (!page) return;

// 			state.currentListview = listview;

// 			hide_kanban_chrome(page);

// 			if (!page.customer_filter_btn_added) {
// 				page.customer_filter_btn_added = true;
// 				page.add_inner_button(__("Select Customer"), () => {
// 					open_marketing_customer_dialog(listview);
// 				});
// 			}

// 			apply_marketing_auto_filter(listview);
// 			patch_field_select_to_hide_marketing();
// 			bind_marketing_filter_dom_guard();
// 			lock_marketing_filter(listview);

// 			if (is_kanban_view(listview)) {
// 				setup_kanban_overrides(listview);
// 				ensure_route_cleanup();
// 			}
// 		},
// 	};

// 	// Hides Kanban's default "add column" and "Select Kanban" controls.
// 	function hide_kanban_chrome(page) {
// 		requestAnimationFrame(() => {
// 			page.wrapper.find(".add-new-column").hide();
// 			page.inner_toolbar.find("button").each(function () {
// 				if ($(this).text().includes("Select Kanban")) {
// 					$(this).parent().hide();
// 				}
// 			});
// 		});
// 	}

// 	// Returns true when the current listview is rendering Kanban.
// 	function is_kanban_view(listview) {
// 		return (
// 			listview.view_name === "Kanban" || window.location.pathname.includes("/view/kanban/")
// 		);
// 	}

// 	// Injects the Kanban board's card/column layout and round-summary CSS once.
// 	function inject_kanban_css() {
// 		if (state.kanbanStyleInjected) return;
// 		state.kanbanStyleInjected = true;

// 		$("<style>")
// 			.attr("id", "interview-kanban-overrides")
// 			.html(
// 				`
// 				/* Board */
// 				.kanban {
// 					overflow-x: auto !important;
// 					overflow-y: hidden !important;
// 					box-sizing: border-box !important;
// 				}

// 				/* Columns */
// 				.kanban-column {
// 					width: 360px !important;
// 					min-width: 360px !important;
// 					max-width: 360px !important;
// 					flex: 0 0 360px !important;
// 					box-sizing: border-box !important;
// 				}

// 				/* Card container */
// 				.kanban-cards {
// 					width: 100% !important;
// 					min-width: 0 !important;
// 					max-width: 100% !important;
// 					box-sizing: border-box !important;
// 				}

// 				/* Normal sortable item */
// 				.kanban-card-wrapper {
// 					display: block !important;

// 					width: 100% !important;
// 					min-width: 0 !important;
// 					max-width: 100% !important;

// 					box-sizing: border-box !important;
// 				}

// 				/* Actual card */
// 				.kanban-card-wrapper > .kanban-card {
// 					display: block !important;

// 					width: 100% !important;
// 					min-width: 0 !important;
// 					max-width: 100% !important;

// 					box-sizing: border-box !important;
// 				}

// 				.kanban-card-body {
// 					width: 100% !important;
// 					min-width: 0 !important;
// 					max-width: 100% !important;
// 					box-sizing: border-box !important;
// 				}

// 				.kanban-card-doc {
// 					width: 100% !important;
// 					min-width: 0 !important;
// 					max-width: 100% !important;
// 					box-sizing: border-box !important;
// 				}

// 				/* Sortable drag element: lock the dragged wrapper to a
// 				   column's width so it doesn't inherit the board's width. */
// 				.kanban-card-wrapper.sortable-drag,
// 				.kanban-card-wrapper.sortable-fallback {
// 					width: 360px !important;
// 					min-width: 360px !important;
// 					max-width: 360px !important;

// 					flex: 0 0 360px !important;

// 					box-sizing: border-box !important;
// 				}

// 				.kanban-card-wrapper.sortable-drag > .kanban-card,
// 				.kanban-card-wrapper.sortable-fallback > .kanban-card {
// 					width: 360px !important;
// 					min-width: 360px !important;
// 					max-width: 360px !important;

// 					box-sizing: border-box !important;
// 				}

// 				/* Sortable ghost: stays inside the target column's width. */
// 				.kanban-card-wrapper.sortable-ghost {
// 					width: 100% !important;
// 					min-width: 0 !important;
// 					max-width: 100% !important;

// 					box-sizing: border-box !important;
// 				}

// 				.kanban-card-wrapper.sortable-ghost > .kanban-card {
// 					width: 100% !important;
// 					min-width: 0 !important;
// 					max-width: 100% !important;

// 					box-sizing: border-box !important;
// 				}

// 				/* Prevent dragged card content from expanding it */
// 				.sortable-drag .kanban-card-title,
// 				.sortable-fallback .kanban-card-title,
// 				.sortable-drag .kanban-card-doc,
// 				.sortable-fallback .kanban-card-doc {
// 					min-width: 0 !important;
// 					max-width: 100% !important;
// 					overflow: hidden !important;
// 				}

// 				.sortable-drag .kanban-title-area,
// 				.sortable-fallback .kanban-title-area {
// 					min-width: 0 !important;
// 					max-width: 100% !important;
// 					box-sizing: border-box !important;
// 				}

// 				/* Hover */
// 				.kanban-card-wrapper:hover {
// 					width: 100% !important;
// 					max-width: 100% !important;
// 					box-sizing: border-box !important;
// 				}

// 				.kanban-card-wrapper:hover > .kanban-card {
// 					width: 100% !important;
// 					max-width: 100% !important;
// 					box-sizing: border-box !important;
// 				}

// 				/* Default Frappe card UI */
// 				.add-card {
// 					display: none !important;
// 				}

// 				.kanban-card-meta {
// 					display: none !important;
// 				}

// 				/* Round summary */
// 				.kanban-rounds-summary {
// 					width: 100%;
// 					min-width: 0;
// 					max-width: 100%;

// 					box-sizing: border-box;

// 					margin-top: 8px;
// 					padding-top: 6px;

// 					border-top: 1px solid var(--border-color, #e0e0e0);

// 					display: flex;
// 					flex-direction: column;
// 					gap: 5px;
// 				}

// 				.kanban-rounds-summary.expanded {
// 					max-height: 220px;
// 					overflow-y: auto;
// 				}

// 				.kanban-round-row {
// 					display: flex;
// 					align-items: center;

// 					gap: 8px;

// 					width: 100%;
// 					min-width: 0;
// 					max-width: 100%;

// 					font-size: 12px;

// 					box-sizing: border-box;
// 				}

// 				.kanban-round-badge {
// 					flex: 0 0 auto;

// 					font-weight: 600;
// 					color: var(--text-muted, #5d6472);

// 					min-width: 20px;
// 				}

// 				.kanban-round-date {
// 					flex: 1 1 auto;

// 					min-width: 0;
// 					max-width: 100%;

// 					color: var(--text-muted, #5d6472);

// 					white-space: nowrap;
// 					overflow: hidden;
// 					text-overflow: ellipsis;
// 				}

// 				.kanban-round-status {
// 					flex: 0 0 auto;

// 					margin-left: auto;

// 					max-width: 45%;

// 					font-size: 11px;
// 					padding: 1px 8px;

// 					white-space: nowrap;
// 					overflow: hidden;
// 					text-overflow: ellipsis;
// 				}

// 				.kanban-rounds-empty {
// 					margin-top: 8px;

// 					font-size: 12px;

// 					color: var(--text-muted, #5d6472);

// 					font-style: italic;
// 				}

// 				.kanban-rounds-toggle {
// 					margin-top: 2px;

// 					font-size: 12px;
// 					font-weight: 600;

// 					color: var(--text-brand, #5570f1);

// 					cursor: pointer;
// 					text-align: right;
// 				}

// 				.kanban-rounds-toggle:hover {
// 					text-decoration: underline;
// 				}
// 			`,
// 			)
// 			.appendTo("head");
// 	}

// 	// Auto-updates an interview's status to "Today" when its last round's
// 	// date matches today, via the same whitelisted endpoint drag-and-drop uses.
// 	function check_and_update_today_status(listview, name, rounds) {
// 		if (!rounds || !rounds.length) return;

// 		const lastRound = rounds[rounds.length - 1];
// 		if (!lastRound) return;

// 		if (FINAL_ROUND_STATUSES.has(lastRound.status)) return;
// 		if (lastRound.status === "Today") return;
// 		if (!is_today(lastRound.date_of_interview)) return;

// 		if (state.pendingStatusChange.has(name)) return;
// 		if (state.pendingTodayUpdate.has(name)) return;

// 		state.pendingTodayUpdate.add(name);

// 		Promise.resolve(apply_status_change(listview, name, "Today"))
// 			.catch((err) => {
// 				console.error("[Interview Kanban] auto Today status update failed", err);
// 			})
// 			.finally(() => {
// 				state.pendingTodayUpdate.delete(name);
// 			});
// 	}

// 	// Renders (or replaces) the round-summary block on each given Kanban card.
// 	function apply_round_summaries($wrappers) {
// 		$wrappers.each(function () {
// 			const $wrapper = $(this);
// 			const name = this.dataset.name;
// 			if (!name) return;

// 			const rounds = state.roundCache.get(name);
// 			if (rounds === undefined) return;

// 			const html = build_round_summary_html(name, rounds);
// 			const $existing = $wrapper.find(".kanban-rounds-summary, .kanban-rounds-empty");

// 			if ($existing.length) {
// 				$existing.replaceWith(html);
// 			} else {
// 				$wrapper.find(".kanban-card-doc").last().append(html);
// 			}
// 		});
// 	}

// 	// Builds the round-summary HTML for one interview's cached rounds.
// 	function build_round_summary_html(name, rounds) {
// 		if (!rounds || !rounds.length) {
// 			return `<div class="kanban-rounds-empty">${__("No rounds yet")}</div>`;
// 		}

// 		const expanded = state.expandedCards.has(name);
// 		const visible = expanded ? rounds : rounds.slice(0, ROUND_PREVIEW_LIMIT);

// 		const rows = visible
// 			.map((r) => {
// 				const color =
// 					window.STATUS_INDICATOR_MAP[r.status] ||
// 					window.STATUS_INDICATOR_MAP["Cancelled"];
// 				const date = r.date_of_interview
// 					? frappe.datetime.str_to_user(r.date_of_interview)
// 					: "—";

// 				return `
// 			<div class="kanban-round-row">
// 				<span class="kanban-round-badge">${frappe.utils.escape_html(r.round ?? "")}</span>
// 				<span class="kanban-round-date">${frappe.utils.escape_html(date)}</span>
// 				<span class="indicator-pill ${color} kanban-round-status">
// 					${frappe.utils.escape_html(r.status || __("Unknown"))}
// 				</span>
// 			</div>`;
// 			})
// 			.join("");

// 		let toggle = "";
// 		if (rounds.length > ROUND_PREVIEW_LIMIT) {
// 			const label = expanded
// 				? __("Show less")
// 				: __("+{0} more", [rounds.length - ROUND_PREVIEW_LIMIT]);
// 			toggle = `<div class="kanban-rounds-toggle" data-name="${frappe.utils.escape_html(name)}">${label}</div>`;
// 		}

// 		return `<div class="kanban-rounds-summary${expanded ? " expanded" : ""}">${rows}${toggle}</div>`;
// 	}

// 	// Binds the "show more / show less" toggle for a card's round list.
// 	function bind_round_toggle_handler(listview) {
// 		listview.page.wrapper
// 			.off("click.kanbanRoundsToggle")
// 			.on("click.kanbanRoundsToggle", ".kanban-rounds-toggle", function (e) {
// 				e.preventDefault();
// 				e.stopPropagation();

// 				const name = this.dataset.name;
// 				if (!name) return;

// 				if (state.expandedCards.has(name)) {
// 					state.expandedCards.delete(name);
// 				} else {
// 					state.expandedCards.add(name);
// 				}

// 				const $wrapper = listview.page.wrapper.find(
// 					`.kanban-card-wrapper[data-name="${name}"]`,
// 				);
// 				apply_round_summaries($wrapper);
// 			});
// 	}

// 	// Wires up all Kanban-specific behavior: CSS, round rendering, drag
// 	// tracking, and the round-toggle handler.
// 	function setup_kanban_overrides(listview) {
// 		inject_kanban_css();
// 		schedule_render(listview);
// 		bind_kanban_observer(listview);
// 		bind_drag_state_tracking(listview);
// 		bind_drag_end_listener(listview);
// 		bind_round_toggle_handler(listview);
// 	}

// 	// Detects the end of a card drag and checks for a resulting column/status change.
// 	function bind_drag_end_listener(listview) {
// 		if (state.dragEndBound) return;
// 		state.dragEndBound = true;

// 		const on_release = () => {
// 			if (!state.isDragging) return;
// 			state.isDragging = false;

// 			const lv = state.currentListview;
// 			if (!lv || !is_kanban_view(lv)) return;

// 			setTimeout(() => check_for_status_change_after_drop(lv), 150);
// 		};

// 		document.addEventListener("mouseup", on_release);
// 		document.addEventListener("touchend", on_release);
// 	}

// 	// Compares each card's post-drop column against its pre-drag baseline
// 	// and triggers a status change for any card that actually moved.
// 	function check_for_status_change_after_drop(listview) {
// 		const $wrappers = listview.page.wrapper.find(".kanban-card-wrapper[data-name]");

// 		$wrappers.each(function () {
// 			const name = this.dataset.name;
// 			if (!name) return;

// 			const columnValue = $(this)
// 				.closest(".kanban-column[data-column-value]")
// 				.attr("data-column-value");
// 			if (!columnValue) return;

// 			if (state.pendingStatusChange.has(name)) return;

// 			const previous = state.cardColumnState.get(name);
// 			if (previous === undefined) {
// 				state.cardColumnState.set(name, columnValue);
// 				return;
// 			}
// 			if (previous === columnValue) return;

// 			if (FINAL_ROUND_STATUSES.has(previous)) {
// 				frappe.msgprint({
// 					title: __("Status Locked"),
// 					indicator: "red",
// 					message: __(
// 						"This interview round is already '{0}' and its status cannot be changed further.",
// 						[previous],
// 					),
// 				});
// 				schedule_board_refresh(listview);
// 				return;
// 			}

// 			state.pendingStatusChange.add(name);
// 			state.cardColumnState.delete(name);

// 			const context = extract_card_context($(this));

// 			Promise.resolve(handle_kanban_status_change(listview, name, columnValue, context))
// 				.catch((err) => {
// 					if (err?.message !== "Cancelled by user") {
// 						console.error("[Interview Kanban] status update failed", err);
// 					}
// 				})
// 				.finally(() => {
// 					state.pendingStatusChange.delete(name);
// 				});
// 		});
// 	}

// 	// (Re)binds a MutationObserver on the Kanban board to re-render round
// 	// summaries whenever the board's DOM changes.
// 	function bind_kanban_observer(listview) {
// 		const board_el = listview.page.wrapper.find(".kanban")[0];
// 		if (!board_el) return;

// 		if (state.kanbanObserver && state.kanbanObservedEl === board_el && board_el.isConnected) {
// 			return;
// 		}

// 		if (state.kanbanObserver) {
// 			state.kanbanObserver.disconnect();
// 		}

// 		state.kanbanObservedEl = board_el;
// 		state.kanbanObserver = new MutationObserver((mutations) => {
// 			const isOwnMutation = mutations.every((m) =>
// 				Array.from(m.addedNodes).every(
// 					(n) =>
// 						n.nodeType === 1 &&
// 						(n.classList?.contains("kanban-rounds-summary") ||
// 							n.classList?.contains("kanban-rounds-empty")),
// 				),
// 			);
// 			if (isOwnMutation) return;

// 			schedule_render(listview);
// 		});

// 		state.kanbanObserver.observe(board_el, { childList: true, subtree: true });
// 	}

// 	// Debounces round-summary rendering to one call per animation frame,
// 	// skipping entirely while a card is being dragged.
// 	function schedule_render(listview) {
// 		if (state.renderScheduled) return;
// 		state.renderScheduled = true;

// 		requestAnimationFrame(() => {
// 			state.renderScheduled = false;
// 			if (state.isDragging) return;

// 			render_round_summary(listview);
// 			sync_column_baseline(listview);
// 		});
// 	}

// 	// Records each card's current column as the known-good baseline for
// 	// drag-change detection.
// 	function sync_column_baseline(listview) {
// 		listview.page.wrapper.find(".kanban-card-wrapper[data-name]").each(function () {
// 			const name = this.dataset.name;
// 			if (!name || state.pendingStatusChange.has(name)) return;

// 			const columnValue = $(this)
// 				.closest(".kanban-column[data-column-value]")
// 				.attr("data-column-value");
// 			if (!columnValue) return;

// 			state.cardColumnState.set(name, columnValue);
// 		});
// 	}

// 	// Tracks drag start on Kanban cards so rendering can pause during a drag.
// 	function bind_drag_state_tracking(listview) {
// 		listview.page.wrapper
// 			.off("mousedown.kanbanDrag touchstart.kanbanDrag")
// 			.on("mousedown.kanbanDrag touchstart.kanbanDrag", ".kanban-card-wrapper", () => {
// 				state.isDragging = true;
// 			});
// 	}

// 	// Reads a card's title/company/role directly from its DOM for use in confirmation dialogs.
// 	function extract_card_context($wrapper) {
// 		const title = $wrapper.find(".kanban-card-title").first().text().trim();
// 		const docLines = $wrapper.find(".kanban-card-doc > .text-muted");
// 		const company = $(docLines[0]).find("span").last().text().trim();
// 		const role = $(docLines[1]).find("span").last().text().trim();
// 		return { title, company, role };
// 	}

// 	// Renders cached round summaries immediately, then fetches summaries
// 	// for any cards not yet cached.
// 	function render_round_summary(listview) {
// 		const $wrappers = listview.page.wrapper.find(".kanban-card-wrapper[data-name]");
// 		if (!$wrappers.length) return;

// 		apply_round_summaries($wrappers);

// 		$wrappers.each(function () {
// 			const name = this.dataset.name;
// 			if (!name) return;
// 			const cachedRounds = state.roundCache.get(name);
// 			if (cachedRounds) check_and_update_today_status(listview, name, cachedRounds);
// 		});

// 		const namesToFetch = [];
// 		$wrappers.each(function () {
// 			const name = this.dataset.name;
// 			if (!name) return;
// 			if (state.roundCache.has(name) || state.roundInFlight.has(name)) return;
// 			namesToFetch.push(name);
// 		});

// 		if (!namesToFetch.length) return;

// 		namesToFetch.forEach((n) => state.roundInFlight.add(n));

// 		frappe.call({
// 			method: ROUND_SUMMARY_METHOD,
// 			args: { names: JSON.stringify(namesToFetch) },
// 			callback(r) {
// 				const data = r.message || {};
// 				Object.entries(data).forEach(([name, rounds]) => {
// 					state.roundCache.set(name, rounds);
// 					check_and_update_today_status(listview, name, rounds);
// 				});
// 				namesToFetch.forEach((n) => state.roundInFlight.delete(n));
// 				apply_round_summaries(
// 					listview.page.wrapper.find(".kanban-card-wrapper[data-name]"),
// 				);
// 			},
// 			error(err) {
// 				namesToFetch.forEach((n) => state.roundInFlight.delete(n));
// 				console.error("[Interview Kanban] round summary fetch failed", err);
// 			},
// 		});
// 	}

// 	// Routes a Kanban column-drop status change through confirmation
// 	// dialogs (for Cancelled/Rescheduled/Completed) before applying it.
// 	function handle_kanban_status_change(listview, interview_name, new_status, context = {}) {
// 		if (CANCELLED_LIKE_STATUSES.has(new_status)) {
// 			return prompt_cancellation_details(interview_name, new_status, context).then(
// 				(values) => {
// 					if (!values) {
// 						schedule_board_refresh(listview);
// 						return Promise.reject(new Error("Cancelled by user"));
// 					}
// 					return Promise.resolve(
// 						apply_status_change(listview, interview_name, new_status, values),
// 					);
// 				},
// 			);
// 		}

// 		if (new_status === "Completed") {
// 			return prompt_terminal_status_confirmation(interview_name, new_status, context).then(
// 				(confirmed) => {
// 					if (!confirmed) {
// 						schedule_board_refresh(listview);
// 						return Promise.reject(new Error("Cancelled by user"));
// 					}
// 					return Promise.resolve(
// 						apply_status_change(listview, interview_name, new_status),
// 					);
// 				},
// 			);
// 		}

// 		return Promise.resolve(apply_status_change(listview, interview_name, new_status));
// 	}

// 	// Confirms marking a round Completed (a terminal, unrevertable status).
// 	function prompt_terminal_status_confirmation(interview_name, status, context) {
// 		return new Promise((resolve) => {
// 			let settled = false;
// 			const resolve_once = (val) => {
// 				if (settled) return;
// 				settled = true;
// 				resolve(val);
// 			};

// 			const message = `
// 			<div style="margin-bottom: 10px;">
// 				<div style="font-weight: 600;">${frappe.utils.escape_html(context.title || interview_name)}</div>
// 				<div style="font-size: 12px; color: var(--text-muted, #5d6472); margin-top: 2px;">
// 					${frappe.utils.escape_html(context.company || "")}
// 					${context.role ? " · " + frappe.utils.escape_html(context.role) : ""}
// 				</div>
// 			</div>
// 			<div>${__("Mark this interview round as")} <span class="indicator-pill ${window.STATUS_INDICATOR_MAP[status] || window.STATUS_INDICATOR_MAP["Cancelled"]}">${frappe.utils.escape_html(status)}</span>?</div>
// 			<div style="margin-top: 8px; font-size: 12px; color: var(--text-muted, #5d6472);">
// 				${__("This status is final — it cannot be changed once confirmed.")}
// 			</div>
// 		`;

// 			frappe.confirm(
// 				message,
// 				() => resolve_once(true),
// 				() => resolve_once(false),
// 			);
// 		});
// 	}

// 	// Prompts for "Cancelled By" and "Reason of Cancel" before applying a
// 	// Cancelled/Rescheduled status.
// 	function prompt_cancellation_details(interview_name, status, context) {
// 		return new Promise((resolve) => {
// 			let settled = false;
// 			const resolve_once = (val) => {
// 				if (settled) return;
// 				settled = true;
// 				resolve(val);
// 			};

// 			const summary_html = `
// 			<div style="margin-bottom: 12px; padding: 10px 12px; background: var(--bg-gray, #f4f5f6); border-radius: 6px;">
// 				<div style="font-weight: 600;">${frappe.utils.escape_html(context.title || interview_name)}</div>
// 				<div style="font-size: 12px; color: var(--text-muted, #5d6472); margin-top: 2px;">
// 					${frappe.utils.escape_html(context.company || "")}
// 					${context.role ? " · " + frappe.utils.escape_html(context.role) : ""}
// 				</div>
// 				<div style="font-size: 12px; margin-top: 6px;">
// 					${__("Mark this interview round as")} <span class="indicator-pill ${window.STATUS_INDICATOR_MAP[status] || window.STATUS_INDICATOR_MAP["Cancelled"]}">${frappe.utils.escape_html(status)}</span>
// 				</div>
// 				<div style="margin-top: 8px; font-size: 12px; color: var(--text-muted, #5d6472);">
// 				${__("This status is final — it cannot be changed once confirmed.")}
// 			</div>
// 			</div>
// 		`;

// 			const dialog = new frappe.ui.Dialog({
// 				title: __("Confirm Status Change"),
// 				fields: [
// 					{ fieldtype: "HTML", fieldname: "summary", options: summary_html },
// 					{
// 						fieldtype: "Select",
// 						fieldname: "cancelled_by",
// 						label: __("Cancelled By"),
// 						options: ["Company", "Candidate"],
// 						reqd: 1,
// 					},
// 					{
// 						fieldtype: "Data",
// 						fieldname: "reason_of_cancel",
// 						label: __(`Reason of ${status}`),
// 						reqd: 1,
// 					},
// 				],
// 				primary_action_label: __("Confirm"),
// 				primary_action(values) {
// 					dialog.hide();
// 					resolve_once(values);
// 				},
// 				secondary_action_label: __("Keep Current Status"),

// 				secondary_action() {
// 					dialog.hide();
// 					resolve_once(null);
// 				},
// 			});

// 			dialog.$wrapper.on("hidden.bs.modal", () => {
// 				resolve_once(null);
// 			});

// 			dialog.show();
// 		});
// 	}

// 	// Applies a status change via the whitelisted update endpoint and
// 	// refreshes the board (reverting the card visually on failure).
// 	function apply_status_change(listview, interview_name, status, extra = {}) {
// 		return frappe
// 			.call({
// 				method: UPDATE_STATUS_METHOD,
// 				args: {
// 					interview: interview_name,
// 					status,
// 					cancelled_by: extra.cancelled_by,
// 					reason_of_cancel: extra.reason_of_cancel,
// 				},
// 			})
// 			.then((r) => {
// 				state.roundCache.delete(interview_name);
// 				schedule_board_refresh(listview);
// 				return r;
// 			})
// 			.catch((err) => {
// 				schedule_board_refresh(listview);
// 				throw err;
// 			});
// 	}

// 	// Debounces the post-update board refresh so it doesn't race Frappe's
// 	// own drag-order persistence call.
// 	function schedule_board_refresh(listview) {
// 		if (state.refreshTimer) clearTimeout(state.refreshTimer);
// 		state.refreshTimer = setTimeout(() => {
// 			state.refreshTimer = null;
// 			listview.refresh();
// 		}, 500);
// 	}

// 	// Returns true if the given date string is today.
// 	function is_today(date_str) {
// 		if (!date_str) return false;
// 		return date_str === frappe.datetime.get_today();
// 	}

// 	// Clears all Kanban-specific caches/observers once the user navigates
// 	// away from the Kanban view.
// 	function ensure_route_cleanup() {
// 		if (state.routeCleanupBound) return;
// 		state.routeCleanupBound = true;
// 		state.expandedCards.clear();
// 		state.roundToggleBound = false;

// 		frappe.router.on("change", function on_route_change() {
// 			if (window.location.pathname.includes("/view/kanban/Interview")) return;

// 			if (state.kanbanObserver) {
// 				state.kanbanObserver.disconnect();
// 				state.kanbanObserver = null;
// 				state.kanbanObservedEl = null;
// 			}
// 			state.roundCache.clear();
// 			state.roundInFlight.clear();
// 			state.cardColumnState.clear();
// 			state.pendingStatusChange.clear();
// 			state.routeCleanupBound = false;

// 			frappe.router.off("change", on_route_change);
// 		});
// 	}

// 	// Reads the currently selected marketing_link.
// 	function get_marketing_param() {
// 		return window.InterviewMarketingFilter.get();
// 	}

// 	// Persists the given value as the selected marketing_link.
// 	function set_marketing_param(value) {
// 		window.InterviewMarketingFilter.set(value);
// 	}

// 	// Triggers the marketing-customer auto-filter unless one is already being applied.
// 	function apply_marketing_auto_filter(listview) {
// 		if (state.marketingIsSetting) return;
// 		auto_apply_marketing_filter(listview);
// 	}

// 	// Returns true if the given marketing_link value is already an active filter on this listview.
// 	function marketing_filter_already_applied(listview, value) {
// 		try {
// 			const filters = listview.filter_area?.filter_list?.filters || [];
// 			return filters.some((f) => f.fieldname === "marketing_link" && f.value === value);
// 		} catch (e) {
// 			return false;
// 		}
// 	}

// 	// Resolves a default marketing_link if none is selected, then applies
// 	// it as a filter and updates the toolbar customer label.
// 	function auto_apply_marketing_filter(listview) {
// 		if (!listview.filter_area) return;

// 		window.ivw_ensure_marketing_param().then((value) => {
// 			if (!value) {
// 				const body = listview.page?.body;
// 				if (body) {
// 					body.html(`
// 						<div class="text-muted text-center mt-5">
// 							You are not assigned to any customer.
// 						</div>
// 					`);
// 				}
// 				return;
// 			}

// 			frappe.call({
// 				method: MARKETING_OPTIONS_METHOD,
// 				args: { param: value },
// 				callback(r) {
// 					const options = r.message || [];
// 					const label = options[0]?.label || value;

// 					update_customer_label(listview.page, label);

// 					if (marketing_filter_already_applied(listview, value)) {
// 						state.marketingAppliedValue = value;
// 						return;
// 					}

// 					state.marketingIsSetting = true;
// 					state.marketingAppliedValue = value;

// 					set_filter_without_loop(listview, value);

// 					setTimeout(() => {
// 						state.marketingIsSetting = false;
// 					}, 1000);
// 				},
// 			});
// 		});
// 	}

// 	// Replaces any existing marketing_link filter with the given value
// 	// without triggering the clear-filter guard.
// 	function set_filter_without_loop(listview, value) {
// 		try {
// 			const existing = listview.filter_area.filter_list.filters || [];
// 			listview.filter_area.filter_list.filters = existing.filter(
// 				(f) => f.fieldname !== "marketing_link",
// 			);
// 			listview.filter_area.add([["Interview", "marketing_link", "=", value]]);
// 		} catch (e) {
// 			listview.filter_area.clear();
// 			listview.filter_area.add([["Interview", "marketing_link", "=", value]]);
// 		}
// 	}

// 	// Removes marketing_link from the "+ Add a Filter" field picker for Interview.
// 	function patch_field_select_to_hide_marketing() {
// 		if (state.fieldSelectPatched) return;
// 		if (!frappe.ui || typeof frappe.ui.FieldSelect !== "function") return;
// 		state.fieldSelectPatched = true;

// 		const original_get_fields = frappe.ui.FieldSelect.prototype.get_fields;
// 		if (typeof original_get_fields !== "function") return;

// 		frappe.ui.FieldSelect.prototype.get_fields = function (...args) {
// 			let fields = original_get_fields.apply(this, args);
// 			if (this.doctype === "Interview" && Array.isArray(fields)) {
// 				fields = fields.filter((df) => df.fieldname !== "marketing_link");
// 			}
// 			return fields;
// 		};
// 	}

// 	// Hides "Marketing" from the filter-field dropdown and hides the
// 	// already-applied marketing_link filter row from the popover.
// 	function scrub_marketing_from_filter_popover() {
// 		if (state.currentListview?.doctype !== "Interview") return;

// 		document
// 			.querySelectorAll(".fieldname-select-area li, .fieldname-select-area [role='option']")
// 			.forEach((li) => {
// 				if (li.textContent.trim() === "Marketing") li.remove();
// 			});

// 		document.querySelectorAll(".filter-edit-area .filter-box").forEach((row) => {
// 			const isMarketingRow =
// 				row.querySelector("[data-fieldname='marketing_link']") ||
// 				row.querySelector(".fieldname-select-area input")?.value?.trim() === "Marketing";

// 			if (isMarketingRow) {
// 				row.style.display = "none";
// 				row.setAttribute("data-marketing-row-hidden", "1");
// 			}
// 		});
// 	}

// 	// Observes the filter popover and re-applies the marketing-link scrub on every DOM mutation.
// 	function bind_marketing_filter_dom_guard() {
// 		if (state.marketingFieldBlockerBound) return;
// 		state.marketingFieldBlockerBound = true;

// 		const observer = new MutationObserver(() => {
// 			if (!document.querySelector(".filter-edit-area")) return;
// 			scrub_marketing_from_filter_popover();
// 		});

// 		observer.observe(document.body, { childList: true, subtree: true });
// 	}

// 	// Wraps filter_area.clear()/filter_list.clear_filters() so any
// 	// non-internal clear silently reinstates the marketing_link filter.
// 	function lock_marketing_filter(listview) {
// 		const filter_area = listview.filter_area;
// 		if (!filter_area || filter_area.__marketingLockApplied) return;
// 		filter_area.__marketingLockApplied = true;

// 		if (typeof filter_area.clear === "function") {
// 			const original_clear = filter_area.clear.bind(filter_area);
// 			filter_area.clear = function (...args) {
// 				const result = original_clear(...args);
// 				if (!state.marketingIsSetting) {
// 					reapply_marketing_filter_after_clear(listview);
// 				}
// 				return result;
// 			};
// 		}

// 		const filter_list = filter_area.filter_list;
// 		if (filter_list && typeof filter_list.clear_filters === "function") {
// 			const original_list_clear = filter_list.clear_filters.bind(filter_list);
// 			filter_list.clear_filters = function (...args) {
// 				const result = original_list_clear(...args);
// 				if (!state.marketingIsSetting) {
// 					reapply_marketing_filter_after_clear(listview);
// 				}
// 				return result;
// 			};
// 		}
// 	}

// 	// Re-applies the marketing_link filter and refreshes the list after a clear.
// 	function reapply_marketing_filter_after_clear(listview) {
// 		const value = state.marketingAppliedValue || get_marketing_param();
// 		if (!value) return;

// 		state.marketingIsSetting = true;
// 		setTimeout(() => {
// 			set_filter_without_loop(listview, value);
// 			listview.refresh();
// 			setTimeout(() => {
// 				state.marketingIsSetting = false;
// 			}, 1000);
// 		}, 50);
// 	}

// 	// Creates (once) the "Customer: —" pill in the list toolbar.
// 	function ensure_customer_label(page) {
// 		if (page.customer_label) return page.customer_label;

// 		const label = $(`
// 			<div class="marketing-customer-pill"
// 				style="
// 					display: inline-flex; align-items: center; gap: 6px;
// 					padding: 4px 10px; margin-right: 8px; border-radius: 10px;
// 					background: #ffffff; border: 1px solid #9ea3ac;
// 					font-size: 15px; white-space: nowrap;
// 				">
// 				<span style="color:#5d6472; font-weight:500;">Customer:</span>
// 				<span class="marketing-customer-value" style="color:#111827; font-weight:600;">—</span>
// 			</div>
// 		`);

// 		page.inner_toolbar.prepend(label);
// 		page.customer_label = label;
// 		return label;
// 	}

// 	// Updates the toolbar customer pill's label text.
// 	function update_customer_label(page, label) {
// 		const pill = ensure_customer_label(page);
// 		const valueEl = pill.find(".marketing-customer-value");

// 		if (!label) {
// 			valueEl.text("—");
// 			pill.css("opacity", 0.6);
// 			return;
// 		}

// 		valueEl.text(label);
// 		pill.css("opacity", 1);
// 	}

// 	// Opens the "Select Customer" dialog for manually choosing a marketing customer.
// 	function open_marketing_customer_dialog(listview) {
// 		const current_value = get_marketing_param();

// 		const dialog = new frappe.ui.Dialog({
// 			title: "Filter Interviews by Customer",
// 			fields: [
// 				{
// 					fieldtype: "Link",
// 					fieldname: "marketing",
// 					label: "Customer",
// 					default: current_value,
// 					options: "Marketing",
// 					reqd: 1,
// 					get_query() {
// 						return { query: MARKETING_SEARCH_METHOD };
// 					},
// 				},
// 			],
// 			primary_action_label: "Apply",
// 			primary_action(values) {
// 				dialog.hide();
// 				state.marketingAppliedValue = null;
// 				set_marketing_param(values.marketing);
// 				apply_marketing_filter(listview, values.marketing);

// 				const marketing_field = dialog.get_field("marketing");
// 				update_customer_label(
// 					listview.page,
// 					marketing_field.get_label?.() || values.marketing,
// 				);
// 			},
// 		});

// 		dialog.show();
// 	}

// 	// Applies the given marketing_link as the list's active filter.
// 	function apply_marketing_filter(listview, value) {
// 		if (!value || !listview.filter_area) return;

// 		state.marketingIsSetting = true;
// 		state.marketingAppliedValue = value;

// 		listview.filter_area.clear();
// 		listview.filter_area.add("Interview", "marketing_link", "=", value);

// 		setTimeout(() => {
// 			state.marketingIsSetting = false;
// 		}, 1000);
// 	}
// })();

// ---------------------------------------------------------------------
// interview_list.js
//
// List + Kanban view customization for Interview.
//
// Requires interview_common.js loaded first.
//
// CHANGES FOR MULTI-CUSTOMER SUPPORT:
//   - "Select Customer" dialog is now a MultiCheck list (+ Select all /
//     Clear all) instead of a single Link field, populated from
//     get_assigned_marketing_customers().
//   - Every place that built a single-value marketing_link filter now
//     builds an ["marketing_link", "in", [...]] filter.
//   - List view: unchanged pagination (still whatever the 20/100/500/2500
//     picker in the UI has selected) — it just now includes all selected
//     customers via the IN filter.
//   - Kanban view: NEW per-column infinite scroll. Each status column
//     tracks its own limit_start and independently fetches more of ITS
//     OWN cards (ordered by creation desc) as the user scrolls near the
//     bottom of that column, via frappe.client.get_list (which goes
//     through interview_query server-side, same as everything else).
//     New cards are appended using markup shaped to match what
//     extract_card_context() and the round-summary renderer already
//     expect, so all the existing drag/status/round-summary machinery
//     picks them up for free via the existing MutationObserver.
// ---------------------------------------------------------------------

(function () {
	"use strict";

	const ROUND_SUMMARY_METHOD =
		"verp_staffing.marketing.doctype.interview.interview.get_round_summary_for_kanban";
	const UPDATE_STATUS_METHOD =
		"verp_staffing.marketing.doctype.interview.interview.update_interview_status_from_kanban";
	const ASSIGNED_CUSTOMERS_METHOD =
		"verp_staffing.marketing.doctype.interview.interview.get_assigned_marketing_customers";

	const CANCELLED_LIKE_STATUSES = new Set(["Cancelled", "Rescheduled"]);
	const FINAL_ROUND_STATUSES = new Set(["Cancelled", "Rescheduled", "Completed"]);

	const ROUND_PREVIEW_LIMIT = 5;
	const KANBAN_COLUMN_PAGE_SIZE = 20;
	const KANBAN_SCROLL_THRESHOLD_PX = 150;

	const state = {
		marketingIsSetting: false,
		kanbanObserver: null,
		kanbanObservedEl: null,
		refreshTimer: null,
		kanbanStyleInjected: false,
		roundCache: new Map(),
		roundInFlight: new Set(),
		renderScheduled: false,
		routeCleanupBound: false,
		cardColumnState: new Map(),
		pendingStatusChange: new Set(),
		currentListview: null,
		isDragging: false,
		expandedCards: new Set(),
		fieldSelectPatched: false,
		marketingFieldBlockerBound: false,
		pendingTodayUpdate: new Set(),
		assignedCustomersCache: null, // [{value,label}] — fetched once, reused by dialog + labels
		// Per-column infinite-scroll state: status -> {limitStart, hasMore, loading}
		kanbanColumnState: new Map(),
	};

	frappe.listview_settings["Interview"] = {
		onload(listview) {
			frappe.breadcrumbs.all[frappe.get_route_str()] = {
				workspace: "Interviews",
				doctype: listview.doctype,
				type: "List",
			};
			frappe.breadcrumbs.update();
		},

		refresh(listview) {
			const page = listview.page;
			if (!page) return;

			state.currentListview = listview;

			hide_kanban_chrome(page);

			if (!page.customer_filter_btn_added) {
				page.customer_filter_btn_added = true;
				page.add_inner_button(__("Select Customer"), () => {
					open_marketing_customer_dialog(listview);
				});
			}

			apply_marketing_auto_filter(listview);
			patch_field_select_to_hide_marketing();
			bind_marketing_filter_dom_guard();
			lock_marketing_filter(listview);

			if (is_kanban_view(listview)) {
				setup_kanban_overrides(listview);
				ensure_route_cleanup();
			} else {
				// Leaving Kanban (or never entering it) — column pagination
				// state is meaningless outside that view.
				state.kanbanColumnState.clear();
			}
		},
	};

	// -----------------------------------------------------------------
	// Kanban chrome
	// -----------------------------------------------------------------

	function hide_kanban_chrome(page) {
		requestAnimationFrame(() => {
			page.wrapper.find(".add-new-column").hide();
			page.inner_toolbar.find("button").each(function () {
				if ($(this).text().includes("Select Kanban")) {
					$(this).parent().hide();
				}
			});
		});
	}

	function is_kanban_view(listview) {
		return (
			listview.view_name === "Kanban" || window.location.pathname.includes("/view/kanban/")
		);
	}

	function inject_kanban_css() {
		if (state.kanbanStyleInjected) return;
		state.kanbanStyleInjected = true;

		$("<style>")
			.attr("id", "interview-kanban-overrides")
			.html(
				`
				.kanban {
					overflow-x: auto !important;
					overflow-y: hidden !important;
					box-sizing: border-box !important;
				}

				.kanban-column {
					width: 360px !important;
					min-width: 360px !important;
					max-width: 360px !important;
					flex: 0 0 360px !important;
					box-sizing: border-box !important;
				}

				.kanban-cards {
					width: 100% !important;
					min-width: 0 !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
					/* NEW: each column scrolls independently, bounded to the
					   board's visible height, so infinite scroll has a real
					   scroll container to listen on instead of growing the
					   page indefinitely. */
					max-height: calc(100vh - 260px) !important;
					overflow-y: auto !important;
				}

				.kanban-card-wrapper {
					display: block !important;
					width: 100% !important;
					min-width: 0 !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.kanban-card-wrapper > .kanban-card {
					display: block !important;
					width: 100% !important;
					min-width: 0 !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.kanban-card-body {
					width: 100% !important;
					min-width: 0 !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.kanban-card-doc {
					width: 100% !important;
					min-width: 0 !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.kanban-card-wrapper.sortable-drag,
				.kanban-card-wrapper.sortable-fallback {
					width: 360px !important;
					min-width: 360px !important;
					max-width: 360px !important;
					flex: 0 0 360px !important;
					box-sizing: border-box !important;
				}

				.kanban-card-wrapper.sortable-drag > .kanban-card,
				.kanban-card-wrapper.sortable-fallback > .kanban-card {
					width: 360px !important;
					min-width: 360px !important;
					max-width: 360px !important;
					box-sizing: border-box !important;
				}

				.kanban-card-wrapper.sortable-ghost {
					width: 100% !important;
					min-width: 0 !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.kanban-card-wrapper.sortable-ghost > .kanban-card {
					width: 100% !important;
					min-width: 0 !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.sortable-drag .kanban-card-title,
				.sortable-fallback .kanban-card-title,
				.sortable-drag .kanban-card-doc,
				.sortable-fallback .kanban-card-doc {
					min-width: 0 !important;
					max-width: 100% !important;
					overflow: hidden !important;
				}

				.sortable-drag .kanban-title-area,
				.sortable-fallback .kanban-title-area {
					min-width: 0 !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.kanban-card-wrapper:hover {
					width: 100% !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.kanban-card-wrapper:hover > .kanban-card {
					width: 100% !important;
					max-width: 100% !important;
					box-sizing: border-box !important;
				}

				.add-card {
					display: none !important;
				}

				.kanban-card-meta {
					display: none !important;
				}

				.kanban-rounds-summary {
					width: 100%;
					min-width: 0;
					max-width: 100%;
					box-sizing: border-box;
					margin-top: 8px;
					padding-top: 6px;
					border-top: 1px solid var(--border-color, #e0e0e0);
					display: flex;
					flex-direction: column;
					gap: 5px;
				}

				.kanban-rounds-summary.expanded {
					max-height: 220px;
					overflow-y: auto;
				}

				.kanban-round-row {
					display: flex;
					align-items: center;
					gap: 8px;
					width: 100%;
					min-width: 0;
					max-width: 100%;
					font-size: 12px;
					box-sizing: border-box;
				}

				.kanban-round-badge {
					flex: 0 0 auto;
					font-weight: 600;
					color: var(--text-muted, #5d6472);
					min-width: 20px;
				}

				.kanban-round-date {
					flex: 1 1 auto;
					min-width: 0;
					max-width: 100%;
					color: var(--text-muted, #5d6472);
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}

				.kanban-round-status {
					flex: 0 0 auto;
					margin-left: auto;
					max-width: 45%;
					font-size: 11px;
					padding: 1px 8px;
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}

				.kanban-rounds-empty {
					margin-top: 8px;
					font-size: 12px;
					color: var(--text-muted, #5d6472);
					font-style: italic;
				}

				.kanban-rounds-toggle {
					margin-top: 2px;
					font-size: 12px;
					font-weight: 600;
					color: var(--text-brand, #5570f1);
					cursor: pointer;
					text-align: right;
				}

				.kanban-rounds-toggle:hover {
					text-decoration: underline;
				}

				.kanban-column-loading {
					text-align: center;
					padding: 10px 0;
					font-size: 12px;
					color: var(--text-muted, #5d6472);
				}

				.kanban-column-end {
					text-align: center;
					padding: 8px 0;
					font-size: 11px;
					color: var(--text-muted, #99a1ac);
					font-style: italic;
				}
			`,
			)
			.appendTo("head");
	}

	function check_and_update_today_status(listview, name, rounds) {
		if (!rounds || !rounds.length) return;

		const lastRound = rounds[rounds.length - 1];
		if (!lastRound) return;

		if (FINAL_ROUND_STATUSES.has(lastRound.status)) return;
		if (lastRound.status === "Today") return;
		if (!is_today(lastRound.date_of_interview)) return;

		if (state.pendingStatusChange.has(name)) return;
		if (state.pendingTodayUpdate.has(name)) return;

		state.pendingTodayUpdate.add(name);

		Promise.resolve(apply_status_change(listview, name, "Today"))
			.catch((err) => {
				console.error("[Interview Kanban] auto Today status update failed", err);
			})
			.finally(() => {
				state.pendingTodayUpdate.delete(name);
			});
	}

	function apply_round_summaries($wrappers) {
		$wrappers.each(function () {
			const $wrapper = $(this);
			const name = this.dataset.name;
			if (!name) return;

			const rounds = state.roundCache.get(name);
			if (rounds === undefined) return;

			const html = build_round_summary_html(name, rounds);
			const $existing = $wrapper.find(".kanban-rounds-summary, .kanban-rounds-empty");

			if ($existing.length) {
				$existing.replaceWith(html);
			} else {
				$wrapper.find(".kanban-card-doc").last().append(html);
			}
		});
	}

	function build_round_summary_html(name, rounds) {
		if (!rounds || !rounds.length) {
			return `<div class="kanban-rounds-empty">${__("No rounds yet")}</div>`;
		}

		const expanded = state.expandedCards.has(name);
		const visible = expanded ? rounds : rounds.slice(0, ROUND_PREVIEW_LIMIT);

		const rows = visible
			.map((r) => {
				const color =
					window.STATUS_INDICATOR_MAP[r.status] ||
					window.STATUS_INDICATOR_MAP["Cancelled"];
				const date = r.date_of_interview
					? frappe.datetime.str_to_user(r.date_of_interview)
					: "—";

				return `
			<div class="kanban-round-row">
				<span class="kanban-round-badge">${frappe.utils.escape_html(r.round ?? "")}</span>
				<span class="kanban-round-date">${frappe.utils.escape_html(date)}</span>
				<span class="indicator-pill ${color} kanban-round-status">
					${frappe.utils.escape_html(r.status || __("Unknown"))}
				</span>
			</div>`;
			})
			.join("");

		let toggle = "";
		if (rounds.length > ROUND_PREVIEW_LIMIT) {
			const label = expanded
				? __("Show less")
				: __("+{0} more", [rounds.length - ROUND_PREVIEW_LIMIT]);
			toggle = `<div class="kanban-rounds-toggle" data-name="${frappe.utils.escape_html(name)}">${label}</div>`;
		}

		return `<div class="kanban-rounds-summary${expanded ? " expanded" : ""}">${rows}${toggle}</div>`;
	}

	function bind_round_toggle_handler(listview) {
		listview.page.wrapper
			.off("click.kanbanRoundsToggle")
			.on("click.kanbanRoundsToggle", ".kanban-rounds-toggle", function (e) {
				e.preventDefault();
				e.stopPropagation();

				const name = this.dataset.name;
				if (!name) return;

				if (state.expandedCards.has(name)) {
					state.expandedCards.delete(name);
				} else {
					state.expandedCards.add(name);
				}

				const $wrapper = listview.page.wrapper.find(
					`.kanban-card-wrapper[data-name="${name}"]`,
				);
				apply_round_summaries($wrapper);
			});
	}

	function setup_kanban_overrides(listview) {
		inject_kanban_css();
		schedule_render(listview);
		bind_kanban_observer(listview);
		bind_drag_state_tracking(listview);
		bind_drag_end_listener(listview);
		bind_round_toggle_handler(listview);
		// Deferred one tick: columns need to exist in the DOM (from the
		// initial Frappe-driven render) before we can attach per-column
		// scroll listeners and seed each column's limitStart from however
		// many cards Frappe's own first fetch already put there.
		setTimeout(() => bind_kanban_infinite_scroll(listview), 0);
	}

	function bind_drag_end_listener(listview) {
		if (state.dragEndBound) return;
		state.dragEndBound = true;

		const on_release = () => {
			if (!state.isDragging) return;
			state.isDragging = false;

			const lv = state.currentListview;
			if (!lv || !is_kanban_view(lv)) return;

			setTimeout(() => check_for_status_change_after_drop(lv), 150);
		};

		document.addEventListener("mouseup", on_release);
		document.addEventListener("touchend", on_release);
	}

	function check_for_status_change_after_drop(listview) {
		const $wrappers = listview.page.wrapper.find(".kanban-card-wrapper[data-name]");

		$wrappers.each(function () {
			const name = this.dataset.name;
			if (!name) return;

			const columnValue = $(this)
				.closest(".kanban-column[data-column-value]")
				.attr("data-column-value");
			if (!columnValue) return;

			if (state.pendingStatusChange.has(name)) return;

			const previous = state.cardColumnState.get(name);
			if (previous === undefined) {
				state.cardColumnState.set(name, columnValue);
				return;
			}
			if (previous === columnValue) return;

			if (FINAL_ROUND_STATUSES.has(previous)) {
				frappe.msgprint({
					title: __("Status Locked"),
					indicator: "red",
					message: __(
						"This interview round is already '{0}' and its status cannot be changed further.",
						[previous],
					),
				});
				schedule_board_refresh(listview);
				return;
			}

			state.pendingStatusChange.add(name);
			state.cardColumnState.delete(name);

			const context = extract_card_context($(this));

			Promise.resolve(handle_kanban_status_change(listview, name, columnValue, context))
				.catch((err) => {
					if (err?.message !== "Cancelled by user") {
						console.error("[Interview Kanban] status update failed", err);
					}
				})
				.finally(() => {
					state.pendingStatusChange.delete(name);
				});
		});
	}

	function bind_kanban_observer(listview) {
		const board_el = listview.page.wrapper.find(".kanban")[0];
		if (!board_el) return;

		if (state.kanbanObserver && state.kanbanObservedEl === board_el && board_el.isConnected) {
			return;
		}

		if (state.kanbanObserver) {
			state.kanbanObserver.disconnect();
		}

		state.kanbanObservedEl = board_el;
		state.kanbanObserver = new MutationObserver((mutations) => {
			const isOwnMutation = mutations.every((m) =>
				Array.from(m.addedNodes).every(
					(n) =>
						n.nodeType === 1 &&
						(n.classList?.contains("kanban-rounds-summary") ||
							n.classList?.contains("kanban-rounds-empty") ||
							n.classList?.contains("kanban-column-loading") ||
							n.classList?.contains("kanban-column-end")),
				),
			);
			if (isOwnMutation) return;

			schedule_render(listview);
			// A fresh board render (e.g. after Select Customer / drag
			// refresh) wipes columns back to Frappe's first-page fetch —
			// re-attach scroll listeners and reset per-column pagination
			// so infinite scroll keeps working against the new baseline.
			state.kanbanColumnState.clear();
			setTimeout(() => bind_kanban_infinite_scroll(listview), 0);
		});

		state.kanbanObserver.observe(board_el, { childList: true, subtree: true });
	}

	function schedule_render(listview) {
		if (state.renderScheduled) return;
		state.renderScheduled = true;

		requestAnimationFrame(() => {
			state.renderScheduled = false;
			if (state.isDragging) return;

			render_round_summary(listview);
			sync_column_baseline(listview);
		});
	}

	function sync_column_baseline(listview) {
		listview.page.wrapper.find(".kanban-card-wrapper[data-name]").each(function () {
			const name = this.dataset.name;
			if (!name || state.pendingStatusChange.has(name)) return;

			const columnValue = $(this)
				.closest(".kanban-column[data-column-value]")
				.attr("data-column-value");
			if (!columnValue) return;

			state.cardColumnState.set(name, columnValue);
		});
	}

	function bind_drag_state_tracking(listview) {
		listview.page.wrapper
			.off("mousedown.kanbanDrag touchstart.kanbanDrag")
			.on("mousedown.kanbanDrag touchstart.kanbanDrag", ".kanban-card-wrapper", () => {
				state.isDragging = true;
			});
	}

	function extract_card_context($wrapper) {
		const title = $wrapper.find(".kanban-card-title").first().text().trim();
		const docLines = $wrapper.find(".kanban-card-doc > .text-muted");
		const company = $(docLines[0]).find("span").last().text().trim();
		const role = $(docLines[1]).find("span").last().text().trim();
		return { title, company, role };
	}

	function render_round_summary(listview) {
		const $wrappers = listview.page.wrapper.find(".kanban-card-wrapper[data-name]");
		if (!$wrappers.length) return;

		apply_round_summaries($wrappers);

		$wrappers.each(function () {
			const name = this.dataset.name;
			if (!name) return;
			const cachedRounds = state.roundCache.get(name);
			if (cachedRounds) check_and_update_today_status(listview, name, cachedRounds);
		});

		const namesToFetch = [];
		$wrappers.each(function () {
			const name = this.dataset.name;
			if (!name) return;
			if (state.roundCache.has(name) || state.roundInFlight.has(name)) return;
			namesToFetch.push(name);
		});

		if (!namesToFetch.length) return;

		namesToFetch.forEach((n) => state.roundInFlight.add(n));

		frappe.call({
			method: ROUND_SUMMARY_METHOD,
			args: { names: JSON.stringify(namesToFetch) },
			callback(r) {
				const data = r.message || {};
				Object.entries(data).forEach(([name, rounds]) => {
					state.roundCache.set(name, rounds);
					check_and_update_today_status(listview, name, rounds);
				});
				namesToFetch.forEach((n) => state.roundInFlight.delete(n));
				apply_round_summaries(
					listview.page.wrapper.find(".kanban-card-wrapper[data-name]"),
				);
			},
			error(err) {
				namesToFetch.forEach((n) => state.roundInFlight.delete(n));
				console.error("[Interview Kanban] round summary fetch failed", err);
			},
		});
	}

	// -----------------------------------------------------------------
	// NEW: per-column infinite scroll
	//
	// Each Kanban column (identified by its data-column-value, which must
	// equal the Interview.status value it represents) gets its own
	// independent scroll listener on its .kanban-cards container and its
	// own limitStart counter. Scrolling near the bottom of a column fetches
	// the NEXT page of THAT status only, ordered by creation desc, filtered
	// to the currently selected customers, and appends the results as new
	// card DOM at the bottom of that column.
	//
	// Uses frappe.client.get_list directly (not the Kanban board's own
	// fetch) because that's an ORM-level call and therefore automatically
	// respects the interview_query permission_query_condition — no extra
	// server work needed beyond what's already registered for List view.
	// -----------------------------------------------------------------

	function bind_kanban_infinite_scroll(listview) {
		if (!is_kanban_view(listview)) return;

		const $columns = listview.page.wrapper.find(".kanban-column[data-column-value]");

		$columns.each(function () {
			const status = this.dataset.columnValue;
			if (!status) return;

			const $cardsContainer = $(this).find(".kanban-cards").first();
			if (!$cardsContainer.length) return;

			// Seed pagination state from however many cards are already
			// rendered in this column (Frappe's own first-page fetch, or a
			// previous infinite-scroll pass), so the next fetch continues
			// from the right offset instead of re-fetching from zero.
			if (!state.kanbanColumnState.has(status)) {
				const existing_count = $cardsContainer.find(
					".kanban-card-wrapper[data-name]",
				).length;
				state.kanbanColumnState.set(status, {
					limitStart: existing_count,
					hasMore: true,
					loading: false,
				});
			}

			if ($cardsContainer.data("ivwScrollBound")) return;
			$cardsContainer.data("ivwScrollBound", true);

			const debounced_check = frappe.utils.debounce(function () {
				const el = $cardsContainer.get(0);
				if (!el) return;
				if (
					el.scrollTop + el.clientHeight >=
					el.scrollHeight - KANBAN_SCROLL_THRESHOLD_PX
				) {
					load_more_kanban_cards(listview, status, $cardsContainer);
				}
			}, 150);

			$cardsContainer.on("scroll.kanbanInfiniteScroll", debounced_check);

			// A column that opens already short enough to not need scrolling
			// (e.g. Cancelled with 3 cards) would otherwise never fire a
			// scroll event to trigger its "load more" — check once up front.
			debounced_check();
		});
	}

	function load_more_kanban_cards(listview, status, $container) {
		const col_state = state.kanbanColumnState.get(status);
		if (!col_state || col_state.loading || !col_state.hasMore) return;

		col_state.loading = true;
		show_column_loading($container, true);

		window.ivw_ensure_marketing_param().then((marketing_links) => {
			if (!marketing_links || !marketing_links.length) {
				col_state.loading = false;
				show_column_loading($container, false);
				return;
			}

			frappe
				.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "Interview",
						filters: [
							["status", "=", status],
							["marketing_link", "in", marketing_links],
						],
						fields: ["name", "company", "role", "status"],
						order_by: "creation desc",
						limit_start: col_state.limitStart,
						limit_page_length: KANBAN_COLUMN_PAGE_SIZE,
					},
				})
				.then((r) => {
					const rows = r.message || [];
					col_state.hasMore = rows.length === KANBAN_COLUMN_PAGE_SIZE;
					col_state.limitStart += rows.length;
					append_kanban_cards($container, rows);
					show_column_loading($container, false);
					if (!col_state.hasMore && rows.length) {
						show_column_end($container);
					}
					col_state.loading = false;
				})
				.catch((err) => {
					console.error("[Interview Kanban] infinite scroll fetch failed", err);
					col_state.loading = false;
					show_column_loading($container, false);
				});
		});
	}

	function show_column_loading($container, show) {
		let $el = $container.find(".kanban-column-loading");
		if (show) {
			if (!$el.length) {
				$el = $(`<div class="kanban-column-loading">${__("Loading…")}</div>`);
				$container.append($el);
			}
		} else {
			$el.remove();
		}
	}

	function show_column_end($container) {
		if ($container.find(".kanban-column-end").length) return;
		$container.append(`<div class="kanban-column-end">${__("No more interviews")}</div>`);
	}

	// Builds card markup shaped to match what extract_card_context() and
	// the round-summary renderer expect from Frappe's own native Kanban
	// cards (kanban-card-title, kanban-card-doc > .text-muted > span:last),
	// so all existing drag/status/round-summary logic works on these
	// dynamically-appended cards without any special-casing.
	function build_kanban_card_html(row) {
		const esc = frappe.utils.escape_html;
		return `
			<div class="kanban-card-wrapper" data-name="${esc(row.name)}">
				<div class="kanban-card">
					<div class="kanban-card-body">
						<div class="kanban-title-area">
							<span class="kanban-card-title">${esc(row.name)}</span>
						</div>
						<div class="kanban-card-doc">
							<div class="text-muted"><span>${__("Company")}</span>: <span>${esc(row.company || "")}</span></div>
							<div class="text-muted"><span>${__("Role")}</span>: <span>${esc(row.role || "")}</span></div>
						</div>
					</div>
				</div>
			</div>
		`;
	}

	function append_kanban_cards($container, rows) {
		if (!rows.length) return;

		// Insert before the trailing "loading"/"end" markers rather than
		// after them, so those stay pinned to the bottom of the column.
		const $markers = $container.find(".kanban-column-loading, .kanban-column-end");

		rows.forEach((row) => {
			// Guard against a card that's already present (e.g. Frappe's own
			// first-page fetch and our page-2 fetch overlapping by one row
			// due to a create/delete happening between the two calls).
			if ($container.find(`.kanban-card-wrapper[data-name="${row.name}"]`).length) return;

			const $card = $(build_kanban_card_html(row));
			if ($markers.length) {
				$card.insertBefore($markers.first());
			} else {
				$container.append($card);
			}
		});

		// Newly-appended cards aren't picked up by the round-summary
		// pipeline until the next scheduled render — the kanbanObserver
		// will normally catch this DOM change on its own, but scheduling
		// explicitly here avoids depending on that observer's own
		// "was this our own mutation" filter logic for a case it wasn't
		// written to recognize.
		schedule_render(state.currentListview);
	}

	// -----------------------------------------------------------------
	// Status-change interception (drag-and-drop on the Kanban board)
	// -----------------------------------------------------------------

	function handle_kanban_status_change(listview, interview_name, new_status, context = {}) {
		if (CANCELLED_LIKE_STATUSES.has(new_status)) {
			return prompt_cancellation_details(interview_name, new_status, context).then(
				(values) => {
					if (!values) {
						schedule_board_refresh(listview);
						return Promise.reject(new Error("Cancelled by user"));
					}
					return Promise.resolve(
						apply_status_change(listview, interview_name, new_status, values),
					);
				},
			);
		}

		if (new_status === "Completed") {
			return prompt_terminal_status_confirmation(interview_name, new_status, context).then(
				(confirmed) => {
					if (!confirmed) {
						schedule_board_refresh(listview);
						return Promise.reject(new Error("Cancelled by user"));
					}
					return Promise.resolve(
						apply_status_change(listview, interview_name, new_status),
					);
				},
			);
		}

		return Promise.resolve(apply_status_change(listview, interview_name, new_status));
	}

	function prompt_terminal_status_confirmation(interview_name, status, context) {
		return new Promise((resolve) => {
			let settled = false;
			const resolve_once = (val) => {
				if (settled) return;
				settled = true;
				resolve(val);
			};

			const message = `
			<div style="margin-bottom: 10px;">
				<div style="font-weight: 600;">${frappe.utils.escape_html(context.title || interview_name)}</div>
				<div style="font-size: 12px; color: var(--text-muted, #5d6472); margin-top: 2px;">
					${frappe.utils.escape_html(context.company || "")}
					${context.role ? " · " + frappe.utils.escape_html(context.role) : ""}
				</div>
			</div>
			<div>${__("Mark this interview round as")} <span class="indicator-pill ${window.STATUS_INDICATOR_MAP[status] || window.STATUS_INDICATOR_MAP["Cancelled"]}">${frappe.utils.escape_html(status)}</span>?</div>
			<div style="margin-top: 8px; font-size: 12px; color: var(--text-muted, #5d6472);">
				${__("This status is final — it cannot be changed once confirmed.")}
			</div>
		`;

			frappe.confirm(
				message,
				() => resolve_once(true),
				() => resolve_once(false),
			);
		});
	}

	function prompt_cancellation_details(interview_name, status, context) {
		return new Promise((resolve) => {
			let settled = false;
			const resolve_once = (val) => {
				if (settled) return;
				settled = true;
				resolve(val);
			};

			const summary_html = `
			<div style="margin-bottom: 12px; padding: 10px 12px; background: var(--bg-gray, #f4f5f6); border-radius: 6px;">
				<div style="font-weight: 600;">${frappe.utils.escape_html(context.title || interview_name)}</div>
				<div style="font-size: 12px; color: var(--text-muted, #5d6472); margin-top: 2px;">
					${frappe.utils.escape_html(context.company || "")}
					${context.role ? " · " + frappe.utils.escape_html(context.role) : ""}
				</div>
				<div style="font-size: 12px; margin-top: 6px;">
					${__("Mark this interview round as")} <span class="indicator-pill ${window.STATUS_INDICATOR_MAP[status] || window.STATUS_INDICATOR_MAP["Cancelled"]}">${frappe.utils.escape_html(status)}</span>
				</div>
				<div style="margin-top: 8px; font-size: 12px; color: var(--text-muted, #5d6472);">
				${__("This status is final — it cannot be changed once confirmed.")}
			</div>
			</div>
		`;

			const dialog = new frappe.ui.Dialog({
				title: __("Confirm Status Change"),
				fields: [
					{ fieldtype: "HTML", fieldname: "summary", options: summary_html },
					{
						fieldtype: "Select",
						fieldname: "cancelled_by",
						label: __("Cancelled By"),
						options: ["Company", "Candidate"],
						reqd: 1,
					},
					{
						fieldtype: "Data",
						fieldname: "reason_of_cancel",
						label: __(`Reason of ${status}`),
						reqd: 1,
					},
				],
				primary_action_label: __("Confirm"),
				primary_action(values) {
					dialog.hide();
					resolve_once(values);
				},
				secondary_action_label: __("Keep Current Status"),

				secondary_action() {
					dialog.hide();
					resolve_once(null);
				},
			});

			dialog.$wrapper.on("hidden.bs.modal", () => {
				resolve_once(null);
			});

			dialog.show();
		});
	}

	function apply_status_change(listview, interview_name, status, extra = {}) {
		return frappe
			.call({
				method: UPDATE_STATUS_METHOD,
				args: {
					interview: interview_name,
					status,
					cancelled_by: extra.cancelled_by,
					reason_of_cancel: extra.reason_of_cancel,
				},
			})
			.then((r) => {
				state.roundCache.delete(interview_name);
				schedule_board_refresh(listview);
				return r;
			})
			.catch((err) => {
				schedule_board_refresh(listview);
				throw err;
			});
	}

	function schedule_board_refresh(listview) {
		if (state.refreshTimer) clearTimeout(state.refreshTimer);
		state.refreshTimer = setTimeout(() => {
			state.refreshTimer = null;
			listview.refresh();
		}, 500);
	}

	function is_today(date_str) {
		if (!date_str) return false;
		return date_str === frappe.datetime.get_today();
	}

	function ensure_route_cleanup() {
		if (state.routeCleanupBound) return;
		state.routeCleanupBound = true;
		state.expandedCards.clear();
		state.roundToggleBound = false;

		frappe.router.on("change", function on_route_change() {
			if (window.location.pathname.includes("/view/kanban/Interview")) return;

			if (state.kanbanObserver) {
				state.kanbanObserver.disconnect();
				state.kanbanObserver = null;
				state.kanbanObservedEl = null;
			}
			state.roundCache.clear();
			state.roundInFlight.clear();
			state.cardColumnState.clear();
			state.pendingStatusChange.clear();
			state.kanbanColumnState.clear();
			state.routeCleanupBound = false;

			frappe.router.off("change", on_route_change);
		});
	}

	// -----------------------------------------------------------------
	// Marketing customer multi-select
	// -----------------------------------------------------------------

	function get_marketing_params() {
		return window.InterviewMarketingFilter.get();
	}

	function set_marketing_params(values) {
		window.InterviewMarketingFilter.set(values);
	}

	function apply_marketing_auto_filter(listview) {
		if (state.marketingIsSetting) return;
		auto_apply_marketing_filter(listview);
	}

	// A filter is considered "already applied" if a marketing_link IN
	// filter exists at all and its value set matches the current
	// selection exactly (order-independent) — not just "some filter with
	// this fieldname exists", since the selection itself can change.
	function marketing_filter_already_applied(listview, values) {
		try {
			const filters = listview.filter_area?.filter_list?.filters || [];
			const existing = filters.find((f) => f.fieldname === "marketing_link");
			if (!existing) return false;
			const existing_values = Array.isArray(existing.value)
				? existing.value
				: [existing.value];
			if (existing_values.length !== values.length) return false;
			const a = existing_values.slice().sort();
			const b = values.slice().sort();
			return a.every((v, i) => v === b[i]);
		} catch (e) {
			return false;
		}
	}

	function fetch_assigned_customers() {
		if (state.assignedCustomersCache) {
			return Promise.resolve(state.assignedCustomersCache);
		}
		return frappe
			.call({ method: ASSIGNED_CUSTOMERS_METHOD })
			.then((r) => {
				state.assignedCustomersCache = r.message || [];
				return state.assignedCustomersCache;
			})
			.catch(() => []);
	}

	function auto_apply_marketing_filter(listview) {
		if (!listview.filter_area) return;

		window.ivw_ensure_marketing_param().then((values) => {
			if (!values || !values.length) {
				const body = listview.page?.body;
				if (body) {
					body.html(`
						<div class="text-muted text-center mt-5">
							You are not assigned to any customer.
						</div>
					`);
				}
				return;
			}

			fetch_assigned_customers().then((options) => {
				update_customer_label(listview.page, options, values);

				if (marketing_filter_already_applied(listview, values)) {
					return;
				}

				state.marketingIsSetting = true;
				set_filter_without_loop(listview, values);
				setTimeout(() => {
					state.marketingIsSetting = false;
				}, 1000);
			});
		});
	}

	function set_filter_without_loop(listview, values) {
		try {
			const existing = listview.filter_area.filter_list.filters || [];
			listview.filter_area.filter_list.filters = existing.filter(
				(f) => f.fieldname !== "marketing_link",
			);
			listview.filter_area.add([["Interview", "marketing_link", "in", values]]);
		} catch (e) {
			listview.filter_area.clear();
			listview.filter_area.add([["Interview", "marketing_link", "in", values]]);
		}
	}

	function patch_field_select_to_hide_marketing() {
		if (state.fieldSelectPatched) return;
		if (!frappe.ui || typeof frappe.ui.FieldSelect !== "function") return;
		state.fieldSelectPatched = true;

		const original_get_fields = frappe.ui.FieldSelect.prototype.get_fields;
		if (typeof original_get_fields !== "function") return;

		frappe.ui.FieldSelect.prototype.get_fields = function (...args) {
			let fields = original_get_fields.apply(this, args);
			if (this.doctype === "Interview" && Array.isArray(fields)) {
				fields = fields.filter((df) => df.fieldname !== "marketing_link");
			}
			return fields;
		};
	}

	function scrub_marketing_from_filter_popover() {
		if (state.currentListview?.doctype !== "Interview") return;

		document
			.querySelectorAll(".fieldname-select-area li, .fieldname-select-area [role='option']")
			.forEach((li) => {
				if (li.textContent.trim() === "Marketing") li.remove();
			});

		document.querySelectorAll(".filter-edit-area .filter-box").forEach((row) => {
			const isMarketingRow =
				row.querySelector("[data-fieldname='marketing_link']") ||
				row.querySelector(".fieldname-select-area input")?.value?.trim() === "Marketing";

			if (isMarketingRow) {
				row.style.display = "none";
				row.setAttribute("data-marketing-row-hidden", "1");
			}
		});
	}

	function bind_marketing_filter_dom_guard() {
		if (state.marketingFieldBlockerBound) return;
		state.marketingFieldBlockerBound = true;

		const observer = new MutationObserver(() => {
			if (!document.querySelector(".filter-edit-area")) return;
			scrub_marketing_from_filter_popover();
		});

		observer.observe(document.body, { childList: true, subtree: true });
	}

	function lock_marketing_filter(listview) {
		const filter_area = listview.filter_area;
		if (!filter_area || filter_area.__marketingLockApplied) return;
		filter_area.__marketingLockApplied = true;

		if (typeof filter_area.clear === "function") {
			const original_clear = filter_area.clear.bind(filter_area);
			filter_area.clear = function (...args) {
				const result = original_clear(...args);
				if (!state.marketingIsSetting) {
					reapply_marketing_filter_after_clear(listview);
				}
				return result;
			};
		}

		const filter_list = filter_area.filter_list;
		if (filter_list && typeof filter_list.clear_filters === "function") {
			const original_list_clear = filter_list.clear_filters.bind(filter_list);
			filter_list.clear_filters = function (...args) {
				const result = original_list_clear(...args);
				if (!state.marketingIsSetting) {
					reapply_marketing_filter_after_clear(listview);
				}
				return result;
			};
		}
	}

	function reapply_marketing_filter_after_clear(listview) {
		const values = get_marketing_params();
		if (!values || !values.length) return;

		state.marketingIsSetting = true;
		setTimeout(() => {
			set_filter_without_loop(listview, values);
			listview.refresh();
			setTimeout(() => {
				state.marketingIsSetting = false;
			}, 1000);
		}, 50);
	}

	function ensure_customer_label(page) {
		if (page.customer_label) return page.customer_label;

		const label = $(`
			<div class="marketing-customer-pill"
				style="
					display: inline-flex; align-items: center; gap: 6px;
					padding: 4px 10px; margin-right: 8px; border-radius: 10px;
					background: #ffffff; border: 1px solid #9ea3ac;
					font-size: 15px; white-space: nowrap;
				">
				<span style="color:#5d6472; font-weight:500;">Customers:</span>
				<span class="marketing-customer-value" style="color:#111827; font-weight:600;">—</span>
			</div>
		`);

		page.inner_toolbar.prepend(label);
		page.customer_label = label;
		return label;
	}

	// Renders "CUSTOMER_A" for one, "CUSTOMER_A +2 more" for several, "All
	// customers (5)" when every assigned customer is currently selected.
	function update_customer_label(page, options, selected_values) {
		const pill = ensure_customer_label(page);
		const valueEl = pill.find(".marketing-customer-value");

		if (!selected_values || !selected_values.length) {
			valueEl.text("—");
			pill.css("opacity", 0.6);
			return;
		}

		const label_by_value = {};
		(options || []).forEach((o) => {
			label_by_value[o.value] = o.label || o.value;
		});

		let text;
		if (options && options.length && selected_values.length === options.length) {
			text = __("All customers ({0})", [selected_values.length]);
		} else {
			const first_label = label_by_value[selected_values[0]] || selected_values[0];
			text =
				selected_values.length === 1
					? first_label
					: __("{0} +{1} more", [first_label, selected_values.length - 1]);
		}

		valueEl.text(text);
		pill.css("opacity", 1);
	}

	// interview_list.js

	function inject_marketing_dialog_styles() {
		if (document.getElementById("interview-marketing-dialog-styles")) return;
		$("<style>")
			.attr("id", "interview-marketing-dialog-styles")
			.html(
				`
            .marketing-dialog-toolbar {
                display: flex;
                gap: 8px;
                margin-bottom: 12px;
            }
            .marketing-dialog-toolbar .btn {
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 14px;
                border: 1px solid var(--border-color, #d1d8dd);
                background: var(--bg-color, #fff);
                color: var(--text-color, #1c1c1c);
                cursor: pointer;
            }
            .marketing-dialog-toolbar .btn:hover {
                background: var(--bg-gray, #f4f5f6);
            }
            .marketing-dialog-toolbar .btn:active {
                background: var(--bg-gray-light, #eceef0);
            }

            /* MultiCheck labels — truncate long customer names, tooltip on hover */
            [data-fieldname="customers"] .label-area {
                display: inline-block;
                max-width: 190px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                vertical-align: middle;
            }
            [data-fieldname="customers"] .checkbox {
                max-width: 100%;
            }
        `,
			)
			.appendTo("head");
	}

	// Multi-select dialog: MultiCheck field populated from
	// get_assigned_marketing_customers, plus Select all / Clear all links.
	function open_marketing_customer_dialog(listview) {
		inject_marketing_dialog_styles();

		fetch_assigned_customers().then((options) => {
			if (!options.length) {
				frappe.msgprint(__("You are not assigned to any customer."));
				return;
			}

			const current_values = get_marketing_params();

			const multicheck_options = options.map((o) => ({
				label: o.label,
				value: o.value,
				checked: current_values.includes(o.value) ? 1 : 0,
			}));

			// Real buttons instead of plain links.
			const toolbar_html = `
            <div class="marketing-dialog-toolbar">
                <button type="button" class="btn btn-default" data-action="select-all">${__("Select all")}</button>
                <button type="button" class="btn btn-default" data-action="clear-all">${__("Clear all")}</button>
            </div>
        `;

			const dialog = new frappe.ui.Dialog({
				title: __("Filter Interviews by Customer(s)"),
				fields: [
					{ fieldtype: "HTML", fieldname: "toolbar", options: toolbar_html },
					{
						fieldtype: "MultiCheck",
						fieldname: "customers",
						label: __("Customers"),
						options: multicheck_options,
						value: current_values,
						columns: 2,
					},
				],
				primary_action_label: __("Apply"),
				primary_action(values) {
					const selected = values.customers || [];
					if (!selected.length) {
						frappe.msgprint(__("Select at least one customer."));
						return;
					}
					dialog.hide();
					set_marketing_params(selected);
					apply_marketing_filter(listview, selected);
					update_customer_label(listview.page, options, selected);
				},
			});

			const customers_control = dialog.fields_dict.customers;

			dialog.$wrapper.on("click", '[data-action="select-all"]', (e) => {
				e.preventDefault();
				customers_control.$wrapper
					.find('input[type="checkbox"]')
					.prop("checked", true)
					.trigger("change");
			});
			dialog.$wrapper.on("click", '[data-action="clear-all"]', (e) => {
				e.preventDefault();
				customers_control.$wrapper
					.find('input[type="checkbox"]')
					.prop("checked", false)
					.trigger("change");
			});

			dialog.show();

			// Give every truncated label a native tooltip with the full name.
			// Must run after show() — MultiCheck builds its DOM in make_input(),
			// which fires as part of dialog rendering.
			customers_control.$wrapper.find(".label-area").each(function () {
				$(this).attr("title", $(this).text().trim());
			});
		});
	}

	function apply_marketing_filter(listview, values) {
		if (!values || !values.length || !listview.filter_area) return;

		state.marketingIsSetting = true;

		listview.filter_area.clear();
		listview.filter_area.add("Interview", "marketing_link", "in", values);

		setTimeout(() => {
			state.marketingIsSetting = false;
		}, 1000);
	}
})();
