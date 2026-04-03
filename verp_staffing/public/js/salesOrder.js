const BRAND_COLOR = "#3b82f6";

window.render_agreement_module = function ({ frm, wrapper, sales_order, allow_create = true }) {
	wrapper.empty();

	wrapper.append(`
		<div id="agreement_module">

			<div id="agreement_list_section">
				<h3>📄 Agreements</h3>
				<div id="agreement_cards"></div>
			</div>

			${
				allow_create
					? `
			<hr/>
			<div id="agreement_builder_section">
	<h3 style="color:${BRAND_COLOR}">➕ Create Agreement</h3>

	<select id="ag_template" class="form-control" style="
		border:1px solid ${BRAND_COLOR};
		border-radius:6px;
	"></select>

	<div id="ag_dynamic_form" style="margin-top: 15px;"></div>

	<button id="ag_preview" style="
		margin-top:10px;
		background:white;
		color:${BRAND_COLOR};
		border:1px solid ${BRAND_COLOR};
		padding:6px 12px;
		border-radius:6px;
	">
		Preview
	</button>

	<button id="ag_save" style="
		margin-top:10px;
		background:${BRAND_COLOR};
		color:white;
		border:none;
		padding:6px 12px;
		border-radius:6px;
	">
		Save
	</button>

	<button id="ag_save_send" style="
		margin-top:10px;
		background: black;
		color:white;
		border:none;
		padding:6px 12px;
		border-radius:6px;
	">
		Save & Send
	</button>
</div>
			`
					: ""
			}

		</div>
	`);

	fetch_and_render_agreements(wrapper, sales_order);

	if (allow_create) {
		load_templates(wrapper);
		bind_builder_events(frm, wrapper, sales_order);
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
			render_agreement_cards(wrapper, r.message || []);
		},
	});
}

function render_agreement_cards(wrapper, agreements) {
	const container = wrapper.find("#agreement_cards");
	container.empty();

	if (!agreements.length) {
		container.append(`<p style="color:#888">No agreements created yet</p>`);
		return;
	}

	agreements.forEach((ag) => {
		container.append(`
			<div class="agreement-card" style="
				border:1px solid #e5e7eb;
				padding:16px;
				border-radius:12px;
				margin-bottom:12px;
				background:#fff;
				box-shadow:0 2px 8px rgba(0,0,0,0.04);
			">

				<div style="display:flex; justify-content:space-between; align-items:center;">
					<div>
						<b style="color:${BRAND_COLOR}">${ag.name || "Agreement"}</b><br/>
                        <b style="">Template: ${ag.template || "Agreement"}</b><br/>
						<small style="color:#666">${ag.creation}</small>
					</div>
					<div>
						<span style="
							background:${BRAND_COLOR}15;
							color:${BRAND_COLOR};
							padding:4px 10px;
							border-radius:20px;
							font-size:12px;
							font-weight:600;
						">
							${ag.status || "Draft"}
						</span>
					</div>
				</div>

				<div style="margin-top:14px; display:flex; gap:10px; flex-wrap:wrap;">

					<a class="btn-primary" href="/app/agreement/${ag.name}" style="
						border-radius:6px;
                        padding: 2px 5px;
                        background-color: transparent;
						border:1px solid ${BRAND_COLOR};
						color:${BRAND_COLOR};
						text-decoration:none;
						font-weight:500;
					">
						View
					</a>

					${
						ag.pdf
							? `
						<button class="open-pdf btn-primary" data-url="${ag.pdf}" style="
							border-radius:6px;
							background:${BRAND_COLOR};
							color:white;
							border:none;
						">
							View PDF
						</button>
					`
							: ""
					}

					${
						ag.status === "Ready To Send"
							? `
						<button class="send-agreement btn-primary" data-name="${ag.name}" style="
							border-radius:6px;
							background: black;
							color:white;
							border:none;
						">
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

function bind_builder_events(frm, wrapper, sales_order) {
	wrapper.on("change", "#ag_template", () => load_form_fields(wrapper));

	wrapper.on("click", "#ag_preview", function () {
		const $btn = $(this);

		setButtonState($btn, "loading", "Generating Preview...");

		preview(frm, wrapper).finally(() => {
			setButtonState($btn, "reset");
		});
	});
	wrapper.on("click", "#ag_save", () => submit(frm, wrapper, sales_order, false));

	wrapper.on("click", "#ag_save_send", () => submit(frm, wrapper, sales_order, true));
}

function submit(frm, wrapper, sales_order, send_email) {
	const template = wrapper.find("#ag_template").val();

	if (!template) {
		frappe.msgprint("Select template");
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
			fetch_and_render_agreements(wrapper, sales_order);
		},
		error() {
			frappe.msgprint("Failed to save agreement");
			setButtonState($btn, "reset");
		},
	});
}

function collect_agreement_data(frm, wrapper) {
	const data = {};

	wrapper.find(".ag-field").each(function () {
		const key = $(this).data("field");
		let val = $(this).val();
		if (key === "Payment_Terms" && !val.length) {
			frappe.msgprint("Please enter valid payment terms");
			return;
		}
		// normalize Payment Terms
		if (key === "Payment_Terms") {
			val = val
				.split(",")
				.map((v) => v.trim())
				.filter((v) => v);
		}

		data[key] = val;
	});
	return data;
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
			form_div.empty();

			blocks.forEach((b) => {
				if (["Text", "Number", "Date"].includes(b.type)) {
					form_div.append(`
                        <div style="margin-bottom: 10px;">
                            <label>${b.label || b.name}</label>
                            <input type="${b.type ?? "text"}" 
                            style="
                            border:1px solid #ddd;
                            border-radius:6px;
                            padding:6px;
                            max-width: 400px
                            " 
                            class="form-control ag-field"
                            data-field="${b.name}">
                        </div>
                    `);
				} else if (b.type === "Payment_Terms") {
					form_div.append(`
                        <div style="margin-bottom: 10px;">
                            <label>${b.label || b.name}</label>
                            <textarea 
                                class="form-control ag-field"
                                data-field="${b.name}"
                                placeholder="Enter comma separated terms"
                                style="
                                    border:1px solid #ddd;
                                    border-radius:6px;
                                    padding:6px;
                                    max-width:400px;
                                    min-height:80px;
                                "
                            ></textarea>
                        </div>
                    `);
				}
			});
		},
	});
}

function preview(frm, wrapper) {
	return new Promise((resolve, reject) => {
		const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
		if (!template) {
			frappe.msgprint("Choose a template first");
			reject();
			return;
		}

		const data = collect_agreement_data(frm, wrapper);

		frappe.call({
			method: "verp_staffing.crm.api.agreement.preview_agreement",
			args: { template, data: JSON.stringify(data) },

			callback(r) {
				if (!r.message) {
					frappe.msgprint("Preview error");
					reject();
					return;
				}
				window.open(r.message.file_url);
				resolve();
			},

			error() {
				frappe.msgprint("Preview failed");
				reject();
			},
		});
	});
}

function collect_so_agreement_data(frm, wrapper) {
	const data = {};
	wrapper.find(".ag-field").each(function () {
		const key = $(this).data("field");
		data[key] = $(this).val();
	});

	// Include payment_terms
	data["Payment_Terms"] = (frm.doc.payment_terms || []).map((r) => ({
		date: r.date,
		amount: r.amount,
		is_received: r.is_received,
	}));

	return data;
}

function setButtonState($btn, state, originalText) {
	if (state === "loading") {
		$btn.data("original-text", $btn.text());
		$btn.prop("disabled", true);
		$btn.css("opacity", "0.6");
		$btn.text(originalText);
	} else {
		$btn.prop("disabled", false);
		$btn.css("opacity", "1");
		$btn.text($btn.data("original-text"));
	}
}
