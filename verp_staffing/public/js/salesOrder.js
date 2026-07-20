window.AgreementFieldManager = class AgreementFieldManager {
	constructor() {
		this.controls = new Map();
	}

	makeKey(field) {
		return `${field.type}::${field.name}`;
	}

	register(field, control) {
		this.controls.set(this.makeKey(field), {
			field,
			control,
		});
	}

	unregister(field) {
		this.controls.delete(this.makeKey(field));
	}

	clear() {
		this.controls.clear();
	}

	getControl(field) {
		return this.controls.get(this.makeKey(field));
	}

	getValues() {
		const data = {};

		for (const [key, item] of this.controls.entries()) {
			const { field, control } = item;

			let value = null;

			switch (field.type) {
				case "Rich_Text":
					value = control.get_input_value();
					break;

				default:
					value = control.val()?.trim() ?? "";
					break;
			}

			data[key] = value;
		}
		return data;
	}
};

const agreementFieldManager = new AgreementFieldManager();

window.render_agreement_module = function ({
	frm,
	wrapper,
	sales_order,
	allow_create = true,
	auto_mode = false,
}) {
	wrapper.empty();

	wrapper.append(`
    <div id="agreement_module" style="padding: 16px;">

      <!-- AGREEMENT LIST -->
      <div id="agreement_list_section" class="mb-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h5 class="mb-0" style="font-weight:600; color: var(--heading-color);">
            📄 Agreements
          </h5>
          <button id="ag_refresh_btn" class="btn btn-xs btn-default">
            <svg class="icon icon-xs"><use href="#icon-refresh"/></svg>
            Refresh
          </button>
        </div>
        <div id="agreement_cards"></div>
      </div>

      ${
			allow_create
				? `
      <hr class="my-4"/>

      <!-- BUILDER SECTION -->
      <div id="agreement_builder_section">
        <h5 class="mb-3" style="font-weight:600; color: var(--heading-color);">
          ➕ Create Agreement
        </h5>

        <div class="frappe-card" style="
          background: var(--card-bg);
          border: 1px solid var(--border-color);
          border-radius: var(--border-radius-lg);
          padding: 20px;
        ">
          <!-- Template Select -->
          <div class="form-group">
            <label class="control-label" style="font-size: 12px; font-weight: 600; color: var(--text-muted);">
              TEMPLATE <span class="text-danger">*</span>
            </label>
            <select id="ag_template" class="form-control" style="
              max-width: 400px;
              border: 1px solid var(--border-color);
              border-radius: var(--border-radius);
              background: var(--control-bg);
              color: var(--text-color);
              padding: 6px 10px;
              height: 34px;
              font-size: 13px;
            ">
              <option value="">Select Template...</option>
            </select>
          </div>

          <!-- Dynamic Fields -->
          <div id="ag_dynamic_form" class="mt-3"></div>

          <!-- Action Buttons -->
          <div class="mt-4 d-flex gap-2 flex-wrap" style="gap: 8px;">
           <button id="ag_preview" class="btn btn-default btn-sm" style="text-center>
              <svg class="icon icon-xs mr-1"><use href="#icon-eye"/></svg>
              Preview
            </button>
            <button id="ag_save" class="btn btn-primary btn-sm" style="text-center>
              <svg class="icon icon-xs mr-1"><use href="#icon-save"/></svg>
              Save${auto_mode ? " As Draft" : ""}
            </button>
            <button id="ag_save_send" class="btn btn-sm" style="
			  display: ${auto_mode ? "none" : "inline-block"};
              background: var(--gray-900);
              color: white;
              border: none;
			  text-center
            >
              <svg class="icon icon-xs mr-1"><use href="#icon-send"/></svg>
              Save &amp; Send
            </button>
          </div>
        </div>
      </div>
      `
				: ""
		}

    </div>
  `);

	fetch_and_render_agreements(wrapper, sales_order);

	if (allow_create) {
		load_templates(wrapper);
		bind_builder_events(frm, wrapper, sales_order, auto_mode);
	}
};

function fetch_and_render_agreements(wrapper, sales_order) {
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Agreement",
			filters: { sales_order },
			fields: ["name", "template", "status", "pdf", "creation"],
			order_by: "creation desc",
		},
		callback(r) {
			render_agreement_cards(wrapper, r.message || [], sales_order);
		},
	});
}

function render_agreement_cards(wrapper, agreements, sales_order) {
	const container = wrapper.find("#agreement_cards");
	container.empty();

	if (!agreements.length) {
		container.append(`
      <div style="
        padding: 24px 16px;
        text-align: center;
        background: var(--subtle-fg);
        border: 1px dashed var(--border-color);
        border-radius: var(--border-radius-lg);
        color: var(--text-muted);
        font-size: 13px;
      ">
        <svg class="icon icon-lg mb-2" style="opacity:0.3;"><use href="#icon-list"/></svg>
        <div>No agreements created yet</div>
      </div>
    `);
		return;
	}

	agreements.forEach((ag) => {
		const status_color =
			ag.status === "Ready To Send"
				? "blue"
				: ag.status === "Sent"
					? "green"
					: ag.status === "Draft"
						? "orange"
						: "gray";

		container.append(`
      <div class="agreement-card" style="
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius-lg);
        padding: 14px 16px;
        margin-bottom: 10px;
        transition: box-shadow 0.15s ease;
      "
      onmouseenter="this.style.boxShadow='var(--shadow-sm)'"
      onmouseleave="this.style.boxShadow='none'"
      >
        <div class="d-flex justify-content-between align-items-start">
          <div style="flex:1; min-width:0;">
            <div style="font-weight:600; font-size:13px; margin-bottom:2px;">
  <a href="/app/agreement/${ag.name}"
     style="color:#260fea; text-decoration:none;"
     onmouseenter="this.style.color='#1d0ed6'"
     onmouseleave="this.style.color='#260fea'"
  >
    ${ag.name}
  </a>
</div>
            <div style="font-size:12px; color: var(--text-muted); margin-bottom:2px;">
              Template: <span style="color: var(--text-color);">${ag.template || "—"}</span>
            </div>
            <div style="font-size:11px; color: var(--text-muted);">
              ${frappe.datetime.str_to_user(ag.creation)}
            </div>
          </div>

          <span class="indicator-pill ${status_color}" style="flex-shrink:0; margin-left:12px; font-size:11px;">
            ${ag.status || "Draft"}
          </span>
        </div>

        <div class="mt-2 d-flex flex-wrap" style="gap:6px; margin-top:10px !important;">
          <a href="/app/agreement/${ag.name}" class="btn btn-xs btn-default">
            View
          </a>
          ${
				ag.pdf
					? `
            <button class="btn btn-xs btn-default open-pdf" data-url="${ag.pdf}">
              View PDF
            </button>
          `
					: ""
			}
          ${
				ag.status === "Ready To Send"
					? `
            <button class="btn btn-xs  btn-primary send-agreement" data-name="${ag.name}">
              Send
            </button>
          `
					: ""
			}
        </div>
      </div>
    `);
	});

	// Events
	container.off("click", ".open-pdf");
	container.on("click", ".open-pdf", function () {
		window.open($(this).data("url"));
	});

	container.off("click", ".send-agreement");
	container.on("click", ".send-agreement", function () {
		const $btn = $(this);
		const name = $btn.data("name");

		setButtonState($btn, "loading", "Sending...");

		frappe.call({
			method: "verp_staffing.crm.api.agreement.send_existing_agreement",
			args: { agreement: name },

			callback(r) {
				if (r.message && r.message.success) {
					frappe.msgprint("Agreement sent");
					setButtonState($btn, "reset");
					fetch_and_render_agreements(wrapper, sales_order);
				} else {
					frappe.msgprint("Failed to send agreement");
					setButtonState($btn, "reset");
				}
			},

			error() {
				frappe.msgprint("Server error while sending");
				setButtonState($btn, "reset");
			},
		});
	});
}

function load_templates(wrapper) {
	const select = wrapper.find("#ag_template");

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Pdf Agreement Template",
			filters: { is_active: 1 },
			fields: ["name", "title"],
		},
		callback(r) {
			select.empty().append(`<option value="">Select Template</option>`);

			(r.message || []).forEach((t) => {
				select.append(`<option value="${t.name}">${t.title}</option>`);
			});
		},
	});
}

// function bind_builder_events(frm, wrapper, sales_order) {
// 	wrapper.on("change", "#ag_template", () => load_form_fields(wrapper));

// 	wrapper.on("click", "#ag_preview", function () {
// 		const $btn = $(this);

// 		setButtonState($btn, "loading", "Generating Preview...");

// 		preview(frm, wrapper).finally(() => {
// 			setButtonState($btn, "reset");
// 		});
// 	});
// 	wrapper.on("click", "#ag_save", () => submit(frm, wrapper, sales_order, false));

// 	wrapper.on("click", "#ag_save_send", () => submit(frm, wrapper, sales_order, true));
// }

function bind_builder_events(frm, wrapper, sales_order, auto_mode) {
	// remove old bindings first (IMPORTANT)
	wrapper.off("change", "#ag_template");
	wrapper.off("click", "#ag_preview");
	wrapper.off("click", "#ag_save");
	wrapper.off("click", "#ag_save_send");

	// bind again (single time)
	wrapper.on("change", "#ag_template", () => load_form_fields(wrapper));

	wrapper.on("click", "#ag_preview", function () {
		const $btn = $(this);

		setButtonState($btn, "loading", "Generating Preview...");

		preview(frm, wrapper).finally(() => {
			setButtonState($btn, "reset");
		});
	});

	wrapper.on("click", "#ag_save", () => {
		if (auto_mode) {
			store_draft_locally(frm, wrapper);
			frappe.show_alert({
				message: "Agreement saved for auto processing, now can save sales order",
				indicator: "green",
			});
			return;
		}

		submit(frm, wrapper, sales_order, false);
	});

	wrapper.on("click", "#ag_save_send", () => submit(frm, wrapper, sales_order, true));
}

function store_draft_locally(frm, wrapper) {
	const template = wrapper.find("#ag_template").val();

	if (!template) {
		frappe.throw("Please select a template");
	}

	const data = collect_agreement_data(frm, wrapper);

	const key = `so_agreement_draft_${frm.doc.name || "new"}`;
	localStorage.setItem(
		key,
		JSON.stringify({
			template,
			data,
		}),
	);
}

function submit(frm, wrapper, sales_order, send_email) {
	const template = wrapper.find("#ag_template").val();

	if (!template) {
		frappe.show_alert({ message: "Please select a template", indicator: "orange" });
		return;
	}

	const $btn = send_email ? wrapper.find("#ag_save_send") : wrapper.find("#ag_save");

	setButtonState($btn, "loading", send_email ? "Saving & Sending..." : "Saving...");

	const data = collect_agreement_data(frm, wrapper);

	frappe.call({
		method: "verp_staffing.crm.api.agreement.submit_and_generate",
		args: {
			sales_order,
			template,
			data: JSON.stringify(data),
			send_email: send_email ? 1 : 0,
		},
		callback() {
			frappe.msgprint("Agreement created");
			setButtonState($btn, "reset");
			wrapper.find("#ag_dynamic_form").hide();

			// optional: also reset template
			wrapper.find("#ag_template").val("");
			fetch_and_render_agreements(wrapper, sales_order);
		},
		error() {
			frappe.msgprint("Failed to save agreement");
			setButtonState($btn, "reset");
		},
	});
}

function collect_agreement_data() {
	return agreementFieldManager.getValues();
}

function load_form_fields(wrapper) {
	const template = wrapper.find("#ag_template").val();
	const form_div = wrapper.find("#ag_dynamic_form");

	if (!template) {
		form_div.empty();
		return;
	}

	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Pdf Agreement Template", name: template },
		callback(r) {
			const tpl = r.message;
			const blocks = JSON.parse(tpl.fields_json || "[]");
			agreementFieldManager.clear();
			form_div.empty();

			if (!blocks.length) return;

			form_div.append(`
				<div style="
				border-top: 1px solid var(--border-color);
				padding-top: 16px;
				margin-top: 4px;
				">
				<div style="font-size:11px; font-weight:600; color:var(--text-muted); margin-bottom:12px; letter-spacing:0.5px;">
					TEMPLATE FIELDS
				</div>
				</div>
			`);

			const groupedBlocks = [];
			const seen = new Set();

			blocks.forEach((b) => {
				if (!b.name || !b.type) return;

				const key = `${b.type.trim().toLowerCase()}|${b.name.trim().toLowerCase()}`;

				if (seen.has(key)) return;

				seen.add(key);
				groupedBlocks.push(b);
			});

			groupedBlocks.forEach((b) => {
				if (["Number", "Date"].includes(b.type)) {
					form_div.append(`
						<div class="form-group" style="margin-bottom:14px; max-width:400px;">
							<label class="control-label" style="
								font-size:12px;
								font-weight:600;
								color: var(--text-muted);
								text-transform: uppercase;
								letter-spacing: 0.4px;
							">
								${b.label || b.name}
							</label>
							<input
								type="${b.type === "Number" ? "number" : b.type === "Date" ? "date" : "text"}"
								class="form-control ag-field"
								data-field="${b.name}"
								placeholder="Enter ${b.label || b.name}..."
								style="
									border: 1px solid var(--border-color);
									border-radius: var(--border-radius);
									background: var(--control-bg);
									color: var(--text-color);
									padding: 6px 10px;
									font-size: 13px;
									height: 34px;
								"
							/>
						</div>
					`);
					agreementFieldManager.register(b, form_div.find(".ag-field").last());
				} else if (b.type == "Text") {
					form_div.append(`
						<div class="form-group" style="margin-bottom:14px; max-width:1000px;">
							<label class="control-label" style="
								font-size:12px;
								font-weight:600;
								color: var(--text-muted);
								text-transform: uppercase;
								letter-spacing: 0.4px;
							">
								${b.label || b.name}
							</label>
							<input
								type="${b.type === "Number" ? "number" : b.type === "Date" ? "date" : "text"}"
								class="form-control ag-field"
								data-field="${b.name}"
								placeholder="Enter ${b.label || b.name}..."
								style="
									border: 1px solid var(--border-color);
									border-radius: var(--border-radius);
									background: var(--control-bg);
									color: var(--text-color);
									padding: 6px 10px;
									font-size: 13px;
									height: 34px;
								"
							/>
						</div>
					`);
					agreementFieldManager.register(b, form_div.find(".ag-field").last());
				} else if (b.type === "Rich_Text") {
					const editor_wrapper = $(`
											<div class="form-group" style="margin-bottom:14px;">
												<label class="control-label" style="
													font-size:12px;
													font-weight:600;
													color: var(--text-muted);
													text-transform: uppercase;
													letter-spacing:0.4px;
												">
													${b.label || b.name}
												</label>

												<div id="editor-${frappe.scrub(b.name)}"></div>
											</div>
										`);

					form_div.append(editor_wrapper);

					const field = frappe.ui.form.make_control({
						parent: editor_wrapper.find(`#editor-${frappe.scrub(b.name)}`),
						df: {
							fieldtype: "Text Editor",
							fieldname: b.name,
						},
						render_input: true,
					});

					field.refresh();
					agreementFieldManager.register(b, field);
				}
			});
		},
	});
}

function preview(frm, wrapper) {
	return new Promise((resolve, reject) => {
		const template = wrapper.find("#ag_template").val();

		if (!template) {
			frappe.show_alert({
				message: "Choose a template first",
				indicator: "orange",
			});
			reject();
			return;
		}

		const data = collect_agreement_data();

		const form = document.createElement("form");
		form.method = "POST";
		form.action = "/api/method/verp_staffing.crm.api.agreement.preview_agreement";
		form.target = "_blank";
		form.style.display = "none";

		const fields = {
			template,
			data: JSON.stringify(data),
			csrf_token: frappe.csrf_token,
		};

		Object.entries(fields).forEach(([name, value]) => {
			const input = document.createElement("input");
			input.type = "hidden";
			input.name = name;
			input.value = value;
			form.appendChild(input);
		});

		document.body.appendChild(form);
		form.submit();
		document.body.removeChild(form);

		resolve();
	});
}

function setButtonState($btn, state, text) {
	if (state === "loading") {
		$btn.data("original-text", $btn.html());
		$btn.prop("disabled", true).css("opacity", "0.65");
		$btn.html(`
      <span class="spinner-border spinner-border-sm mr-1"
            style="width:11px;height:11px;border-width:2px;"
            role="status"></span>
      ${text}
    `);
	} else {
		$btn.prop("disabled", false).css("opacity", "1");
		$btn.html($btn.data("original-text"));
	}
}
