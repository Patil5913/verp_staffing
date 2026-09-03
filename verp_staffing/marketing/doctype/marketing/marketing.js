// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing", {
	setup(frm) {
		$(frm.wrapper).on("shown.bs.tab", ".nav-link", () => {
			render_tab_data(frm);
		});

	},
	async refresh(frm) {
		window.render_notes(frm);
		window.render_activity_section(frm);
		add_owner_grid_column(frm, "job_application_count");
		window.fetch_and_render_resume(frm);

		if (frm.doc.status === "Completed") {
			frm.set_df_property("status", "read_only", 1);
		}
		render_tab_data(frm);

		ensure_job_application_lock_patch(frm);

		frappe.call({
			method: "verp_staffing.crm.api.helpers._is_superior_in_department",
			args: {
				assign_to: frm.doc.assign_to,
				current_user: frappe.session.user,
				department: "Marketing",
			},
			callback(r) {
				if (!r.message) return;
				const is_superior = r.message.is_superior;

				frm.set_df_property("target", "read_only", !is_superior);
				if (frm.doc.start_date) {
					frm.set_df_property("start_date", "read_only", !is_superior);
				}

				const jobGrid = frm.fields_dict["job_application_count"].grid;
				jobGrid.update_docfield_property("date", "read_only", !is_superior); // unchanged — whole-column lock is intentional here

				frm.__mkt_job_app_is_superior = is_superior;
				apply_job_application_row_locks(frm, is_superior);

				frm.refresh_field("target");
			},
			error(err) {
				console.error("Permission check failed", err);
			},
		});

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "Marketing";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		frm.add_custom_button(__("Create Interview"), () => {
			open_create_interview_dialog(frm);
		});

		frm.set_query("assign_to", () => {
			return {
				query: "verp_staffing.crm.api.helpers.get_assign_to_by_service",
				filters: {
					service: "Marketing",
					customer: frm.doc.customer,
				},
			};
		});

		window.add_forward_button(frm, (service_name = "Marketing"));
		// to display the lead details

		if (!frm.is_new()) {
			frm.set_df_property("customer", "read_only", 1);
		}
		window.setup_service_permission_button(frm);

		// to display the interview list
		render_interview_list(frm);

		const display_fields = await window.get_display_fields(frm.doctype);

		window.render_customer_related_html({
			frm: frm,
			html_field: "customer_details_html",
			customer: frm.doc.customer,
			fields: display_fields,
		});

		window.setup_service_permission_button(frm);
	},

	customer(frm) {
		frm.trigger("refresh");
	},
});

function apply_job_application_row_locks(frm, is_superior) {
	const grid = frm.fields_dict["job_application_count"].grid;
	const today = frappe.datetime.get_today();

	(grid.grid_rows || []).forEach((grid_row) => {
		if (!grid_row.doc) return; // skip filter/search row

		const is_own_row = grid_row.doc.owner === frappe.session.user;
		const is_today = grid_row.doc.date === today;
		const locked = !is_superior && (!is_today || !is_own_row);

		["large_application", "small_application"].forEach((fieldname) => {
			set_row_field_readonly(grid_row, fieldname, locked);
		});
	});
}

function set_row_field_readonly(grid_row, fieldname, locked) {
	const grid = grid_row.grid;

	// clone docfields for this row only, same pattern as CR History locking —
	// avoids mutating the shared array used by every row
	if (grid_row.docfields === grid.docfields) {
		grid_row.docfields = grid.docfields.map((df) => ({ ...df }));
	}
	const df = grid_row.docfields.find((d) => d.fieldname === fieldname);
	if (df) {
		df.__base_read_only = df.__base_read_only ?? df.read_only ?? 0;
		df.read_only = locked ? 1 : df.__base_read_only;
	}

	// if the row is currently editable inline, refresh the live control too
	const field = grid_row.on_grid_fields_dict && grid_row.on_grid_fields_dict[fieldname];
	if (field) {
		field.df.__base_read_only = field.df.__base_read_only ?? field.df.read_only ?? 0;
		field.df.read_only = locked ? 1 : field.df.__base_read_only;
		field.refresh();
	}

	// if the row's expanded form dialog is open, refresh that field too
	const form_field = grid_row.grid_form?.fields_dict?.[fieldname];
	if (form_field) {
		form_field.df.__base_read_only =
			form_field.df.__base_read_only ?? form_field.df.read_only ?? 0;
		form_field.df.read_only = locked ? 1 : form_field.df.__base_read_only;
		form_field.refresh();
	}
}

function ensure_job_application_lock_patch(frm) {
	const grid = frm.fields_dict["job_application_count"].grid;
	if (grid.__row_lock_patched) return;
	grid.__row_lock_patched = true;

	const reapply = () => {
		if (frm.__mkt_job_app_is_superior !== undefined) {
			apply_job_application_row_locks(frm, frm.__mkt_job_app_is_superior);
		}
	};

	const original_refresh = grid.refresh.bind(grid);
	grid.refresh = function (...args) {
		original_refresh(...args);
		reapply();
	};

	if (typeof grid.make_head === "function") {
		const original_make_head = grid.make_head.bind(grid);
		grid.make_head = function (...args) {
			original_make_head(...args);
			reapply();
		};
	}
}

function render_tab_data(frm) {
	if (frm.is_new()) return;
	const active_tab = frm.active_tab_map && frm.active_tab_map[frm.doc.name];
	if (active_tab.df.fieldname === "history_tab") {
		load_customer_history_if_needed(frm);
	}
}

function load_customer_history_if_needed(frm) {
	if (!frm.doc.name) return;
	if (frm.__history_loaded_for === frm.doc.name) return; // already loaded for this doc

	frm.__history_loaded_for = frm.doc.name;

	if (frm.fields_dict.customer_details) {
		frm.fields_dict.customer_details.$wrapper.html(
			"<p style='color:#888'>Loading history...</p>",
		);
	}

	window.verp_staffing.render_customer_history_widget(frm, {
		fieldname: "customer_details",
		customer: frm.doc.customer,
		doctype: "Customer",
		department: "marketing",
	});
}

function handle_assign_to_permission(frm) {
	if (!frm.doc.assign_to) return;

	frappe.db.get_value("Employee", frm.doc.assign_to, "user").then((r) => {
		if (!r.message) return;

		const employee_user = r.message.user;

		if (frappe.session.user === employee_user) {
			frm.set_df_property("start_date", "read_only", 1);
			frm.set_df_property("target", "read_only", 1);
			frm.set_df_property("target_based_on", "read_only", 1);
			frm.refresh_field("start_date");
		} else {
			frm.set_df_property("start_date", "read_only", 0);
			frm.set_df_property("target", "read_only", 0);
			frm.set_df_property("target_based_on", "read_only", 0);
			frm.refresh_field("start_date");
		}
	});
}

frappe.ui.form.on("Job Application Count", {
	job_application_count_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.date) {
			row.date = frappe.datetime.get_today();
			frm.refresh_field("job_application_count");
		}
	},

	small_application(frm, cdt, cdn) {
		update_job_application_totals(frm, cdt, cdn);
	},

	large_application(frm, cdt, cdn) {
		update_job_application_totals(frm, cdt, cdn);
	},
});

function open_create_interview_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Create Interview"),
		fields: [
			{
				fieldname: "company",
				fieldtype: "Data",
				label: "Company",
				reqd: 1,
			},
			{
				fieldname: "role",
				fieldtype: "Data",
				label: "Role",
				reqd: 1,
			},
		],
		primary_action_label: __("Create Interview"),
		primary_action(values) {
			dialog.hide();
			create_interview(frm, values);
		},
	});

	dialog.show();
}

function create_interview(frm, values) {
	frappe.db.get_single_value("ERP Configuration", "default_interview_status").then((status) => {
		if (!status) {
			frappe.throw("Default Interview Status is not set in ERP Configuration");
		}

		const interview_doc = {
			doctype: "Interview",
			marketing_link: frm.doc.name,
			company: values.company,
			role: values.role,
			status: status, // dynamic now
		};

		frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: interview_doc,
			},
			callback(r) {
				if (r.message) {
					frappe.msgprint({
						title: __("Success"),
						message: __("Interview Created Successfully"),
						indicator: "green",
					});

					frappe.set_route("Form", "Interview", r.message.name);
				}
			},
			error(err) {
				frappe.msgprint({
					title: __("Error"),
					message: err?.exc || __("Failed to create Interview"),
					indicator: "red",
				});
			},
		});
	});
}

const MKT_INTERVIEW_VISIBLE_COUNT = 5;
const MKT_INTERVIEW_LIST_MAX_HEIGHT = 230; // px

function render_interview_list(frm) {
	if (!frm.doc.name) return;

	frappe.call({
		method: "verp_staffing.marketing.doctype.marketing.marketing.get_interviews_by_marketing",
		args: {
			marketing: frm.doc.name,
		},
		callback(r) {
			render_interview_list_html(frm, r.message || []);
		},
	});
}

function mkt_inject_interview_list_styles() {
	if (document.getElementById("mkt-interview-list-styles")) return;
	const style = document.createElement("style");
	style.id = "mkt-interview-list-styles";
	style.textContent = `
		.mkt-interview-list-wrap { width: 100%; }
		.mkt-interview-list {
			margin: 0;
			padding: 0;
			list-style: none;
		}
		.mkt-interview-list-wrap.mkt-expanded .mkt-interview-list {
			max-height: ${MKT_INTERVIEW_LIST_MAX_HEIGHT}px;
			overflow-y: auto;
			padding-right: 4px;
		}
		.mkt-interview-item {
			display: flex;
			align-items: center;
			gap: 8px;
			padding: 7px 8px;
			border-radius: 6px;
			font-size: 13px;
			color: #1c1c1c;
			text-decoration: none;
			transition: background .12s ease;
			min-width: 0;
		}
		.mkt-interview-item:hover {
			background: #F1F1F1;
			text-decoration: none;
			color: #1c1c1c;
		}
		.mkt-interview-item span:last-child {
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.mkt-interview-dot {
			width: 6px;
			height: 6px;
			border-radius: 50%;
			background: #2490EF;
			flex: none;
		}
		.mkt-interview-toggle-btn {
			margin-top: 4px;
			font-size: 12.5px;
			font-weight: 600;
			color: #2490EF;
			background: none;
			border: none;
			cursor: pointer;
			padding: 4px 8px;
		}
		.mkt-interview-toggle-btn:hover {
			text-decoration: underline;
		}
		.mkt-interview-empty {
			color: #8D99A6;
			font-size: 13px;
			padding: 6px 2px;
		}
	`;
	document.head.appendChild(style);
}

function render_interview_list_html(frm, data) {
	mkt_inject_interview_list_styles();

	const $wrapper = frm.fields_dict.interview_list.$wrapper;

	if (!data.length) {
		$wrapper.html("<div class='mkt-interview-empty'>No interviews linked</div>");
		return;
	}

	const has_more = data.length > MKT_INTERVIEW_VISIBLE_COUNT;
	const esc = frappe.utils.escape_html;

	function build_items(list) {
		return list
			.map(
				(d) => `
					<li>
						<a href="#" class="mkt-interview-item" data-interview="${esc(d.company || "")}">
							<span class="mkt-interview-dot"></span>
							<span>${esc(d.company || "")}</span>
						</a>
					</li>
				`,
			)
			.join("");
	}

	$wrapper.html(`
		<div class="mkt-interview-list-wrap">
			<ul class="mkt-interview-list">
				${build_items(has_more ? data.slice(0, MKT_INTERVIEW_VISIBLE_COUNT) : data)}
			</ul>
			${
				has_more
					? `<button type="button" class="mkt-interview-toggle-btn" data-expanded="0">
							Read more (${data.length - MKT_INTERVIEW_VISIBLE_COUNT} more)
						</button>`
					: ""
			}
		</div>
	`);

	const $wrap = $wrapper.find(".mkt-interview-list-wrap");
	const $list = $wrapper.find(".mkt-interview-list");
	const $toggle = $wrapper.find(".mkt-interview-toggle-btn");

	function bind_item_clicks() {
		$wrapper
			.find(".mkt-interview-item")
			.off("click")
			.on("click", function (e) {
				e.preventDefault();
				frappe.set_route("List", "Interview", "Kanban", { marketing_link: frm.doc.name });
			});
	}
	bind_item_clicks();

	if (!has_more) return;

	$toggle.on("click", function () {
		const expanded = $toggle.attr("data-expanded") === "1";

		if (!expanded) {
			$list.html(build_items(data));
			$wrap.addClass("mkt-expanded");
			$toggle.attr("data-expanded", "1").text("Show less");
		} else {
			$list.html(build_items(data.slice(0, MKT_INTERVIEW_VISIBLE_COUNT)));
			$wrap.removeClass("mkt-expanded");
			$toggle
				.attr("data-expanded", "0")
				.text(`Read more (${data.length - MKT_INTERVIEW_VISIBLE_COUNT} more)`);
		}

		bind_item_clicks();
	});
}

frappe.ui.form.on("Job Application Count", {
	job_application_count_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.date) {
			row.date = frappe.datetime.get_today();
			frm.refresh_field("job_application_count");
		}
	},

	small_application(frm, cdt, cdn) {
		update_job_application_totals(frm, cdt, cdn);
	},

	large_application(frm, cdt, cdn) {
		update_job_application_totals(frm, cdt, cdn);
	},
});

function update_job_application_totals(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	let small = flt(row.small_application);
	let large = flt(row.large_application);

	// Auto-calc only if at least one value exists
	if (small || large) {
		row.total_application = small + large;
		frm.refresh_field("job_application_count");
	}
}

function add_owner_grid_column(frm, fieldname, options = {}) {
	const { label = __("Created By") } = options;
	const grid = frm.fields_dict[fieldname].grid;

	if (!grid.__owner_column_patched) {
		grid.__owner_column_patched = true;

		const original_refresh = grid.refresh.bind(grid);
		grid.refresh = function (...args) {
			original_refresh(...args);
			inject_owner_column(grid, label);
		};

		if (typeof grid.make_head === "function") {
			const original_make_head = grid.make_head.bind(grid);
			grid.make_head = function (...args) {
				original_make_head(...args);
				inject_owner_column(grid, label);
			};
		}
	}
	grid.refresh();
}

function inject_owner_column(grid, label) {
	if (grid.header_row) {
		inject_owner_cell(grid.header_row, label, true);
	}
	(grid.grid_rows || []).forEach((grid_row) => inject_owner_cell(grid_row, label, false));
}

function inject_owner_cell(grid_row, label, is_header) {
	if (!grid_row.row) return;
	if (!is_header && !grid_row.doc) return; // skip search/filter row
	const $row = grid_row.row;

	const display = is_header ? label : resolve_owner_display(grid_row);
	let $col = $row.children(".owner-col");

	if ($col.length) {
		$col.find(".static-area").text(display);
		$col.attr("title", is_header ? display : grid_row.doc?.owner || "");
		return;
	}

	// find the anchor BEFORE creating the new column, and exclude .owner-col
	// so it can never match itself on a stale/duplicate pass
	const $last_data_col = $row.children("[data-fieldname]").not(".owner-col").last();

	$col = make_owner_col(display, is_header);
	if (!is_header) $col.attr("title", grid_row.doc?.owner || "");

	if ($last_data_col.length) {
		$col.insertAfter($last_data_col);
	} else {
		$row.append($col); // fallback: no real data columns found
	}
}

function make_owner_col(display, is_header) {
	// detached — NOT appended here, caller controls placement
	const $col = $(`
		<div class="col grid-static-col owner-col" data-fieldname="owner" data-fieldtype="Data">
			<div class="field-area" style="display:none;"></div>
			<div class="static-area ellipsis"></div>
		</div>
	`);
	$col.find(".static-area").text(display);
	if (is_header) $col.attr("title", display);
	return $col;
}

function resolve_owner_display(grid_row) {
	const owner = grid_row.doc.owner;
	const info = owner ? frappe.user_info(owner) : null;
	return info ? info.fullname : owner || "";
}
