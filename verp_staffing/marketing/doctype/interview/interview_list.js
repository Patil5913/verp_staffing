// List + Kanban view customization

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
	const DIALOG_PAGE_SIZE = 20;
	const DIALOG_SCROLL_THRESHOLD_PX = 80;
	const DIALOG_SEARCH_DEBOUNCE_MS = 300;

	const state = {
		marketingIsSetting: false,
		lastAppliedKey: null,
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
		pendingTodayUpdate: new Set(),
		assignedCustomersCache: null,
		kanbanColumnState: new Map(),
	};

	frappe.listview_settings["Interview"] = {
		// Registers the Interviews breadcrumb workspace for this listview.
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

			if (is_kanban_view(listview)) {
				setup_kanban_overrides(listview);
				ensure_route_cleanup();
			} else {
				state.kanbanColumnState.clear();
			}
		},
	};

	// Returns true if filter_area's currently-applied marketing_link filter
	// (if any) already matches `values` exactly (order-independent), so
	// callers can skip a redundant re-add.
	function values_match_current_filter(listview, values) {
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

	// One-way sync that pushes the authoritative customer selection into this
	// view's own native filter_area (so the "Filters" chip matches), without
	// ever reading filter_area back into shared state.
	function sync_native_filter_display(listview, values) {
		if (!listview.filter_area || !values || !values.length) return;
		if (values_match_current_filter(listview, values)) return;

		state.marketingIsSetting = true;
		try {
			const filter_list = listview.filter_area.filter_list;
			const existing = filter_list.filters || [];
			filter_list.filters = existing.filter((f) => f.fieldname !== "marketing_link");
			listview.filter_area.add([["Interview", "marketing_link", "in", values]]);
		} catch (e) {}
		setTimeout(() => {
			state.marketingIsSetting = false;
		}, 300);
	}

	// Hides the native "add new column" and "Select Kanban" controls from
	// the Kanban board's toolbar.
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

	// Returns true when the current listview is the Kanban view.
	function is_kanban_view(listview) {
		return (
			listview.view_name === "Kanban" || window.location.pathname.includes("/view/kanban/")
		);
	}

	// Injects the Kanban board's layout, card, and round-summary CSS into
	// the document head once.
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

	// Auto-transitions an interview's last round to "Today" status once,
	// if it's not already in a final/Today state and its date is today.
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

	// Renders (or re-renders) the round-summary block into each given
	// Kanban card wrapper, using whatever is currently in the round cache.
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

	// Builds the HTML for a card's round-summary list (rows plus an
	// expand/collapse toggle when there are more rounds than the preview limit).
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

	// Binds the click handler for a card's "+N more / Show less" round
	// toggle, tracking expanded state per card and re-rendering that card.
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

	// Wires up every Kanban-specific override (styles, rendering, drag
	// tracking, round toggles, infinite scroll) for the current board render.
	function setup_kanban_overrides(listview) {
		inject_kanban_css();
		schedule_render(listview);
		bind_kanban_observer(listview);
		bind_drag_state_tracking(listview);
		bind_drag_end_listener(listview);
		bind_round_toggle_handler(listview);
		setTimeout(() => bind_kanban_infinite_scroll(listview), 0);
	}

	// Binds a single global mouseup/touchend listener (once) that, after a
	// Kanban drag ends, checks whether any card's column actually changed.
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

	// Compares every card's current column against its last-known column;
	// for any card that moved, blocks the move if its prior status was
	// final, otherwise kicks off the status-change flow for that card.
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

	// Observes the Kanban board's DOM for non-cosmetic mutations and
	// re-schedules a round-summary render (and rebinds infinite scroll)
	// whenever the board is rebuilt.
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
			state.kanbanColumnState.clear();
			setTimeout(() => bind_kanban_infinite_scroll(listview), 0);
		});

		state.kanbanObserver.observe(board_el, { childList: true, subtree: true });
	}

	// Debounces round-summary rendering to a single animation frame,
	// skipping it entirely while a drag is in progress.
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

	// Records each visible card's current column as its baseline, so a
	// later drag-end can detect which cards actually changed column.
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

	// Flags state.isDragging on mousedown/touchstart over a Kanban card, so
	// other handlers can suppress work while a drag is in progress.
	function bind_drag_state_tracking(listview) {
		listview.page.wrapper
			.off("mousedown.kanbanDrag touchstart.kanbanDrag")
			.on("mousedown.kanbanDrag touchstart.kanbanDrag", ".kanban-card-wrapper", () => {
				state.isDragging = true;
			});
	}

	// Reads the title, company, and role text back out of a rendered card
	// wrapper, for use in confirmation dialogs.
	function extract_card_context($wrapper) {
		const title = $wrapper.find(".kanban-card-title").first().text().trim();
		const docLines = $wrapper.find(".kanban-card-doc > .text-muted");
		const company = $(docLines[0]).find("span").last().text().trim();
		const role = $(docLines[1]).find("span").last().text().trim();
		return { title, company, role };
	}

	// Renders round summaries into every visible card, auto-updates any
	// card whose last round should now be "Today", and fetches round data
	// for whichever cards aren't cached yet.
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

	// Binds a debounced scroll listener to each Kanban column's card
	// container (once per container) that loads the next page of cards
	// when the user scrolls near the bottom, seeding pagination state
	// from the number of cards already rendered.
	function bind_kanban_infinite_scroll(listview) {
		if (!is_kanban_view(listview)) return;

		const $columns = listview.page.wrapper.find(".kanban-column[data-column-value]");

		$columns.each(function () {
			const status = this.dataset.columnValue;
			if (!status) return;

			const $cardsContainer = $(this).find(".kanban-cards").first();
			if (!$cardsContainer.length) return;

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
			debounced_check();
		});
	}

	// Fetches and appends the next page of cards for a single Kanban
	// column, scoped to the current customer selection, updating that
	// column's pagination state and loading/end-of-list indicators.
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

	// Shows or hides the "Loading…" indicator at the bottom of a Kanban
	// column's card container.
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

	// Appends a "No more interviews" end-of-list marker to a Kanban
	// column's card container, if not already present.
	function show_column_end($container) {
		if ($container.find(".kanban-column-end").length) return;
		$container.append(`<div class="kanban-column-end">${__("No more interviews")}</div>`);
	}

	// Builds the HTML markup for a single lazily-loaded Kanban card.
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

	// Appends newly-fetched rows as Kanban cards ahead of the
	// loading/end markers, skipping any row already rendered, then
	// re-schedules a round-summary render for the new cards.
	function append_kanban_cards($container, rows) {
		if (!rows.length) return;

		const $markers = $container.find(".kanban-column-loading, .kanban-column-end");

		rows.forEach((row) => {
			if ($container.find(`.kanban-card-wrapper[data-name="${row.name}"]`).length) return;

			const $card = $(build_kanban_card_html(row));
			if ($markers.length) {
				$card.insertBefore($markers.first());
			} else {
				$container.append($card);
			}
		});

		schedule_render(state.currentListview);
	}

	// Routes a Kanban drag-drop status change to the right confirmation
	// flow (cancellation-details prompt, terminal-status confirmation, or
	// a direct update) based on the target status.
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

	// Shows a confirmation dialog for moving a card into the terminal
	// "Completed" status, resolving true/false based on the user's choice.
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

	// Opens a dialog collecting "Cancelled By" and a reason before moving a
	// card into a cancelled-like status, resolving those values or null if
	// the user backs out.
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

	// Calls the backend to persist an interview's new status, invalidates
	// its cached round data, and schedules a board refresh either way.
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

	// Debounces a listview refresh so rapid consecutive status changes
	// only trigger a single board reload.
	function schedule_board_refresh(listview) {
		if (state.refreshTimer) clearTimeout(state.refreshTimer);
		state.refreshTimer = setTimeout(() => {
			state.refreshTimer = null;
			listview.refresh();
		}, 500);
	}

	// Returns true when the given date string equals today's date.
	function is_today(date_str) {
		if (!date_str) return false;
		return date_str === frappe.datetime.get_today();
	}

	// Binds a one-time route-change listener that, once the user navigates
	// away from the Interview Kanban view, tears down all Kanban-specific
	// observers and per-card/per-column state.
	function ensure_route_cleanup() {
		if (state.routeCleanupBound) return;
		state.routeCleanupBound = true;
		state.expandedCards.clear();

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

	// Returns the currently selected customer list from shared filter state.
	function get_marketing_params() {
		return window.InterviewMarketingFilter.get();
	}

	// Persists a new customer selection to shared filter state.
	function set_marketing_params(values) {
		window.InterviewMarketingFilter.set(values);
	}

	// Fetches and caches the full unpaginated list of customers the user is
	// assigned to, for use in labels/counts (not for filtering).
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

	// Resolves the current/default customer selection, updates the toolbar
	// pill and native filter display, and — only if the selection actually
	// changed since it was last applied — triggers one listview refresh so
	// the shared frappe.call gate's filters take effect.
	function apply_marketing_auto_filter(listview) {
		if (state.marketingIsSetting) return;

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
			});

			sync_native_filter_display(listview, values);

			const key = values.slice().sort().join(",");
			if (key === state.lastAppliedKey) return;

			state.marketingIsSetting = true;
			state.lastAppliedKey = key;
			listview.refresh();
			setTimeout(() => {
				state.marketingIsSetting = false;
			}, 300);
		});
	}

	// Lazily creates (or returns the existing) "Customers: …" pill element
	// in the page's inner toolbar.
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

	// Updates the toolbar's "Customers: …" pill text to reflect the
	// current selection (single name, "+N more", "All customers (N)", or
	// a dash when nothing is selected).
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

	// Injects the multi-select customer dialog's toolbar/list/row CSS into
	// the document head once.
	function inject_marketing_dialog_styles() {
		if (document.getElementById("interview-marketing-dialog-styles")) return;
		$("<style>")
			.attr("id", "interview-marketing-dialog-styles")
			.html(
				`
				.marketing-dialog-toolbar {
					display: flex;
					align-items: center;
					gap: 8px;
					margin-bottom: 12px;
				}
				.marketing-dialog-toolbar .btn {
					flex: 0 0 auto;
					border-radius: 6px;
					font-size: 12px;
					font-weight: 600;
					padding: 4px 14px;
					border: 1px solid var(--border-color, #d1d8dd);
					background: var(--bg-color, #fff);
					color: var(--text-color, #1c1c1c);
					cursor: pointer;
					white-space: nowrap;
				}
				.marketing-dialog-toolbar .btn:hover {
					background: var(--bg-gray, #f4f5f6);
				}
				.marketing-dialog-toolbar .btn:active {
					background: var(--bg-gray-light, #eceef0);
				}
				.marketing-dialog-search {
					flex: 1 1 auto;
					min-width: 0;
					padding: 5px 10px;
					font-size: 13px;
					border-radius: 6px;
					border: 1px solid var(--border-color, #d1d8dd);
				}
				.marketing-dialog-count {
					margin-bottom: 8px;
					font-size: 12px;
					color: var(--text-muted, #5d6472);
				}
				.marketing-dialog-list {
					max-height: 340px;
					overflow-y: auto;
					border: 1px solid var(--border-color, #e0e0e0);
					border-radius: 6px;
					padding: 6px 8px;
					display: grid;
					grid-template-columns: 1fr 1fr;
					gap: 2px 12px;
					align-content: start;
				}
				.marketing-dialog-row {
					display: flex;
					align-items: center;
					gap: 8px;
					padding: 6px 8px;
					border-radius: 4px;
					cursor: pointer;
					min-width: 0;
				}
				.marketing-dialog-row:hover {
					background: var(--bg-gray, #f4f5f6);
				}
				.marketing-dialog-row input[type="checkbox"] {
					flex: 0 0 auto;
					margin: 0;
				}
				.marketing-dialog-row label {
					flex: 1 1 auto;
					min-width: 0;
					margin: 0;
					overflow: hidden;
					text-overflow: ellipsis;
					white-space: nowrap;
					cursor: pointer;
					font-weight: 400;
				}
				.marketing-dialog-status {
					grid-column: 1 / -1;
					text-align: center;
					padding: 10px 0;
					font-size: 12px;
					color: var(--text-muted, #5d6472);
				}
			`,
			)
			.appendTo("head");
	}

	// Builds and shows the multi-select "Filter Interviews by Customer(s)"
	// dialog: renders a searchable, paginated, checkbox list of assigned
	// customers with select-all/clear-all controls, and on Apply persists
	// the chosen selection and refreshes the listview.
	function open_marketing_customer_dialog(listview) {
		inject_marketing_dialog_styles();

		const current_values = get_marketing_params();
		const selected = new Set(current_values);

		const dlg_state = {
			loaded: [],
			search_term: "",
			start: 0,
			hasMore: true,
			loading: false,
		};

		const toolbar_html = `
			<div class="marketing-dialog-toolbar">
				<button type="button" class="btn btn-default" data-action="select-all">${__("Select all")}</button>
				<button type="button" class="btn btn-default" data-action="clear-all">${__("Clear all")}</button>
				<input type="text" class="marketing-dialog-search" data-action="search"
					placeholder="${__("Search customers…")}" autocomplete="off" />
			</div>
			<div class="marketing-dialog-count" data-el="count"></div>
			<div class="marketing-dialog-list" data-el="list"></div>
		`;

		const dialog = new frappe.ui.Dialog({
			title: __("Filter Interviews by Customer(s)"),
			fields: [{ fieldtype: "HTML", fieldname: "body", options: toolbar_html }],
			primary_action_label: __("Apply"),
			primary_action() {
				const values = Array.from(selected);
				if (!values.length) {
					frappe.msgprint(__("Select at least one customer."));
					return;
				}
				dialog.hide();
				set_marketing_params(values);
				const key = values.slice().sort().join(",");
				state.lastAppliedKey = key;
				fetch_assigned_customers().then((options) => {
					update_customer_label(listview.page, options, values);
				});
				listview.refresh();
			},
		});

		const $wrapper = dialog.$wrapper;
		const $list = $wrapper.find('[data-el="list"]');
		const $count = $wrapper.find('[data-el="count"]');
		const $search = $wrapper.find('[data-action="search"]');

		// Updates the "N selected" count label from the current selection.
		function render_count() {
			$count.text(__("{0} selected", [selected.size]));
		}

		// Builds the HTML for a single checkbox row in the customer list.
		function render_row(option) {
			const esc = frappe.utils.escape_html;
			const checked = selected.has(option.value) ? "checked" : "";
			const row_id = `ivw-cust-${esc(option.value)}`;
			return `
				<div class="marketing-dialog-row" data-value="${esc(option.value)}">
					<input type="checkbox" id="${row_id}" ${checked} />
					<label for="${row_id}" title="${esc(option.label)}">${esc(option.label)}</label>
				</div>
			`;
		}

		// Shows, updates, or clears the status row (loading/empty/error
		// message) at the bottom of the customer list.
		function render_status(text) {
			let $status = $list.find(".marketing-dialog-status");
			if (!text) {
				$status.remove();
				return;
			}
			if (!$status.length) {
				$status = $(`<div class="marketing-dialog-status"></div>`);
				$list.append($status);
			}
			$status.text(text);
		}

		// Appends newly-fetched customer rows to the list, ahead of the
		// status row if one is present.
		function append_rows(options) {
			const $status = $list.find(".marketing-dialog-status");
			options.forEach((o) => {
				const $row = $(render_row(o));
				if ($status.length) {
					$row.insertBefore($status);
				} else {
					$list.append($row);
				}
			});
		}

		// Fetches the next (or, on reset, the first) page of customers for
		// the active search term and appends them to the dialog's list.
		function fetch_page(reset) {
			if (dlg_state.loading) return;
			if (!reset && !dlg_state.hasMore) return;

			if (reset) {
				dlg_state.loaded = [];
				dlg_state.start = 0;
				dlg_state.hasMore = true;
				$list.empty();
			}

			dlg_state.loading = true;
			render_status(__("Loading…"));

			frappe
				.call({
					method: ASSIGNED_CUSTOMERS_METHOD,
					args: {
						txt: dlg_state.search_term,
						start: dlg_state.start,
						page_length: DIALOG_PAGE_SIZE,
					},
				})
				.then((r) => {
					const rows = r.message || [];
					dlg_state.hasMore = rows.length === DIALOG_PAGE_SIZE;
					dlg_state.start += rows.length;
					dlg_state.loaded = dlg_state.loaded.concat(rows);
					dlg_state.loading = false;

					render_status(null);
					append_rows(rows);

					if (!dlg_state.loaded.length) {
						render_status(__("No customers found."));
					}
				})
				.catch(() => {
					dlg_state.loading = false;
					render_status(__("Failed to load customers."));
				});
		}

		$list.on(
			"scroll",
			frappe.utils.debounce(function () {
				const el = $list.get(0);
				if (!el) return;
				if (
					el.scrollTop + el.clientHeight >=
					el.scrollHeight - DIALOG_SCROLL_THRESHOLD_PX
				) {
					fetch_page(false);
				}
			}, 150),
		);

		$list.on("change", 'input[type="checkbox"]', function () {
			const value = $(this).closest(".marketing-dialog-row").data("value");
			if (!value) return;
			if (this.checked) {
				selected.add(value);
			} else {
				selected.delete(value);
			}
			render_count();
		});

		$list.on("click", ".marketing-dialog-row", function (e) {
			if ($(e.target).closest("input, label").length) return;
			$(this).find('input[type="checkbox"]').trigger("click");
		});

		$wrapper.on("click", '[data-action="select-all"]', (e) => {
			e.preventDefault();
			dlg_state.loaded.forEach((o) => selected.add(o.value));
			$list.find('input[type="checkbox"]').prop("checked", true);
			render_count();
		});

		$wrapper.on("click", '[data-action="clear-all"]', (e) => {
			e.preventDefault();
			dlg_state.loaded.forEach((o) => selected.delete(o.value));
			$list.find('input[type="checkbox"]').prop("checked", false);
			render_count();
		});

		$search.on(
			"input",
			frappe.utils.debounce(function () {
				dlg_state.search_term = $search.val().trim();
				fetch_page(true);
			}, DIALOG_SEARCH_DEBOUNCE_MS),
		);

		dialog.show();
		render_count();
		fetch_page(true);
	}
})();