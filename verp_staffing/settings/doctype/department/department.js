// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Department", {
	async refresh(frm) {
		set_service_query(frm);

		if (!frm.doc.name) return;

		// Show redirect buttopn in headline
		if(frappe.session.user === "Administrator"){
			await render_headline(frm);
		}
	},
	onload(frm) {
		set_service_query(frm);
		set_role_query(frm);
	},
});

async function render_headline(frm) {
	if (frm.is_new()) return;

	const r = await frappe.db.get_value("Hierarchy", { department: frm.doc.name }, "name");

	if (r.message?.name) {
		const hierarchy = r.message.name;

		frm.dashboard.set_headline_alert(
			__(
				`Department setup is complete. Hierarchy is already been defined.
				<a href="#" class="btn btn-xs btn-primary setup-hierarchy-action" style="margin-left:8px;">
					Open Hierarchy →
				</a>`,
			),
			"blue",
		);

		frm.page.wrapper
			.find(".setup-hierarchy-action")
			.off("click")
			.on("click", function (e) {
				e.preventDefault();
				frappe.set_route("Form", "Hierarchy", hierarchy);
			});
	} else {
		frm.dashboard.set_headline_alert(
			__(
				`Department setup is complete. The next step is defining Hierarchy of this department.
				<a href="#" class="btn btn-xs btn-primary setup-hierarchy-action" style="margin-left:8px;">
					Create Hierarchy →
				</a>`,
			),
			"orange",
		);

		frm.page.wrapper
			.find(".setup-hierarchy-action")
			.off("click")
			.on("click", function (e) {
				e.preventDefault();

				frappe.route_options = {
					department: frm.doc.name,
				};

				frappe.new_doc("Hierarchy");
			});
	}
}

function set_service_query(frm) {
	frm.set_query("services", function () {
		return {
			query: "verp_staffing.settings.doctype.department.department.get_department_service_query",
			filters: {
				department: frm.doc.name,
			},
		};
	});
}

function set_role_query(frm) {
	frm.set_query("role", function () {
		return {
			query: "verp_staffing.settings.doctype.department.department.get_department_role_query",
			filters: {
				department: frm.doc.name,
			},
		};
	});
}
