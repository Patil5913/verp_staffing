// // Copyright (c) 2025, Vrugle and contributors
// // For license information, please see license.txt
if (window.pdfjsLib) {
    pdfjsLib.GlobalWorkerOptions.workerSrc =
        "/assets/verp_staffing/js/pdf.worker.js";
}

frappe.ui.form.on("Pdf Agreement Template", {
    refresh(frm) {
        if (frm.doc.upload_pdf_template) {
            frm.trigger("render_builder");
        } else {
            // blank builder area
            const wrapper = frm.fields_dict && frm.fields_dict.builder_html && frm.fields_dict.builder_html.$wrapper;
            if (wrapper) wrapper.html("<div style='padding:10px;color:#666'>Upload a PDF template to start building.</div>");
        }

        frm.add_custom_button("Show Form Tour", () => {
            const tour_name = 'PDF Agreement Template Form';

            frm.tour.init({ tour_name })
                .then(() => frm.tour.start());
        });
    },

    upload_pdf_template(frm) {
        // re-render builder when user uploads a template
        frm.trigger("render_builder");
    },

    render_builder(frm) {
        const wrapper = frm.fields_dict && frm.fields_dict.builder_html && frm.fields_dict.builder_html.$wrapper;
        if (!wrapper) return;

        wrapper.html(`
            <div id="pdf-builder" style="display:flex; gap:20px; height: calc(100vh - 200px);">
                <div id="pdf-pages-wrap" style="flex:1; overflow:auto; padding:10px; background:#f7f7f7; border:1px solid #eaeaea;">
                    <div id="pdf-pages" style="max-width:100%; margin:auto;"></div>
                </div>

                <div id="sidebar" style="width:320px; border-left:1px solid #ddd; padding:15px; background:#fff; position:relative;">
                    <h4 style="margin-top:0">Fields</h4>
                    <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px;">
                        <button class="btn btn-sm btn-primary add-field" data-type="Text">Text</button>
                        <button class="btn btn-sm btn-primary add-field" data-type="Number">Number</button>
                        <button class="btn btn-sm btn-primary add-field" data-type="Payment_Terms">Payment Terms</button>
                        <button class="btn btn-sm btn-primary add-field" data-type="Date">Date</button>
                        <button class="btn btn-sm btn-primary add-field" data-type="Checkbox">Checkbox</button>
                        <button class="btn btn-sm btn-primary add-field" data-type="Signature">Signature</button>
                    </div>

                    <div style="margin-top:12px;">
                        <button class="btn btn-success" id="save-template">Save Template</button>
                        <button class="btn btn-default" id="clear-temp" style="margin-left:8px;">Clear</button>
                    </div>

                    <hr/>

                    <div class="agt-step">
                        <b>Quick Steps</b>
                        <ol style="margin:6px 0 0 18px; padding:0;">
                            <li>Select a field type (button highlights).</li>
                            <li>Click an empty area on PDF to place it.</li>
                            <li>Drag to move, bottom-right to resize.</li>
                            <li>Fields snap to a 10px grid & to other fields (edges/centers).</li>
                        </ol>
                    </div>

                    <div style="margin-top:auto; font-size:12px; color:#666;">
                        Tip: Don’t overlap fields. Click existing field to edit/delete.
                    </div>
                </div>
            </div>
        `);
        wrapper.find("#save-template").on("click", () => Save_Template(frm));

        // load PDF pages and existing fields
        load_pdf_into_builder(frm);
    }
});


async function load_pdf_into_builder(frm) {
    console.log("pdfjsLib:", window.pdfjsLib);

    if (!window.pdfjsLib) {
        frappe.throw("PDF.js not loaded. Check app_include_js.");
    }
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
    }

    // after pages created, load existing fields and enable interactions
    load_existing_fields(frm);
    setup_drag_drop(frm);
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
    fields.forEach(f => {
        render_field_on_canvas(frm, f);
    });
}

// central renderer for a single field object { field_id, name, type, page, x, y, width, height }
function render_field_on_canvas(frm, field) {
    const layer = $(`.pdf-page-container[data-page="${field.page}"] .fields-layer`);
    if (!layer.length) return;

    // create wrapper element
    const id = field.field_id || ("fld_" + (frappe.utils && frappe.utils.get_random ? frappe.utils.get_random(8) : Math.random().toString(36).slice(2, 10)));

    // If element already exists, remove and re-create (to update)
    layer.find(`[data-id="${id}"]`).remove();

    const $el = $(`
    <div class="pdf-field" data-id="${id}" data-type="${field.type}" style="
        position:absolute;
        top:${field.y}px;
        left:${field.x}px;
        width:${field.width || 150}px;
        height:${field.height || 30}px;
        border:1px dashed #222;
        background: rgba(255,255,255,0.85);
        padding:4px;
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

    /* bottom-right corner */
    .resize-se {
        right:-5px; 
        bottom:-5px; 
        cursor:se-resize;
    }

    /* right side */
    .resize-e {
        right:-5px;
        top:50%;
        transform:translateY(-50%);
        cursor:e-resize;
    }

    /* bottom side */
    .resize-s {
        left:50%;
        transform:translateX(-50%);
        bottom:-5px;
        cursor:s-resize;
    }
    </style>

        <div class="pdf-field-label" style="padding-right:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            ${escape_html(field.name || field.type)}
        </div>

        <div class="pdf-field-toolbar" style="display:none; gap:6px;">
            <button class="btn btn-xs btn-default edit-field" title="Edit">✎</button>
            <button class="btn btn-xs btn-danger delete-field" title="Delete">🗑</button>
        </div>

        <!-- RESIZE HANDLES -->
        <div class="resize-handle resize-se"></div>
        <div class="resize-handle resize-e"></div>
        <div class="resize-handle resize-s"></div>
    </div>
`);


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
    $("#pdf-builder .add-field").off("click").on("click", function () {
        const type = $(this).data("type");

        // instruct user
        frappe.msgprint(`Click on the PDF to place a "${type}" field. You will be prompted for the field name.`);

        // single click handler for placement
        $(".pdf-page-container").off("click.place_field").on("click.place_field", function (evt) {
            // compute position relative to container
            const $pc = $(this);
            const page = $pc.data("page");
            const off = $pc.offset();
            const x = evt.pageX - off.left;
            const y = evt.pageY - off.top;

            // require field name
            frappe.prompt([
                { fieldname: "field_name", label: "Field Name (unique)", fieldtype: "Data", reqd: 1 }
            ], function (values) {
                // build field object
                const real = (frm._pdf_page_sizes && frm._pdf_page_sizes[page]) || { width: $pc.width(), height: $pc.height() };

                const id = "fld_" + (frappe.utils && frappe.utils.get_random ? frappe.utils.get_random(8) : Math.random().toString(36).slice(2, 10));
                const fld = {
                    field_id: id,
                    name: values.field_name.trim(),
                    type: type,
                    page: page,
                    x: Math.round(x),
                    y: Math.round(y),
                    width: 150,
                    height: 30
                };

                // store and render
                if (!frm._temp_fields) frm._temp_fields = [];
                frm._temp_fields.push(fld);
                render_field_on_canvas(frm, fld);
            }, "Add Field");

            // remove the one-time handler
            $(".pdf-page-container").off("click.place_field");
        });
    });

    // clear placement on clear-temp
    $(document).off("click", "#clear-temp").on("click", "#clear-temp", function () {
        frm._temp_fields = [];
        $(".fields-layer").empty();
    });
}


// attach edit / delete handlers for a rendered field element
function attach_field_select_handlers($el, frm, field) {
    // show toolbar on hover
    $el.on("mouseenter", function () {
        $(this).find(".pdf-field-toolbar").show();
    }).on("mouseleave", function () {
        $(this).find(".pdf-field-toolbar").hide();
    });

    // edit
    $el.find(".edit-field").off("click").on("click", function (e) {
        e.stopPropagation();
        frappe.prompt([
            { fieldname: "field_name", label: "Field Name", fieldtype: "Data", reqd: 1, default: field.name }
        ], function (vals) {
            // update in temp store and DOM
            const newName = vals.field_name.trim();
            field.name = newName;
            $el.find(".pdf-field-label").text(newName);

            update_temp_field(frm, field.field_id, { name: newName });
        }, "Edit Field");
    });

    // delete
    $el.find(".delete-field").off("click").on("click", function (e) {
        e.stopPropagation();
        frappe.confirm(
            "Delete this field?",
            function () {
                // remove from DOM and temp array
                const fid = field.field_id;
                $el.remove();
                frm._temp_fields = (frm._temp_fields || []).filter(x => x.field_id !== fid);
            }
        );
    });

    // click on field focuses it (optional)
    $el.on("click", function (e) {
        e.stopPropagation();
        // maybe show a property panel in sidebar later
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
    let startX = 0, startY = 0, origLeft = 0, origTop = 0;
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
    });
}

// Escape helper for label text
function escape_html(s) {
    return String(s || "").replace(/[&<>"'`=\/]/g, function (c) {
        return {
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
            "'": '&#39;', '/': '&#x2F;', '`': '&#x60;', '=': '&#x3D;'
        }[c];
    });
}


function Save_Template(frm) {
    if (!frm) return;

    const names = (frm._temp_fields || []).map(f => f.name && f.name.trim()).filter(Boolean);
    const dup = names.find((n, i) => names.indexOf(n) !== i);
    if (dup) {
        frappe.msgprint(`Duplicate field name found: ${dup}. Use unique names.`);
        return;
    }

    // Attach real page sizes to any field missing them
    frm._temp_fields = (frm._temp_fields || []).map(f => {
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
    let startX, startY, startW, startH;
    let mode = null; // "se", "e", "s"

    $el.find(".resize-handle").on("mousedown", function (e) {
        e.stopPropagation();
        resizing = true;

        mode = $(this).attr("class").includes("resize-se")
            ? "se"
            : $(this).attr("class").includes("resize-e")
                ? "e"
                : "s";

        startX = e.pageX;
        startY = e.pageY;
        startW = $el.width();
        startH = $el.height();
    });

    $(document).on("mousemove.resize_" + field.field_id, function (e) {
        if (!resizing) return;

        let newW = startW;
        let newH = startH;

        if (mode === "se" || mode === "e")
            newW = Math.max(40, startW + (e.pageX - startX)); // min width 40

        if (mode === "se" || mode === "s")
            newH = Math.max(20, startH + (e.pageY - startY)); // min height 20

        $el.css({ width: newW + "px", height: newH + "px" });
    });

    $(document).on("mouseup.resize_" + field.field_id, function () {
        if (!resizing) return;

        resizing = false;

        // save to temp fields
        update_temp_field(frm, field.field_id, {
            width: Math.round($el.width()),
            height: Math.round($el.height())
        });
    });
}
