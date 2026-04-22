// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt
let activeBox = null;
let actionType = null;
let offsetX = 0;
let offsetY = 0;
let activeOverlay = null;
let recipients = [];
let activeRecipient = null;
let recipientColors = {};
let selectedFieldType = "signature";

const colorPalette = [
	"#2563eb", // Royal Blue
	"#16a34a", // Forest Green
	"#f59e0b", // Amber Orange
	"#ef4444", // Bright Red
	"#8b5cf6", // Deep Purple
	"#06b6d4", // Cyan
	"#ec4899", // Pink
	"#84cc16", // Lime

	// New distinct additions
	"#4338ca", // Indigo (Deeper than Blue)
	"#115e59", // Teal (Between Green and Blue)
	"#9a3412", // Burnt Sienna (Darker/Earthier than Orange)
	"#facc15", // Bright Yellow (Distinct from Amber)
	"#57534e", // Stone Grey (Neutral)
	"#9d174d", // Maroon/Rose (Deeper than Red)
	"#78350f", // Dark Brown
	"#d946ef", // Fuchsia/Magenta (Vibrant Purple-Pink)
];
frappe.ui.form.on("E Sign", {
	refresh(frm) {
		if (!frm.doc.original_pdf) return;

		rebuild_recipients(frm);

		if (!frm._pdf_loaded) {
			frm._pdf_loaded = true;
			load_pdf_pages(frm).then(() => {
				render_existing_boxes(frm); // only AFTER pages are ready
			});
		}

		// PRODUCTION SEND BUTTON
		frm.clear_custom_buttons();

		if (frm.doc.status === "Draft") {
			frm.add_custom_button("Send For Signature", () => {
				frappe.confirm(
					"Send document to all recipients and lock editing?",

					function () {
						// YES
						send_for_signature(frm);
					},

					function () {
						// NO
					},
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Sent" || frm.doc.status === "Fully Signed") {
			setTimeout(lock_editor, 500);
		}
	},
});

function rebuild_recipients(frm) {
	recipients = [];
	recipientColors = {};

	if (!frm.doc.signature_fields) return;

	const unique = [
		...new Set(frm.doc.signature_fields.map((r) => r.signer_email).filter(Boolean)),
	];

	unique.forEach((email, index) => {
		recipients.push(email);

		const color = colorPalette[index % colorPalette.length];

		recipientColors[email] = color;
	});

	if (!activeRecipient && recipients.length) {
		activeRecipient = recipients[0];
	}
}

async function load_pdf_pages(frm) {
	const field = frm.fields_dict.original_pdf.$wrapper;

	// hide original attach field UI
	field.find(".control-input-wrapper").hide();

	// create full width container after it
	if (!document.getElementById("esign-root")) {
		field.after(`
      <div id="esign-root" style="width:100%; margin-top:20px;"></div>
  `);
	}

	const wrapper = $("#esign-root");
	wrapper.html(`
<div class="esign-layout">

  <div class="esign-toolbar">

      <div class="recipient-section">

          <div class="toolbar-title">ADD RECIPIENTS</div>

          <input type="email"
                 id="recipient-input"
                 placeholder="Enter email..."
                 class="form-control"/>

          <button class="btn btn-xs btn-primary"
                  id="add-recipient-btn"
                  style="margin-top:6px;width:100%;">
                  Add Recipient
          </button>

          <div id="recipient-list" style="margin-top:10px;"></div>

      </div>

      <hr/>

      <div class="toolbar-title">ADD FIELDS</div>
      
        <div class="toolbar-subtext">
          Drag and drop fields anywhere in the document.
        </div>

      ${field_button("signature", "E-signature", "edit")}
      ${field_button("text", "Text", "type")}
      ${field_button("name", "Recipient name", "user")}
      ${field_button("date", "Date", "calendar")}
      ${field_button("number", "Number", "hash")}
      ${field_button("checkbox", "Checkbox", "check")}

  </div>

  <div id="pdf-container" class="esign-pdf-container"></div>

</div>
`);

	enable_toolbar_drag();
	render_recipient_list();

	const response = await frappe.call({
		method: "verp_staffing.esign.doctype.e_sign.e_sign.generate_pdf_pages",
		args: { docname: frm.doc.name },
	});

	if (!response.message) {
		console.error("PDF API failed", response);
		frappe.msgprint("Failed to load PDF pages");
		return;
	}

	const pages = response.message;

	const container = document.getElementById("pdf-container");

	pages.forEach((page) => {
		const pageWrapper = document.createElement("div");
		pageWrapper.style.position = "relative";
		pageWrapper.style.marginBottom = "24px";
		pageWrapper.style.width = "100%";
		pageWrapper.style.maxWidth = "1200px";
		pageWrapper.dataset.page = page.page_number;

		const img = document.createElement("img");
		img.src = page.url;
		img.style.width = "100%";
		img.style.maxWidth = "1200px";
		img.style.borderRadius = "6px";
		img.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
		img.style.display = "block";

		const overlay = document.createElement("div");
		overlay.className = "page-overlay";
		overlay.dataset.page = page.page_number;
		overlay.style.position = "absolute";
		overlay.style.inset = "0";

		pageWrapper.appendChild(img);
		pageWrapper.appendChild(overlay);
		container.appendChild(pageWrapper);

		enable_drop(frm, overlay);
	});
	render_existing_boxes(frm);
}

frappe.dom.set_style(`
.esign-layout{
    display:flex;
    gap:16px;
    height:85vh;
    width:100%;
}
.esign-toolbar{
    width:240px;
    min-width:240px;
    background:var(--card-bg);
    border:1px solid var(--border-color);
    border-radius:8px;
    padding:12px;
    overflow:auto;
}

.toolbar-title{
    font-weight:600;
    margin-bottom:10px;
    font-size:13px;
    color:var(--text-muted);
}

.toolbar-subtext {
	font-size: 11px;
	color: #6b7280;
	margin-top: 4px;
	line-height: 1.4;
	font-weight: 400;
	letter-spacing: 0.2px;
	padding-bottom: 15px;
}

.esign-field-tool{
    display:flex;
    align-items:center;
    gap:8px;
    padding:8px 10px;
    border:1px solid var(--border-color);
    border-radius:6px;
    margin-bottom:6px;
    cursor:pointer;
    font-size:13px;
    background:var(--control-bg);
}

.esign-field-tool:hover{
    background:var(--gray-100);
}

.esign-field-tool.active{
    border-color:var(--primary);
    background:var(--primary-light);
}

.field-icon{
    width:16px;
    text-align:center;
}

.esign-pdf-container{
    flex-grow:1;
    width:100%;
    overflow:auto;
    padding:24px;
    background:var(--gray-50);
    border-radius:8px;
    display:flex;
    flex-direction:column;
    align-items:flex-start;
}`);

setTimeout(() => {
	const fieldWrapper = cur_frm.fields_dict.original_pdf.$wrapper;

	fieldWrapper.closest(".frappe-control").style.maxWidth = "100%";
	fieldWrapper.closest(".form-column").style.maxWidth = "100%";
	fieldWrapper.closest(".form-column").style.flex = "1";
}, 200);

function enable_toolbar_drag() {
	document.querySelectorAll(".esign-field-tool").forEach((tool) => {
		tool.addEventListener("dragstart", function (e) {
			e.dataTransfer.setData("field_type", this.dataset.type);
		});
	});

	document.querySelectorAll(".esign-field-tool").forEach((btn) => {
		btn.addEventListener("click", function () {
			document
				.querySelectorAll(".esign-field-tool")
				.forEach((b) => b.classList.remove("active"));

			this.classList.add("active");

			selectedFieldType = this.dataset.type;
		});
	});
	init_recipient_system();
}

function init_recipient_system() {
	const input = document.getElementById("recipient-input");
	const btn = document.getElementById("add-recipient-btn");

	btn.onclick = function () {
		const email = input.value.trim();

		if (!email) return;

		if (recipients.includes(email)) {
			frappe.msgprint("Recipient already added");
			return;
		}

		recipients.push(email);

		const color = colorPalette[recipients.length % colorPalette.length];
		recipientColors[email] = color;

		if (!activeRecipient) {
			activeRecipient = email;
		}

		input.value = "";

		render_recipient_list();
	};
}

function render_recipient_list() {
	const container = document.getElementById("recipient-list");

	container.innerHTML = "";

	recipients.forEach((email) => {
		const div = document.createElement("div");

		div.className = "recipient-item";

		if (email === activeRecipient) {
			div.style.border = "1px solid var(--primary)";
			div.style.background = "var(--primary-light)";
		}

		div.style.padding = "6px";
		div.style.borderRadius = "4px";
		div.style.cursor = "pointer";
		div.style.marginBottom = "4px";

		const color = recipientColors[email];

		div.style.border = "2px solid " + color;
		div.style.background = email === activeRecipient ? color + "22" : "transparent";

		div.innerHTML = `
  <div style="display:flex;align-items:center;gap:6px;">
    <div style="
      width:10px;
      height:10px;
      border-radius:50%;
      background:${color};
    "></div>
    <span>${email}</span>
  </div>
`;

		div.onclick = function () {
			activeRecipient = email;
			render_recipient_list();
		};

		container.appendChild(div);
	});
}

function enable_drop(frm, overlay) {
	overlay.addEventListener("dragover", function (e) {
		e.preventDefault();
	});

	overlay.addEventListener("drop", function (e) {
		e.preventDefault();

		const type = e.dataTransfer.getData("field_type");
		if (!type) return;

		if (!activeRecipient) {
			frappe.msgprint("Add recipient first");
			return;
		}

		const rect = overlay.getBoundingClientRect();

		const x = e.clientX - rect.left;
		const y = e.clientY - rect.top;

		const box = create_box(frm, type);

		box.style.left = x + "px";
		box.style.top = y + "px";
		box.style.width = "120px";
		box.style.height = "40px";

		box.dataset.signer_email = activeRecipient;

		overlay.appendChild(box);

		attach_box_events(frm, box, overlay);
		save_box(frm, box, overlay);
	});
}

function field_button(type, label, icon) {
	return `
    <div class="esign-field-tool"
         draggable="true"
         data-type="${type}">
         
        <span class="field-icon">
            <i class="fa fa-${icon}"></i>
        </span>

        <span class="field-label">
            ${label}
        </span>

    </div>
  `;
}

const fieldIcons = {
	signature: "fa-pencil",
	initial: "fa-font",
	text: "fa-keyboard-o",
	name: "fa-user",
	email: "fa-envelope",
	date: "fa-calendar",
	number: "fa-hashtag",
	checkbox: "fa-check-square-o",
};

function create_box(frm, type = "signature") {
	const box = document.createElement("div");
	box.classList.add("esign-box");
	box.dataset.field_type = type;
	box.style.position = "absolute";

	const color = recipientColors[activeRecipient] || "#2563eb";

	box.style.cursor = "move";

	if (type === "checkbox") {
		box.style.width = "22px";
		box.style.height = "22px";
		box.style.display = "flex";
		box.style.alignItems = "center";
		box.style.justifyContent = "center";
	} else {
		box.style.border = "2px solid " + color;
		box.style.background = color + "22";
		box.style.minWidth = "80px";
		box.style.minHeight = "30px";
	}

	// CHECKBOX UI
	if (type === "checkbox") {
		const checkbox = document.createElement("input");
		checkbox.type = "checkbox";
		checkbox.disabled = true;
		checkbox.background = color + "22";
		checkbox.style.pointerEvents = "none";

		box.appendChild(checkbox);
	}

	if (type !== "checkbox") {
		const label = document.createElement("div");

		label.innerHTML = `
  <i class="fa ${fieldIcons[type] || "fa-square"}"></i>
  ${type.replace("_", " ").toUpperCase()}
`;

		// label.style.background = color;
		label.style.padding = "2px 6px";
		label.style.borderRadius = "3px";
		label.style.position = "absolute";
		label.style.top = "2px";
		label.style.left = "4px";
		label.style.background = "transparent";

		label.style.display = "flex";
		label.style.alignItems = "center";
		label.style.gap = "4px";
		label.style.fontSize = "9px";
		label.style.fontWeight = "600";
		label.style.color = color;
		label.style.pointerEvents = "none";

		box.appendChild(label);
	}

	// DELETE BUTTON
	const deleteBtn = document.createElement("div");
	deleteBtn.innerHTML = "✕";
	deleteBtn.style.position = "absolute";
	deleteBtn.style.top = "-8px";
	deleteBtn.style.right = "-8px";
	deleteBtn.style.width = "18px";
	deleteBtn.style.height = "18px";
	deleteBtn.style.borderRadius = "50%";
	deleteBtn.style.background = "#ef4444";
	deleteBtn.style.color = "white";
	deleteBtn.style.display = "flex";
	deleteBtn.style.alignItems = "center";
	deleteBtn.style.justifyContent = "center";
	deleteBtn.style.fontSize = "12px";
	deleteBtn.style.cursor = "pointer";
	deleteBtn.style.zIndex = "10";

	deleteBtn.addEventListener("click", function (e) {
		e.stopPropagation();

		if (!confirm("Delete this signature box?")) return;

		const rowname = box.dataset.rowname;

		if (rowname) {
			frm.doc.signature_fields = frm.doc.signature_fields.filter(
				(row) => row.name !== rowname,
			);

			frm.dirty();
			frm.refresh_field("signature_fields");
		}

		box.remove();

		frm.save();
		render_existing_boxes(frm);
	});

	box.appendChild(deleteBtn);

	if (type !== "checkbox") {
		const resize = document.createElement("div");

		resize.style.position = "absolute";
		resize.style.right = "0";
		resize.style.bottom = "0";
		resize.style.width = "10px";
		resize.style.height = "10px";
		resize.style.background = color;
		resize.style.cursor = "se-resize";

		box.appendChild(resize);
	}

	deleteBtn.style.opacity = "0";

	box.addEventListener("mouseenter", () => {
		if (box.dataset.field_type == "checkbox") {
			box.style.outline = "2px solid " + color;
		}
		deleteBtn.style.opacity = "1";
	});

	box.addEventListener("mouseleave", () => {
		box.style.outline = "none";
		deleteBtn.style.opacity = "0";
	});

	return box;
}

function attach_box_events(frm, box, overlay) {
	const resizeHandle = box.lastChild;

	box.addEventListener("mousedown", function (e) {
		e.stopPropagation();

		activeBox = box;
		activeOverlay = overlay;

		if (e.target === resizeHandle) {
			actionType = "resize";
		} else {
			actionType = "drag";
			offsetX = e.offsetX;
			offsetY = e.offsetY;
		}
	});
}

document.addEventListener("mousemove", function (e) {
	if (!activeBox || !actionType) return;

	const rect = activeOverlay.getBoundingClientRect();

	if (actionType === "drag") {
		activeBox.style.left = e.clientX - rect.left - offsetX + "px";
		activeBox.style.top = e.clientY - rect.top - offsetY + "px";
	}

	if (actionType === "resize") {
		const boxRect = activeBox.getBoundingClientRect();
		activeBox.style.width = e.clientX - boxRect.left + "px";
		activeBox.style.height = e.clientY - boxRect.top + "px";
	}
});

document.addEventListener("mouseup", function () {
	if (activeBox && activeOverlay) {
		update_child_table(cur_frm, activeBox, activeOverlay);
	}

	activeBox = null;
	actionType = null;
});

function save_box(frm, box, overlay) {
	const rect = overlay.getBoundingClientRect();

	const child = frm.add_child("signature_fields", {
		page_number: overlay.dataset.page,
		signer_email: box.dataset.signer_email,
		field_type: box.dataset.field_type,
		x_percent: (box.offsetLeft / rect.width) * 100,
		y_percent: (box.offsetTop / rect.height) * 100,
		width_percent: (box.offsetWidth / rect.width) * 100,
		height_percent: (box.offsetHeight / rect.height) * 100,
	});
	box.dataset.rowname = child.name;

	frm.refresh_field("signature_fields");
}

function update_child_table(frm, box, overlay) {
	const rect = overlay.getBoundingClientRect();
	const rowname = box.dataset.rowname;

	if (!rowname) return;

	const row = frm.doc.signature_fields.find((r) => r.name === rowname);
	if (!row) return;

	row.x_percent = (box.offsetLeft / rect.width) * 100;
	row.y_percent = (box.offsetTop / rect.height) * 100;
	row.width_percent = (box.offsetWidth / rect.width) * 100;
	row.height_percent = (box.offsetHeight / rect.height) * 100;

	frm.refresh_field("signature_fields");
}

function render_existing_boxes(frm) {
	// Prevent duplicate rendering
	document.querySelectorAll(".page-overlay").forEach((o) => (o.innerHTML = ""));

	frm.doc.signature_fields.forEach((field) => {
		const overlay = document.querySelector(`.page-overlay[data-page="${field.page_number}"]`);

		if (!overlay) return;

		// 🔥 IF SIGNED → SHOW SIGNATURE IMAGE
		if (field.signed && field.signature_image) {
			const img = document.createElement("img");
			img.src = field.signature_image;

			img.style.position = "absolute";
			img.style.left = field.x_percent + "%";
			img.style.top = field.y_percent + "%";
			img.style.width = field.width_percent + "%";
			img.style.height = field.height_percent + "%";
			img.style.objectFit = "contain";

			overlay.appendChild(img);
			return;
		}

		// 🔹 ELSE render editable box
		const previousRecipient = activeRecipient;
		activeRecipient = field.signer_email;

		const box = create_box(frm, field.field_type);

		activeRecipient = previousRecipient;

		box.style.left = field.x_percent + "%";
		box.style.top = field.y_percent + "%";
		box.style.width = field.width_percent + "%";
		box.style.height = field.height_percent + "%";

		box.dataset.rowname = field.name;
		box.dataset.signer_email = field.signer_email;

		overlay.appendChild(box);
		attach_box_events(frm, box, overlay);
	});
}

async function send_for_signature(frm) {
	const uniqueRecipients = [
		...new Set(frm.doc.signature_fields.map((f) => f.signer_email).filter(Boolean)),
	];

	if (!uniqueRecipients.length) {
		frappe.msgprint("Add at least one recipient field");
		return;
	}

	if (!frm.doc.signature_fields.length) {
		frappe.msgprint("Add at least one field");
		return;
	}

	if (frm.is_dirty()) {
		await frm.save();
	}

	frappe
		.call({
			method: "verp_staffing.esign.doctype.e_sign.e_sign.send_all_signers",
			args: {
				agreement: frm.doc.name,
			},
			freeze: true,
			freeze_message: "Sending emails...",
		})
		.then(() => {
			frm._pdf_loaded = false;
			frappe.msgprint("Emails sent successfully");

			lock_editor();

			frm.reload_doc();
		});
}

function lock_editor() {
	// disable drag fields
	document.querySelectorAll(".esign-field-tool").forEach((el) => {
		el.setAttribute("draggable", false);
		el.style.opacity = "0.5";
		el.style.pointerEvents = "none";
	});

	// disable recipient input
	const input = document.getElementById("recipient-input");
	const btn = document.getElementById("add-recipient-btn");

	if (input) input.disabled = true;
	if (btn) btn.disabled = true;

	// disable existing boxes
	document.querySelectorAll(".esign-box").forEach((box) => {
		box.style.pointerEvents = "none";
	});
}
