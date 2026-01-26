frappe.provide("frappe.ui.misc");
frappe.ui.misc.about = function () {
	if (frappe.ui.misc.about_dialog) {
		frappe.ui.misc.about_dialog.show();
		return;
	}

	const dialog = new frappe.ui.Dialog({ title: __("About Vrugle") });

	$(dialog.body).html(
		`<div>
				<p>${__("Open Source Applications for the Web")}</p>

				<p>
					<i class='fa fa-globe fa-fw'></i>
					${__("Website")}:
					<a href='https://vrugle.com/' target='_blank'>https://vrugle.com/</a>
				</p>

				<p>
					<i class='fa fa-file-text fa-fw'></i>
					${__("Vrugle Blog")}:
					<a href='https://vrugle.com/blog' target='_blank'>https://vrugle.com/blog</a>
				</p>

				<p>
					<i class='fa fa-linkedin fa-fw'></i>
					${__("LinkedIn")}:
					<a href='https://www.linkedin.com/company/vrugle' target='_blank'>https://www.linkedin.com/company/vrugle</a>
				</p>

				<p>
					<i class='fa fa-instagram fa-fw'></i>
					${__("Instagram")}:
					<a href='https://www.instagram.com/vrugle/' target='_blank'>https://www.instagram.com/vrugle/</a>
				</p>

				<hr>

				<div class="d-flex align-items-center justify-content-between">
					<h4>${__("Installed Apps")}</h4>
					<button class="btn action-btn hidden" id="copy-apps-info"
					title="${__("Copy Apps Version")}"
					style="margin-bottom: var(--margin-md);">
						${frappe.utils.icon("clipboard")}
					</button>
				</div>

				<div id='about-app-versions'>${__("Loading versions...")}</div>

			</div>`
	);

	frappe.ui.misc.about_dialog = dialog;

	frappe.ui.misc.about_dialog.on_page_show = function () {
		if (!frappe.versions) {
			frappe.call({
				method: "frappe.utils.change_log.get_versions",
				callback: function (r) {
					show_versions(r.message);
				},
			});
		} else {
			show_versions(frappe.versions);
		}
	};

	const show_versions = function (versions) {
		const $wrap = $("#about-app-versions").empty();
		let app = {};

		function get_version_text(app) {
			if (app.branch) {
				return `v${app.branch_version || app.version} (${app.branch})`;
			} else {
				return `v${app.version}`;
			}
		}

		for (const app_name in versions) {
			app = versions[app_name];
			const title = `${app_name}: ${app.branch_version || app.version}`;
			const text = `<p class='app-version' role='button' title='${title}'>
							<b>${app.title}:</b> ${get_version_text(app)}
						</p>`;
			$(text).appendTo($wrap);
		}

		frappe.versions = versions;

		if (frappe.versions) {
			$(dialog.body).find("#copy-apps-info").removeClass("hidden");
		}
	};

	const code_block = (snippet, lang = "") => "```" + lang + "\n" + snippet + "\n```";

	// Listener for copying installed apps info
	$(dialog.body).on("click", "#copy-apps-info", function () {
		if (!frappe.versions) return;

		const versions = Object.entries(frappe.versions).reduce((acc, [key, app]) => {
			acc[key] = app.branch_version || app.version;
			return acc;
		}, {});

		frappe.utils.copy_to_clipboard(code_block(JSON.stringify(versions, null, "\t"), "json"));
	});

	// Listener for copy app version
	$(dialog.body).on("click", ".app-version", function () {
		const title = $(this).attr("title");
		if (title) {
			frappe.utils.copy_to_clipboard(title);
		}
	});

	frappe.ui.misc.about_dialog.show();
};
