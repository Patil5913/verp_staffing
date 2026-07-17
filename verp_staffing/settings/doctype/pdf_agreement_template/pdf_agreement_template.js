// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt
const PREVIEW_FONT_SCALE = 1.5;

if (!document.getElementById("pdf-builder-style")) {
	const style = document.createElement("style");
	style.id = "pdf-builder-style";
	style.innerHTML = `
	.tool-section{
		margin-bottom:28px;
	}

	.tool-title{
		font-size:13px;
		font-weight:600;
		color:#6b7280;
		margin-bottom:12px;
		text-transform:uppercase;
		letter-spacing:.5px;
	}

	.builder-tool{
		padding:12px 14px;
		margin-bottom:8px;
		border:1px solid #dbe3ef;
		border-radius:10px;
		background:white;
		cursor:grab;
		transition:.18s;
		font-weight:500;
	}

	.builder-tool:hover{
		background:#eff6ff;
		border-color:#60a5fa;
	}

	.builder-tool.dragging{
		opacity:.4;
	}
		
	.pdf-field.selected{
		border:2px solid #2563eb!important;
		box-shadow:0 0 0 3px rgba(37,99,235,.15);
	}

	.fields-layer{
		min-height:100%;
	}

	.builder-tool{
		user-select:none;
	}

	.builder-tool:active{
		cursor:grabbing;
	}
	`;

	document.head.appendChild(style);
}
let CURRENT_TOOL = null;

frappe.ui.form.on("Pdf Agreement Template", {
	refresh(frm) {
		if (frm._pdf_dialog_observer) {
			frm._pdf_dialog_observer.disconnect();
			frm._pdf_dialog_observer = null;
		}
		frm._pdf_save_hook = false;
		if (frm.doc.upload_pdf_template) {
			frm.trigger("render_builder");
		} else {
			// blank builder area
			const wrapper =
				frm.fields_dict &&
				frm.fields_dict.builder_html &&
				frm.fields_dict.builder_html.$wrapper;
			if (wrapper)
				wrapper.html(
					"<div style='padding:10px;color:#666'>Upload a PDF template to start building.</div>",
				);
		}

		frm.add_custom_button("Show Form Tour", () => {
			const tour_name = "PDF Agreement Template";

			frm.tour.init({ tour_name }).then(() => frm.tour.start());
		});

		if (window._pdf_upload_observer) {
			window._pdf_upload_observer.disconnect();
			window._pdf_upload_observer = null;
		}

		window._pdf_upload_observer = new MutationObserver(function () {
			document.querySelectorAll(".btn-file-upload").forEach(function (btn) {
				const label = btn.querySelector(".mt-1");
				if (!label) return;
				const txt = label.innerText.trim();
				if (txt === "My Device") {
					// Make sure My Device is always visible
					btn.style.removeProperty("display");
				} else {
					// Hide Library, Link, Camera
					btn.style.setProperty("display", "none", "important");
				}
			});
		});

		window._pdf_upload_observer.observe(document.body, {
			childList: true,
			subtree: true,
		});
		const field = frm.fields_dict.upload_pdf_template;

		if (!field) return;

		field.df.options = {
			restrictions: {
				allowed_file_types: [".pdf"],
			},
		};

		field.refresh();
	},

	// upload_pdf_template(frm) {
	//     // re-render builder when user uploads a template
	//     frm.trigger("render_builder");
	// },
	upload_pdf_template(frm) {
		const file_url = frm.doc.upload_pdf_template;
		if (file_url && !file_url.toLowerCase().endsWith(".pdf")) {
			frm.set_value("upload_pdf_template", "");
			frappe.throw("Only PDF files are allowed.");
			return;
		}
		if (file_url) {
			frm.trigger("render_builder");
		}
	},
	render_builder(frm) {
		const wrapper =
			frm.fields_dict &&
			frm.fields_dict.builder_html &&
			frm.fields_dict.builder_html.$wrapper;
		if (!wrapper) return;

		wrapper.html(`
			<div id="pdf-builder" style="
				display:flex;
				height:calc(100vh - 180px);
				background:#f5f7fb;
				overflow:hidden;
			">

				<!-- LEFT TOOLBOX -->

				<div id="builder-toolbox"
					style="
					width:240px;
					background:white;
					border-right:1px solid #e5e7eb;
					padding:20px;
					overflow:auto;
				">

					<h4 style="margin-top:0;margin-bottom:18px;">
						Builder
					</h4>

					<div class="tool-section">

						<div class="tool-title">
							Standard Fields
						</div>

						<div class="builder-tool add-field" data-type="Text">
							📝 Text
						</div>

						<div class="builder-tool add-field" data-type="Number">
							🔢 Number
						</div>

						<div class="builder-tool add-field" data-type="Date">
							📅 Date
						</div>

						<div class="builder-tool add-field" data-type="Payment_Terms">
							📄 Payment Terms
						</div>

					</div>


					<div class="tool-section">

						<div class="tool-title">
							Customer Fields
						</div>

						<div class="builder-tool add-field"
							data-type="Signature">

							✍ Signature

						</div>

					</div>

					<hr>

					<button
						class="btn btn-success btn-block"
						id="save-template">

						Save Template

					</button>

					<button
						class="btn btn-default btn-block"
						id="clear-temp"
						style="margin-top:10px;">

						Clear

					</button>

				</div>


				<!-- PDF -->


				<div
					id="pdf-pages-wrap"
					style="
					flex:1;
					overflow:auto;
					padding:25px;
					background:#eef3fa;
				">

					<div id="pdf-pages"></div>

				</div>



				<!-- RIGHT SIDEBAR -->


				<div
					id="property-sidebar"
					style="
					width:340px;
					background:white;
					border-left:1px solid #e5e7eb;
					display:none;
					flex-direction:column;
				">


					<div
						style="
						padding:18px;
						border-bottom:1px solid #eee;
						display:flex;
						justify-content:space-between;
						align-items:center;
					">

						<h4 style="margin:0;">
							Properties
						</h4>

						<button
							id="close-properties"
							class="btn btn-xs">

							✕

						</button>

					</div>


					<div
						id="property-content"
						style="
						flex:1;
						overflow:auto;
						padding:20px;
					">

					</div>

				</div>

			</div>
			`);
		wrapper.find("#save-template").on("click", () => Save_Template(frm));
		wrapper.find("#close-properties").on("click", close_property_sidebar);
		// load PDF pages and existing fields
		if (frm.doc.upload_pdf_template) {
			load_pdf_into_builder(frm);
		}
		if (!frm._pdf_save_hook) {
			frm._pdf_save_hook = true;
			frappe.ui.form.on("Pdf Agreement Template", {
				before_save(frm) {
					// Commit temp fields to fields_json before Frappe saves
					const names = frm._temp_fields
						.map((f) => f.name && f.name.trim())
						.filter(Boolean);
					// const dup = names.find((n, i) => names.indexOf(n) !== i);
					// if (dup) {
					// 	frappe.msgprint(`Duplicate field name found: ${dup}. Use unique names.`);
					// 	frappe.validated = false;
					// 	return;
					// }

					// Attach real page sizes if missing
					frm._temp_fields = frm._temp_fields.map((f) => {
						if (!f.page_width || !f.page_height) {
							const $pc = $(`.pdf-page-container[data-page="${f.page}"]`);
							f.page_width = $pc.width() || f.page_width || 0;
							f.page_height = $pc.height() || f.page_height || 0;
						}
						return f;
					});

					frm.doc.fields_json = JSON.stringify(frm._temp_fields || []);
				},
			});
		}
	},
});

function close_property_sidebar() {
	$("#property-sidebar").hide();

	$("#property-content").empty();

	$(".pdf-field").removeClass("selected");
}

const PDFJS_URL = "/assets/verp_staffing/js/pdf.min.js";
const PDFJS_WORKER = "/assets/verp_staffing/js/pdf.worker.min.js";

// Load pdf.js once per browser session.
function load_pdfjs() {
	if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
	if (window._dsc_pdfjs_promise) return window._dsc_pdfjs_promise;

	window._dsc_pdfjs_promise = new Promise((resolve, reject) => {
		const s = document.createElement("script");
		s.src = PDFJS_URL;
		s.onload = () => {
			if (window.pdfjsLib) {
				window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER;
				resolve(window.pdfjsLib);
			} else {
				reject(new Error(__("pdf.js failed to initialise.")));
			}
		};
		s.onerror = () => reject(new Error(__("Could not load the PDF viewer (pdf.js).")));
		document.head.appendChild(s);
	});
	return window._dsc_pdfjs_promise;
}

async function load_pdf_into_builder(frm) {
	//first load pdf.js if not already loaded
	load_pdfjs()
		.then(async () => {
			const pdf_url = frappe.urllib.get_full_url(frm.doc.upload_pdf_template);

			if (!pdf_url) return;

			// ensure temp fields container
			if (!frm._temp_fields) frm._temp_fields = [];

			const wrapper = $("#pdf-pages");
			wrapper.empty();

			// load with pdfjsLib (assumes you included require() and worker elsewhere)
			const pdf = await pdfjsLib.getDocument(pdf_url).promise;

			// render each page as image and a positioned overlay div
			for (let i = 1; i <= pdf.numPages; i++) {
				const page = await pdf.getPage(i);
				const viewport = page.getViewport({ scale: 1.5 });

				// render to canvas off-DOM
				const canvas = document.createElement("canvas");
				canvas.width = viewport.width;
				canvas.height = viewport.height;
				const ctx = canvas.getContext("2d");
				await page.render({ canvasContext: ctx, viewport: viewport }).promise;

				// append page container
				const pageHtml = $(`
					<div class="pdf-page-container" data-page="${i}" style="position:relative; margin: 18px auto; width:${viewport.width}px; height:${viewport.height}px; box-shadow:0 1px 4px rgba(0,0,0,0.08); background:#fff;">
						<img src="${canvas.toDataURL()}" class="pdf-page-img" style="width:100%; height:100%; display:block;" />
						<div class="fields-layer" style="position:absolute; top:0; left:0; width:100%; height:100%;"></div>
					</div>
				`);

				wrapper.append(pageHtml);
				pageHtml.on("click", function (e) {
					if (e.target !== this) return;

					close_property_sidebar();
				});
			}

			// after pages created, load existing fields and enable interactions
			load_existing_fields(frm);
			setup_drag_drop(frm);
		})
		.catch((err) => {
			frappe.msgprint(
				`Error loading PDF template: ${frappe.utils.escape_html(
					(err && err.message) || String(err),
				)}`,
			);
		});
}

// Render saved fields from frm.doc.fields_json into overlay
function load_existing_fields(frm) {
	const raw = frm.doc.fields_json || frm.doc.fields_json === "" ? frm.doc.fields_json : null;

	let fields = [];
	try {
		if (raw) fields = JSON.parse(raw);
	} catch (e) {
		console.error("fields_json parse error", e);
		fields = [];
	}

	// store to temp
	frm._temp_fields = fields.slice();

	// render each
	fields.forEach((f) => {
		render_field_on_canvas(frm, f);
	});
}

// Place holders for each field type
const PREVIEW_VALUES = {
	Text: "Acme Corporation Private Limited",
	Number: "₹ 12,45,000",
	Payment_Terms: "Net 30 days from invoice date",
	Date: "31 March 2026",
	Checkbox: "☑",
	Signature: "Johnathan Smith",
};

// central renderer for a single field object { field_id, name, type, page, x, y, width, height }
function render_field_on_canvas(frm, field) {
	const layer = $(`.pdf-page-container[data-page="${field.page}"] .fields-layer`);
	if (!layer.length) return;

	// create wrapper element
	const id =
		field.field_id ||
		"fld_" +
			(frappe.utils && frappe.utils.get_random
				? frappe.utils.get_random(8)
				: Math.random().toString(36).slice(2, 10));

	// If element already exists, remove and re-create (to update)
	layer.find(`[data-id="${id}"]`).remove();
	const previewText = field.builder_placeholder || PREVIEW_VALUES[field.type] || field.name;

	const $el = $(`
    <div class="pdf-field" data-id="${id}" data-type="${field.type}" style="
        position:absolute;
        top:${field.y}px;
        left:${field.x}px;
        width:${field.width || 150}px;
        height:${field.height || 30}px;
        border:1px dashed #222;
        background: rgba(255,255,255,0.85);
        padding:0px;
        box-sizing:border-box;
        cursor:move;
        display:flex;
        align-items:center;
        justify-content:space-between;
        font-size:12px;
        z-index:10;
    ">
        <style>
			.resize-handle {
				position:absolute;
				width:10px;
				height:10px;
				background:#333;
				border-radius:2px;
				z-index:20;
			}
			.field-close{
				position:absolute;
				top:-10px;
				right:-10px;
				width:22px;
				height:22px;
				border-radius:50%;
				background:#ef4444;
				color:white;
				display:flex;
				align-items:center;
				justify-content:center;
				cursor:pointer;
				font-size:13px;
				font-weight:600;
				box-shadow:0 3px 10px rgba(0,0,0,.15);
				opacity:0;
				transition:.18s;
			}
			.pdf-field:hover .field-close{
				opacity:1;
			}
			.pdf-field{
				border:2px dashed #94a3b8!important;
				border-radius:8px;
				background:rgba(255,255,255,.92);
				transition:.15s;
			}
			.pdf-field.selected{
				border-color:#2563eb!important;
				background:#eff6ff;
				box-shadow:0 0 0 3px rgba(37,99,235,.18);
			}
			.resize-handle{
				position:absolute;
				width:12px;
				height:12px;
				right:-6px;
				bottom:-6px;
				background:#2563eb;
				border-radius:3px;
				cursor:nwse-resize;
			}
			#property-content label{
				font-weight:600;
				font-size:13px;
				margin-top:14px;
				display:block;
			}
			#property-content input{
				width:100%;
				margin-top:6px;
				margin-bottom:10px;
			}
    </style>

        <div class="pdf-field-preview"
			style="
			display:flex;
			align-items:center;
			justify-content:flex-start;
			padding:2px;
			font-family:revert-layer;
			font-size:${field.font_size * PREVIEW_FONT_SCALE}px;
			line-height:${field.line_height};
			white-space:normal;
			overflow:hidden;
			width:100%;
			height:100%;"
		>
  ${escape_html(previewText)}
	</div>
        <div class="field-close">
			✕
		</div>

        <!-- RESIZE HANDLES -->
        <div class="resize-handle"></div>
    </div>
`);
	const preview = $el.find(".pdf-field-preview")[0];

	const canvas = document.createElement("canvas");
	const ctx = canvas.getContext("2d");

	ctx.font = window.getComputedStyle(preview).font;

	layer.append($el);

	// store id in dataset if missing
	if (!field.field_id) field.field_id = id;

	// attach interactions
	make_field_resizable($el, frm, field);
	make_field_draggable($el, frm, field);
	attach_field_select_handlers($el, frm, field);
}

// Setup the workflow of selecting "Add Field" and clicking the PDF to place it
function setup_drag_drop(frm) {
	// LEFT TOOLBOX

	$(".builder-tool")
		.attr("draggable", true)

		.off("dragstart")

		.on("dragstart", function (e) {
			CURRENT_TOOL = $(this).data("type");

			$(this).addClass("dragging");

			e.originalEvent.dataTransfer.effectAllowed = "copy";

			e.originalEvent.dataTransfer.setData("text/plain", CURRENT_TOOL);
		})

		.off("dragend")

		.on("dragend", function () {
			$(this).removeClass("dragging");

			CURRENT_TOOL = null;
		});
	// PDF PAGE
	$(".fields-layer")
		.off("dragover")

		.on("dragover", function (e) {
			e.preventDefault();

			e.originalEvent.dataTransfer.dropEffect = "copy";
		});

	$(".fields-layer")
		.off("drop")

		.on("drop", function (e) {
			e.preventDefault();

			if (!CURRENT_TOOL) return;

			const layer = $(this);

			const page = layer.closest(".pdf-page-container").data("page");

			const off = layer.offset();

			const x = e.originalEvent.pageX - off.left;

			const y = e.originalEvent.pageY - off.top;

			create_new_field(frm, CURRENT_TOOL, page, x, y);
		});

	// CLEAR

	$("#clear-temp")
		.off("click")

		.on("click", function () {
			frm._temp_fields = [];

			$(".fields-layer").empty();

			close_property_sidebar();

			frm.dirty();
		});
}

function create_new_field(frm, type, page, x, y) {

	frappe.prompt(
		[
			{
				fieldname: "field_name",
				label: "Field Name",
				fieldtype: "Data",
				reqd: 1,
			},
			{
				fieldname: "placeholder",
				label: "Builder Preview",
				fieldtype: "Data",
				hidden: type == "Signature" ? 1 : 0,
			},
			{
				fieldname: "font_size",
				label: "Font Size",
				fieldtype: "Int",
				hidden: type == "Signature" ? 1 : 0,
				default: 12,
			},
			{
				fieldname: "line_height",
				label: "Line Height",
				fieldtype: "Float",
				hidden: type == "Signature" ? 1 : 0,
				default: 1.2,
			},
		],

		function (values) {
			const id =
				"fld_" +
				(frappe.utils.get_random
					? frappe.utils.get_random(8)
					: Math.random().toString(36).substring(2));

			const field = {
				field_id: id,
				name: values.field_name.trim(),
				type: type,
				page: page,
				x: Math.round(x),
				y: Math.round(y),
				width: 150,
				height: 30,
				font_size: values.font_size,
				line_height: values.line_height,
				font_family: "helv",
				wrap: true,
				overflow: "warn",
				builder_placeholder: values.placeholder || "",
			};

			if (!frm._temp_fields) frm._temp_fields = [];

			frm._temp_fields.push(field);

			render_field_on_canvas(frm, field);

			frm.dirty();
		},

		"Create Field",
	);
}

function open_property_sidebar(frm, field) {
	if (field.type == "Signature") {
		return;
	}
	const panel = $("#property-sidebar");

	const body = $("#property-content");

	panel.show();

	$(".pdf-field").removeClass("selected");

	$(`[data-id="${field.field_id}"]`).addClass("selected");

	body.html(`

		<label>Field Name</label>

		<input
		id="prop-name"
		value="${escape_html(field.name)}">

		<label>Preview Text</label>

		<input
		id="prop-placeholder"
		value="${escape_html(field.builder_placeholder || "")}">

		<label>Font Size</label>

		<input
		id="prop-font"
		type="number"
		value="${field.font_size}">

		<label>Line Height</label>

		<input
		id="prop-line"
		type="number"
		step=".1"
		value="${field.line_height}">

		<label>Width</label>

		<input
		value="${Math.round(field.width)}"
		disabled>

		<label>Height</label>

		<input
		value="${Math.round(field.height)}"
		disabled>

	`);

	$("#prop-name").on("input", function () {
		field.name = this.value;

		update_temp_field(frm, field.field_id, {
			name: field.name,
		});

		frm.dirty();
	});

	$("#prop-placeholder").on("input", function () {
		field.builder_placeholder = this.value;

		update_temp_field(frm, field.field_id, {
			builder_placeholder: this.value,
		});

		$(`[data-id="${field.field_id}"]`)
			.find(".pdf-field-preview")
			.text(this.value || PREVIEW_VALUES[field.type]);

		frm.dirty();
	});

	$("#prop-font").on("input", function () {
		field.font_size = parseInt(this.value) || 12;

		update_temp_field(frm, field.field_id, {
			font_size: field.font_size,
		});

		$(`[data-id="${field.field_id}"]`)
			.find(".pdf-field-preview")
			.css("font-size", field.font_size * PREVIEW_FONT_SCALE + "px");

		frm.dirty();
	});

	$("#prop-line").on("input", function () {
		field.line_height = parseFloat(this.value) || 1.2;

		update_temp_field(frm, field.field_id, {
			line_height: field.line_height,
		});

		$(`[data-id="${field.field_id}"]`)
			.find(".pdf-field-preview")
			.css("line-height", field.line_height);

		frm.dirty();
	});
}

function attach_field_select_handlers($el, frm, field) {
	$el.off("click");

	$el.on("click", function (e) {
		e.stopPropagation();

		open_property_sidebar(frm, field);
	});

	$el.find(".field-close")

		.off("click")

		.on("click", function (e) {
			e.stopPropagation();

			frappe.confirm(
				"Delete field?",

				function () {
					$el.remove();

					console.log("frm._temp_fields: ", frm._temp_fields, field);
					frm._temp_fields = (frm._temp_fields || []).filter(
						(d) => d.field_id !== field.field_id,
					);
					close_property_sidebar();

					frm.dirty();
				},
			);
		});
}

// simple update helper
function update_temp_field(frm, field_id, updates) {
	frm._temp_fields = frm._temp_fields || [];
	for (let i = 0; i < frm._temp_fields.length; i++) {
		if (frm._temp_fields[i].field_id === field_id) {
			Object.assign(frm._temp_fields[i], updates);
			break;
		}
	}
}

// draggable implementation (mouse events) — $el is jQuery element
function make_field_draggable($el, frm, field) {
	let isDragging = false;
	let startX = 0,
		startY = 0,
		origLeft = 0,
		origTop = 0;
	const $container = $el.closest(".pdf-page-container");
	const layer = $container.find(".fields-layer");

	$el.on("mousedown", function (e) {
		// only left button
		if (e.which !== 1) return;
		isDragging = true;
		startX = e.pageX;
		startY = e.pageY;
		origLeft = parseInt($el.css("left"), 10) || 0;
		origTop = parseInt($el.css("top"), 10) || 0;
		$el.css("opacity", 0.85);
		e.preventDefault();
	});

	$(document).on("mousemove.pdffield." + field.field_id, function (e) {
		if (!isDragging) return;
		const dx = e.pageX - startX;
		const dy = e.pageY - startY;
		const newLeft = origLeft + dx;
		const newTop = origTop + dy;

		// clamp inside container
		const maxLeft = layer.width() - $el.outerWidth();
		const maxTop = layer.height() - $el.outerHeight();
		const clampedLeft = Math.max(0, Math.min(newLeft, maxLeft));
		const clampedTop = Math.max(0, Math.min(newTop, maxTop));

		$el.css({ left: clampedLeft + "px", top: clampedTop + "px" });
	});

	$(document).on("mouseup.pdffield." + field.field_id, function (e) {
		if (!isDragging) return;
		isDragging = false;
		$el.css("opacity", 1);

		// save new coords to frm._temp_fields
		const left = parseInt($el.css("left"), 10) || 0;
		const top = parseInt($el.css("top"), 10) || 0;
		update_temp_field(frm, field.field_id, { x: Math.round(left), y: Math.round(top) });
		frm.dirty();
	});
}

// Escape helper for label text
function escape_html(s) {
	return String(s || "").replace(/[&<>"'`=\/]/g, function (c) {
		return {
			"&": "&amp;",
			"<": "&lt;",
			">": "&gt;",
			'"': "&quot;",
			"'": "&#39;",
			"/": "&#x2F;",
			"`": "&#x60;",
			"=": "&#x3D;",
		}[c];
	});
}

function Save_Template(frm) {
	if (!frm) return;

	const names = (frm._temp_fields || []).map((f) => f.name && f.name.trim()).filter(Boolean);
	// const dup = names.find((n, i) => names.indexOf(n) !== i);
	// if (dup) {
	// 	frappe.msgprint(`Duplicate field name found: ${dup}. Use unique names.`);
	// 	return;
	// }

	// Attach real page sizes to any field missing them
	frm._temp_fields = (frm._temp_fields || []).map((f) => {
		if (!f.page_width || !f.page_height) {
			const page = f.page;
			const real = (frm._pdf_page_sizes && frm._pdf_page_sizes[page]) || null;
			if (real) {
				f.page_width = real.width;
				f.page_height = real.height;
			} else {
				// fallback: use the page DOM size (less accurate)
				const $pc = $(`.pdf-page-container[data-page="${page}"]`);
				f.page_width = $pc.width() || f.page_width || 0;
				f.page_height = $pc.height() || f.page_height || 0;
			}
		}
		return f;
	});

	// commit to doctype field and save
	frm.set_value("fields_json", JSON.stringify(frm._temp_fields || []));
	frm.save();
}

function make_field_resizable($el, frm, field) {
	let resizing = false;

	let startX;
	let startY;

	let startWidth;
	let startHeight;

	$el.find(".resize-handle")
		.off("mousedown")
		.on("mousedown", function (e) {
			e.preventDefault();
			e.stopPropagation();

			resizing = true;

			startX = e.pageX;
			startY = e.pageY;

			startWidth = $el.outerWidth();
			startHeight = $el.outerHeight();

			$(document.body).css("cursor", "nwse-resize");
		});

	$(document)
		.off("mousemove.resize_" + field.field_id)
		.on("mousemove.resize_" + field.field_id, function (e) {
			if (!resizing) return;

			const dx = e.pageX - startX;
			const dy = e.pageY - startY;

			const width = Math.max(40, startWidth + dx);
			const height = Math.max(20, startHeight + dy);

			$el.css({
				width: width,
				height: height,
			});

			update_temp_field(frm, field.field_id, {
				width,
				height,
			});

			// Update sidebar if selected
			if ($el.hasClass("selected")) {
				$("#property-content input").eq(4).val(Math.round(width));

				$("#property-content input").eq(5).val(Math.round(height));
			}
		});

	$(document)
		.off("mouseup.resize_" + field.field_id)
		.on("mouseup.resize_" + field.field_id, function () {
			if (!resizing) return;

			resizing = false;

			$(document.body).css("cursor", "");

			field.width = $el.outerWidth();
			field.height = $el.outerHeight();

			update_temp_field(frm, field.field_id, {
				width: field.width,
				height: field.height,
			});

			frm.dirty();
		});
}
