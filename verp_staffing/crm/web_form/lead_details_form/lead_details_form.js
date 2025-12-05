console.log("Webform JS Loaded!!!");

// Unique storage key per form
const AUDIT_KEY = "audit_trail_storage";

frappe.ready(function () {

    add_audit_event("form", { event: "form_opened" });

    // unique key for this webform
    let storage_key = "webform_filled_lead_details_form";

    frappe.web_form.on('signature_method', (field, value) => {
        if (value === "Upload") {
            show_upload_button();
        } else {
            frappe.web_form.set_value("signature_custom_html", "");
        }
    });

    // If method is already Upload on load
    if (frappe.web_form.get_value("signature_method") === "Upload") {
        show_upload_button();
    }

    render_file_upload_buttons();

    // check if already filled
    if (localStorage.getItem(storage_key) === "1") {
        console.log("Form already submitted previously.");
        // hide form and show message
        $(".web-form-container").html(`
    <div style="
        padding: clamp(16px, 4vw, 24px);
        margin: 16px;
        background: linear-gradient(135deg, #fff5f5 0%, #ffe3e3 100%);
        border: 2px solid #ff6b6b;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(255, 107, 107, 0.1);
        text-align: center;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
        animation: slideIn 0.3s ease-out;
    ">
        <div style="
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: clamp(48px, 12vw, 64px);
            height: clamp(48px, 12vw, 64px);
            background: #ff6b6b;
            border-radius: 50%;
            margin-bottom: 16px;
        ">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
        </div>
        
        <h3 style="
            margin: 0 0 12px 0;
            font-size: clamp(18px, 4vw, 24px);
            font-weight: 600;
            color: #d63031;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        ">
            Form Already Submitted
        </h3>
        
        <p style="
            margin: 0;
            font-size: clamp(14px, 3vw, 16px);
            color: #636e72;
            line-height: 1.6;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        ">
            You have already submitted this form. If you need to make changes, please contact support.
        </p>
    </div>
    
    <style>
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @media (max-width: 480px) {
            .web-form-container > div {
                margin: 12px;
                border-radius: 8px;
            }
        }
    </style>
`);
        return;
    }

    // when submit button is clicked
    if (frappe.web_form) {
        frappe.web_form.validate = () => {
            console.log("Validating form...");

            let entry_date = frappe.web_form.get_value("entry_date");
            if (!validate_entry_date(entry_date)) {
                return false;
            }

            // 2️⃣ SSN DIGIT
            let ssn_digit = frappe.web_form.get_value("ssn_digit");
            if (!validate_ssn_digit(ssn_digit)) {
                return false;
            }

            // 3️⃣ LEAD COURSE TABLE
            let lead_course = frappe.web_form.get_value("educational_details") || [];
            if (!validate_lead_course_table(lead_course)) {
                return false;
            }

            // 4️⃣ PAST EXPERIENCE TABLE
            let educational_details = frappe.web_form.get_value("past_experience_table") || [];
            if (!validate_past_experience_table(educational_details)) {
                return false;
            }

            // 5️⃣ ADDRESS HISTORY TABLE
            let address_history = frappe.web_form.get_value("address_history") || [];
            if (!validate_address_history(address_history)) {
                return false;
            }

            return true;
        };


        frappe.web_form.after_save = () => {
            frappe.msgprint("Form submitted successfully!");
            localStorage.removeItem(AUDIT_KEY);
            localStorage.setItem(storage_key, "1");
        };
    }

    frappe.web_form.on("signature", () => {
        add_audit_event("signature");
    });
});


window.addEventListener("beforeunload", () => {
    add_audit_event("form", { event: "form_refreshed" });
});

function is_valid_mm_yyyy(value) {
    return /^(0[1-9]|1[0-2])-[0-9]{4}$/.test(value);
}

function validate_past_experience_table(table) {
    for (let idx = 0; idx < table.length; idx++) {
        let row = table[idx];

        if (row.start_date && !is_valid_mm_yyyy(row.start_date)) {
            frappe.msgprint(`In Past Experience Table, Row ${idx + 1}:<br>Start Date must be MM-YYYY`);
            return false;
        }

        if (!row.is_currently_working) {
            if (!row.end_date) {
                frappe.msgprint(`In Past Experience Table, Row ${idx + 1}:<br>End Date is required.`);
                return false;
            }
            if (row.end_date && !is_valid_mm_yyyy(row.end_date)) {
                frappe.msgprint(`In Past Experience Table, Row ${idx + 1}:<br>End Date must be MM-YYYY`);
                return false;
            }
        }

        if (row.description) {
            const desc = row.description.replace(/\s/g, "");
            if (desc.length < 800) {
                frappe.msgprint(`In Past Experience Table, Row ${idx + 1}:<br>Description must contain at least 800 characters`);
                return false;
            }
        }
    }
    return true;
}


function validate_lead_course_table(table) {
    for (let idx = 0; idx < table.length; idx++) {
        let row = table[idx];

        if (row.start_date && !is_valid_mm_yyyy(row.start_date)) {
            frappe.msgprint(`In Education Details Table, Row ${idx + 1}:<br>Start Date must be MM-YYYY`);
            return false;
        }

        if (row.end_date && !is_valid_mm_yyyy(row.end_date)) {
            frappe.msgprint(`In Education Details Table, Row ${idx + 1}:<br>End Date must be MM-YYYY`);
            return false;
        }

        let grade = Number(row.grade);
        if (row.grade && !(grade >= 0 && grade <= 10)) {
            frappe.msgprint(`In Education Details Table, Row ${idx + 1}:<br>Grade must be between 0 and 10.`);
            return false;
        }
    }
    return true;
}


function validate_address_history(table) {
    for (let idx = 0; idx < table.length; idx++) {
        let row = table[idx];

        if (row.from_date && !is_valid_mm_yyyy(row.from_date)) {
            frappe.msgprint(`In Address History Table, Row ${idx + 1}:<br>From Date must be MM-YYYY`);
            return false;
        }

        if (row.to_date && !is_valid_mm_yyyy(row.to_date)) {
            frappe.msgprint(`In Address History Table, Row ${idx + 1}:<br>To Date must be MM-YYYY`);
            return false;
        }
    }
    return true;
}


function validate_entry_date(value) {
    if (value && !is_valid_mm_yyyy(value)) {
        frappe.msgprint("Entry Date Into USA/Canada must be in MM-YYYY format.");
        return false
    }
    return true
}

function validate_ssn_digit(value) {
    console.log("validate_ssn_digit")

    if (value && String(value).length !== 4) {
        frappe.msgprint("SSN must contain only last 4 digits.");
        return false
    }
    return true
}

function load_audit_trail() {
    try {
        return JSON.parse(localStorage.getItem(AUDIT_KEY)) || {
            "form visit logs": [],
            "signature update logs": []
        };
    } catch (e) {
        return {
            "form visit logs": [],
            "signature update logs": []
        };
    }
}

function save_audit_trail(audit) {
    localStorage.setItem(AUDIT_KEY, JSON.stringify(audit));
}

// Unified reusable function for adding event logs
function add_audit_event(type, data = {}) {
    let audit = load_audit_trail();

    if (type === "form") {
        audit["form visit logs"].push({
            event: data.event,
            timestamp: format_timestamp()
        });
    }

    if (type === "signature") {
        audit["signature update logs"].push({
            timestamp: format_timestamp()
        });
    }

    save_audit_trail(audit);

    // Also push into the hidden field for submission
    frappe.web_form.set_value("audit_trail", JSON.stringify(audit));
}

function format_timestamp() {
    let d = new Date();

    let day = String(d.getDate()).padStart(2, '0');
    let month = String(d.getMonth() + 1).padStart(2, '0');
    let year = d.getFullYear();

    let hours = String(d.getHours()).padStart(2, '0');
    let minutes = String(d.getMinutes()).padStart(2, '0');
    let seconds = String(d.getSeconds()).padStart(2, '0');

    return `${day}-${month}-${year}, ${hours}:${minutes}:${seconds}`;
}

function record_signature_event() {
    let signature = frappe.web_form.get_value("signature");

    if (!signature) {
        console.log("signature not found")
        return
    };

    let existing_json = frappe.web_form.get_value("signature_event_log");
    let log = [];

    if (existing_json) {
        try { log = JSON.parse(existing_json); }
        catch (e) { log = []; }
    }

    log.push({
        event: "signature_updated",
        timestamp: format_timestamp(),
        signature_length: signature.length
    });

    frappe.web_form.set_value("signature_event_log", JSON.stringify(log));
}

function show_upload_button() {
    let html = `
        <button class="btn btn-primary" id="open_signature_upload">
            Upload Image
        </button>
        <div id="signature_preview_area" style="margin-top: 15px;"></div>
    `;

    frappe.web_form.set_value("signature_custom_html", html);

    setTimeout(() => {
        $("#open_signature_upload").on("click", function () {
            open_signature_dialog();
        });
    }, 300);
}

function open_signature_dialog() {
    let selected_image = null;

    let d = new frappe.ui.Dialog({
        title: "Upload Signature Image",
        fields: [
            {
                label: "Select Image",
                fieldname: "file_input",
                fieldtype: "HTML",
                options: `<input type="file" accept="image/*" id="signature_file_input">`
            },
            {
                label: "Preview",
                fieldname: "preview",
                fieldtype: "HTML",
                options: `<div id="signature_preview" 
                            style="margin-top:10px; text-align:center;">
                          </div>`
            }
        ],
        primary_action_label: "Upload",
        primary_action(values) {
            if (!selected_image) {
                frappe.msgprint("Please select an image.");
                return;
            }
            upload_signature_file(selected_image, d);
        }
    });

    d.show();

    // file input listener
    $(document).on("change", "#signature_file_input", function (e) {
        selected_image = e.target.files[0];

        if (selected_image) {
            let reader = new FileReader();
            reader.onload = function (event) {
                $("#signature_preview").html(`
                    <div style="position:relative; display:inline-block;">
                        <img src="${event.target.result}"
                             style="max-width:200px; border:1px solid #ccc; padding:5px;">
                        <span id="delete_selected_image"
                              style="position:absolute; top:0; right:0; 
                                     background:red; color:white;
                                     padding:2px 5px; cursor:pointer;">
                            X
                        </span>
                    </div>
                `);
            };
            reader.readAsDataURL(selected_image);
        }
    });

    // delete selected image
    $(document).on("click", "#delete_selected_image", function () {
        selected_image = null;
        $("#signature_preview").html(`<span>No image selected</span>`);
        $("#signature_file_input").val("");
    });
}

function upload_signature_file(file, dialog) {
    let reader = new FileReader();

    reader.onload = function () {
        let base64_img = reader.result; // contains data:image/jpeg;base64,...

        frappe.call({
            method: "verp_staffing.crm.api.upload.upload_file",
            args: {
                filename: file.name,
                filedata: base64_img
            },
            callback: function (r) {
                if (r.message && r.message.success) {
                    frappe.msgprint("Image Uploaded Successfully!");
                    dialog.hide();
                    console.log(r.message);
                    frappe.web_form.set_value("signature_image", r.message.file_name);

                    // Set image in HTML field
                    frappe.web_form.set_value(
                        "signature_custom_html",
                        `<img src="${r.message.file_url}" 
                              style="max-width:200px; margin-top:10px;">`
                    );
                }
            }
        });
    };

    reader.readAsDataURL(file);
}

let label_map = {
    "visa_copy": "Visa Copy",
    "ead_card": "EAD Card",
    "driving_licence": "Driving Licence"
};

function render_file_upload_buttons() {
    let html = `
        <div id="visa_copy_container">
            <button class="btn btn-primary file-btn" data-field="visa_copy">Upload Visa Copy</button>
        </div>

        <div id="ead_card_container" style="margin-top:10px;">
            <button class="btn btn-primary file-btn" data-field="ead_card">Upload EAD Card</button>
        </div>

        <div id="driving_licence_container" style="margin-top:10px;">
            <button class="btn btn-primary file-btn" data-field="driving_licence">Upload Driving Licence</button>
        </div>
    `;

    frappe.web_form.set_value("files_custom_html", html);

    // Activate all buttons
    setTimeout(() => {
        $(".file-btn").on("click", function () {
            let target_field = $(this).data("field");
            open_file_upload_dialog(target_field);
        });
    }, 300);
}

function open_file_upload_dialog(target_field) {
    // use a fresh selected_file per dialog instance
    let selected_file = null;

    // generate a unique id for the file input so multiple dialogs don't clash
    const input_id = "custom_pdf_input_" + Date.now();

    let d = new frappe.ui.Dialog({
        title: "Upload PDF File",
        fields: [
            {
                label: "Select PDF File",
                fieldname: "file_input",
                fieldtype: "HTML",
                // use the unique id in the markup
                options: `<input type="file" accept="application/pdf" id="${input_id}">`
            },
            {
                label: "Preview",
                fieldname: "preview",
                fieldtype: "HTML",
                options: `<div id="pdf_preview_area" style="margin-top:10px; color:#666;">No file selected</div>`
            }
        ],
        primary_action_label: "Upload",
        primary_action(values) {
            if (!selected_file) {
                frappe.msgprint("Please select a PDF file.");
                return;
            }
            // call upload routine
            upload_pdf_file(selected_file, target_field, d);
        }
    });

    d.show();

    // cache wrapper for event delegation limited to this dialog
    const $wrap = d.wrapper;

    // change listener on file input (scoped to this dialog via wrapper)
    $wrap.on("change", `#${input_id}`, function (e) {
        selected_file = e.target.files[0];

        if (!selected_file) {
            // reset preview
            $wrap.find("#pdf_preview_area").html("No file selected");
            return;
        }

        if (selected_file.type !== "application/pdf") {
            frappe.msgprint("Only PDF files are allowed.");
            // clear selected_file and input
            selected_file = null;
            $wrap.find(`#${input_id}`).val("");
            $wrap.find("#pdf_preview_area").html("No file selected");
            return;
        }

        // show preview with delete button (replace the content each time)
        const previewHtml = `
            <div style="position:relative; margin-top:10px; display:inline-block;">
                <span style="font-weight:bold;">${selected_file.name}</span>
                <span id="delete_pdf_btn" 
                      style="position:absolute; top:0; right:-20px; color:white; background:red;
                             padding:2px 6px; border-radius:3px; cursor:pointer;">X</span>
            </div>
        `;
        $wrap.find("#pdf_preview_area").html(previewHtml);
    });

    // delete button (scoped to this dialog)
    $wrap.on("click", "#delete_pdf_btn", function () {
        selected_file = null;
        // reset input element
        $wrap.find(`#${input_id}`).val("");
        $wrap.find("#pdf_preview_area").html("No file selected");
    });

    // When dialog is hidden, remove listeners attached to wrapper to avoid leaks
    d.$wrapper.on("hide", function () {
        // off delegated handlers bound to this wrapper
        $wrap.off("change", `#${input_id}`);
        $wrap.off("click", "#delete_pdf_btn");
    });
}

function upload_pdf_file(file, target_field, dialog) {
    let reader = new FileReader();

    reader.onload = function () {
        let base64_pdf = reader.result;

        frappe.call({
            method: "verp_staffing.crm.api.upload.upload_file",
            args: {
                filename: file.name,
                filedata: base64_pdf
            },
            callback: function (r) {
                if (r.message && r.message.success) {
                    dialog.hide();

                    // Set File Name into Link Field
                    frappe.web_form.set_value(target_field, r.message.file_name);

                    // Show preview list below buttons
                    add_file_preview(target_field, r.message.file_url, r.message.file_name);
                } else {
                    frappe.msgprint("Upload failed: " + (r.message && r.message.error ? r.message.error : "Unknown error"));
                }
            },
            error: function (err) {
                frappe.msgprint("Upload failed. See console for details.");
                console.error(err);
            }
        });
    };

    reader.readAsDataURL(file);
}

// ------------------------------
// Show Uploaded File Below Buttons
// ------------------------------
function add_file_preview(field, url, name) {


    let container_id = "#" + field + "_container";

    let preview_html = `
        <div style="margin-top:5px;">
            <b>${label_map[field]}:</b>
            <a href="${url}" target="_blank">${name}</a>
        </div>
    `;

    // REPLACE the button with preview
    $(container_id).html(preview_html);
}