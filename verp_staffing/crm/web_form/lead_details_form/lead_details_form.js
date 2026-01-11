// Unique storage key per form
const AUDIT_KEY = "audit_trail_storage";
// unique key for this webform
let storage_key = "webform_filled_lead_details_form";
// max file size
const MAX_PDF_SIZE = 1 * 1024 * 1024; // 1 MB in bytes

frappe.ready(function () {
    // Wait until Web Form UI loads
    add_audit_event("form", { event: "form_opened" });

    // remove discard button
    document.querySelector('.discard-btn').remove();

    const fields_to_hide = [
        "agreement_link", "signature_image", "audit_trail", "customer",
        "visa_copy", "ead_card", "driving_licence", "old_resume",
    ];

    fields_to_hide.forEach(fieldname => {
        frappe.web_form.set_df_property(fieldname, "hidden", 1);
    });

    setTimeout(() => {
        const wrapper = document.querySelector(
            '.control-input-wrapper'
        );

        if (wrapper) {
            wrapper.style.borderBottom = "none";
            wrapper.style.boxShadow = "none";

            const inner = wrapper.querySelector(".control-input");
            if (inner) {
                inner.style.borderBottom = "none";
                inner.style.boxShadow = "none";
            }
        }
    }, 300);

    setTimeout(() => {
        controlNextButton();
        controlSubmitButton();
        attachCheckboxListeners();
    }, 500);

    // 1. Get PDF path from URL (?file=path/to.pdf)
    const urlParams = new URLSearchParams(window.location.search);

    // Supported key names
    const salesOrder = urlParams.get("so")
    const customerValue = urlParams.get("c");
    const agreementValue = urlParams.get("agr");
    const pdfValue = urlParams.get("p");


    // 2. If lead exists → store in webform field "lead"
    if (customerValue) {
        frappe.web_form.set_value("customer", customerValue);
    }

    if (agreementValue) {
        frappe.web_form.set_value("agreement_link", agreementValue);
    }

    // sales order is mandatory now
    if (!salesOrder) {
        console.error("Sales Order missing in URL");
        return;
    }

    if (pdfValue) {
        // fetch Agreement by Sales Order
        frappe.call({
            method: "verp_staffing.crm.api.pdf_to_image.pdf_to_images",
            args: {
                path: pdfValue
            },
            callback: function (res) {
                if (!res.message || !res.message.length) {
                    console.error("PDF to image conversion failed");
                    return;
                }

                let html = "";

                res.message.forEach(img => {
                    html += `
                        <img 
                            src="${img}" 
                            style="width:100%; margin-bottom:20px; border:1px solid #ccc;"
                        >
                    `;
                });

                frappe.web_form.set_value("agreement_html", html);
            }
        });
    }

    frappe.web_form.on('signature_method', (field, value) => {
        if (value === "Upload") {
            show_upload_button();
        } else if (value === "Text") {
            show_text_button()
        } else {
            frappe.web_form.set_value("signature_custom_html", "");
        }
    });

    // If method is already Upload on load
    if (frappe.web_form.get_value("signature_method") === "Upload") {
        show_upload_button();
    }

    // If method is already Upload on load
    if (frappe.web_form.get_value("signature_method") === "Text") {
        show_text_button();
    }

    render_file_upload_buttons();

    // check if already filled
    if (localStorage.getItem(storage_key) === "1") {
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

            let signature_method = frappe.web_form.get_value("signature_method") || []
            if (!validate_signature(signature_method)) {
                return false
            }

            let email = frappe.web_form.get_value("email");
            if (!validate_email(email, "Email")) {
                return false;
            }

            let personal_phone = frappe.web_form.get_value("personal_phone_number");
            if (!validate_phone(personal_phone, "Personal Phone Number")) {
                return false;
            }

            let entry_date = frappe.web_form.get_value("entry_date");
            if (!validate_entry_date(entry_date)) {
                return false;
            }

            let ssn_digit = frappe.web_form.get_value("ssn_digit");
            if (!validate_ssn_digit(ssn_digit)) {
                return false;
            }

            let lead_course = frappe.web_form.get_value("educational_details") || [];
            if (!validate_lead_course_table(lead_course)) {
                return false;
            }

            let educational_details = frappe.web_form.get_value("past_experience_table") || [];
            if (!validate_past_experience_table(educational_details)) {
                return false;
            }

            let address_history = frappe.web_form.get_value("address_history") || [];
            if (!validate_address_history(address_history)) {
                return false;
            }

            let marketing_phone = frappe.web_form.get_value("number_for_marketing");
            if (!validate_phone(marketing_phone, "Marketing Phone Number")) {
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
        controlNextButton();
        add_audit_event("signature");
    });

    function waitAndCheckFile(fieldname) {
        setTimeout(() => {
            let val = frappe.web_form.get_value(fieldname);
            controlSubmitButton();
        }, 300);
    }

    frappe.web_form.on("visa_copy", () => waitAndCheckFile("visa_copy"));
    frappe.web_form.on("ead_card", () => waitAndCheckFile("ead_card"));

});

window.addEventListener("beforeunload", () => {
    // reset signature logs on refresh
    let audit = load_audit_trail();
    audit["signature update logs"] = [];
    save_audit_trail(audit);
});

function validate_email(email, label) {
    const email_regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email_regex.test(email)) {
        frappe.msgprint(`${label} is not a valid email address`);
        return false;
    }
    return true;
}

function validate_phone(phone, label) {
    // allows +, digits, spaces, hyphens
    const phone_regex = /^[+]?[\d\s-]{6,20}$/;
    if (!phone_regex.test(phone)) {
        frappe.msgprint(
            `${label} must contain only numbers and optional country code (+)`
        );
        return false;
    }
    return true;
}


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

    if (value && String(value).length !== 4) {
        frappe.msgprint("SSN must contain only last 4 digits.");
        return false
    }
    return true
}

function validate_signature(method) {

    if (method === "Upload") {
        let signature_image = frappe.web_form.get_value("signature_image");

        if (!signature_image) {
            frappe.msgprint("Please upload your signature image.");
            return false;
        }
        return true;
    }

    if (method === "Text") {
        let signature_image = frappe.web_form.get_value("signature_image");

        if (!signature_image) {
            frappe.msgprint("Please provide your Text signature image.");
            return false;
        }
        return true;
    }

    if (method === "Draw") {
        let signature = frappe.web_form.get_value("signature");

        if (!signature) {
            frappe.msgprint("Please draw your signature.");
            return false;
        }
        return true;
    }

    // If no valid method selected
    frappe.msgprint("Please select a signature method.");
    return false;
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

function show_text_button() {
    let html = `
        <button class="btn btn-primary" id="open_signature_upload">
            Provide Text Signature
        </button>
        <p style="color:red; font-size:12px; margin-top:5px;">
            * Text Signature is compulsory
        </p>
        <div id="signature_preview_area" style="margin-top: 15px;"></div>
    `;

    frappe.web_form.set_value("signature_custom_html", html);

    setTimeout(() => {
        $("#open_signature_upload").on("click", function () {
            open_text_dialog();
        });
    }, 300);
}

function load_signature_fonts() {
    if (document.getElementById("signature-fonts")) return;

    const link = document.createElement("link");
    link.id = "signature-fonts";
    link.rel = "stylesheet";
    link.href =
        "https://fonts.googleapis.com/css2?" +
        "family=Sacramento&" +
        "family=Mr+Dafoe&" +
        "family=Yellowtail&" +
        "family=Marck+Script&" +
        "family=Alex+Brush&" +
        "display=swap";

    document.head.appendChild(link);
}

function open_text_dialog() {
    load_signature_fonts();

    const fonts = [
        "Sacramento",      // ⭐ most natural handwritten signature
        "Mr Dafoe",        // bold, marker-style signature
        "Yellowtail",      // smooth cursive signature
        "Marck Script",    // clean handwritten look
        "Alex Brush"       // elegant but still signature-like
    ];


    let selectedFont = fonts[0];

    let d = new frappe.ui.Dialog({
        title: "Create Text Signature",
        fields: [
            {
                label: "Your Name",
                fieldname: "signature_text",
                fieldtype: "Data",
                reqd: 1
            },
            {
                fieldname: "preview_html",
                fieldtype: "HTML",
                options: `
                    <div style="margin-top:16px;">
                        <div id="signature_text_preview"
                             style="
                                font-size:44px;
                                font-weight: 400;
                                letter-spacing: 0.5px;
                                line-height: 1.2;
                                font-family:${selectedFont};
                                padding:12px;
                                border-bottom:1px solid #ddd;
                             ">
                        </div>

                        <div id="font_buttons" style="margin-top:14px;"></div>

                        <p style="
                            margin-top:16px;
                            font-size:13px;
                            color:#842029;
                            background:#f8d7da;
                            padding:12px;
                            border-radius:8px;
                        ">
                            <b>Important:</b>
                            Once you click <b>Upload Signature</b>,
                            this signature will be <u>locked</u> and cannot be changed.
                        </p>
                    </div>
                `
            }
        ],
        primary_action_label: "Upload Signature",
        primary_action(values) {
            if (!values.signature_text) {
                frappe.msgprint("Please enter your name.");
                return;
            }

            generate_signature_image(
                values.signature_text,
                selectedFont,
                d
            );
        }
    });

    d.show();

    const $wrap = d.wrapper;

    const rotate = (Math.random() * 1.5 - 0.75).toFixed(2);

    $wrap.find("#signature_text_preview").css(
        "transform",
        `rotate(${rotate}deg)`
    );


    // Inject clean CSS once
    if (!document.getElementById("signature-style")) {
        $("<style id='signature-style'>\
            .signature-font-grid {\
                display:grid;\
                grid-template-columns:repeat(auto-fit,minmax(130px,1fr));\
                gap:10px;\
            }\
            .signature-font-btn {\
                background:#ffffff;\
                border:1px solid #e5e7eb;\
                border-radius:10px;\
                padding:10px;\
                font-size:14px;\
                cursor:pointer;\
                transition:all .15s ease;\
                text-align:center;\
            }\
            .signature-font-btn:hover {\
                background:#f9fafb;\
            }\
            .signature-font-btn.active {\
                border-color:#2563eb;\
                background:#eef2ff;\
                box-shadow:0 0 0 2px rgba(37,99,235,.15);\
            }\
        </style>").appendTo("head");
    }

    // Render font buttons
    let btnHtml = `<div class="signature-font-grid">`;

    fonts.forEach(font => {
        btnHtml += `
            <button type="button"
                    class="signature-font-btn ${font === selectedFont ? "active" : ""}"
                    data-font="${font}"
                    style="font-family:${font};">
                ${font}
            </button>
        `;
    });

    btnHtml += `</div>`;

    $wrap.find("#font_buttons").html(btnHtml);

    // Live typing preview
    $wrap.find('input[data-fieldname="signature_text"]').on("input", function () {
        const text = $(this).val();
        $wrap.find("#signature_text_preview")
            .css("font-family", selectedFont)
            .text(text);
    });

    // Font selection
    $wrap.on("click", ".signature-font-btn", function () {
        selectedFont = $(this).data("font");

        $wrap.find(".signature-font-btn").removeClass("active");
        $(this).addClass("active");

        const text = $wrap.find('input[data-fieldname="signature_text"]').val();
        $wrap.find("#signature_text_preview")
            .css("font-family", selectedFont)
            .text(text);
    });
}


function generate_signature_image(text, font, dialog) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    canvas.width = 600;
    canvas.height = 150;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#000";
    ctx.font = `48px ${font}`;
    ctx.textBaseline = "middle";
    ctx.fillText(text, 20, canvas.height / 2);

    const base64_img = canvas.toDataURL("image/png");

    frappe.call({
        method: "verp_staffing.crm.api.upload.upload_file",
        args: {
            filename: "signature.png",
            filedata: base64_img
        },
        callback: function (r) {
            if (r.message && r.message.success) {
                frappe.msgprint("Signature uploaded successfully.");
                dialog.hide();

                frappe.web_form.set_df_property("signature_method", "read_only", 1);

                frappe.web_form.set_value(
                    "signature_image",
                    r.message.file_name
                );

                frappe.web_form.set_value(
                    "signature_custom_html",
                    `<img src="${r.message.file_url}" 
                              style="max-width:200px; margin-top:10px;">`
                );
            }
        }
    });
}


function show_upload_button() {
    let html = `
        <button class="btn btn-primary" id="open_signature_upload">
            Upload Image
        </button>
        <p style="color:red; font-size:12px; margin-top:5px;">* Image Upload is compulsory</p>
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
                options: `
                        <input type="file" accept="image/*" id="signature_file_input">
                        <div style="margin-top:6px; font-size:12px; color:#cc0000;">
                            Max file size allowed: <b>1 MB</b>. Larger files will be rejected.
                        </div>
                        `
            },
            {
                label: "Preview",
                fieldname: "preview",
                fieldtype: "HTML",
                options: `<div id="signature_preview" 
                            style="margin-top:10px; text-align:center;">
                          </div>
                          <p id="upload_notice"
                   style="
                        margin-top:15px;
                        font-size:13px;
                        color:#cc0000;
                        background:#ffe6e6;
                        padding:10px;
                        border-left: 3px solid #cc0000;
                        border-radius: 4px;
                   ">
                    <b>Note:</b> You may change your <span style="font-weight: 700;">signature</span> <u>only in this upload window</u>.
                            Once uploaded, the <span style="font-weight: 700;">signature</span> cannot be changed again.
                </p>`
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

        if (selected_image.size > MAX_PDF_SIZE) {
            frappe.msgprint({
                title: "File Too Large",
                message: "Image size must not exceed 1 MB.",
                indicator: "red"
            });
            selected_image = null;
            $("#signature_file_input").val("");
            return;
        }


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
                    frappe.web_form.set_value("signature_image", r.message.file_name);
                    frappe.web_form.set_df_property("signature_method", "read_only", 1);

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
    "driving_licence": "Driving Licence",
    "old_resume": "Old Resume"
};

function render_file_upload_buttons() {
    let html = `
    <div id="visa_copy_container" style="margin-bottom: 15px;">
        <button class="btn btn-primary file-btn" data-field="visa_copy">Upload Visa Copy</button>
        <p style="color:red; font-size:12px; margin-top:5px;">* Visa Copy is compulsory</p>
    </div>

    <div id="ead_card_container" style="margin-bottom: 15px;">
        <button class="btn btn-primary file-btn" data-field="ead_card">Upload EAD Card</button>
        <p style="color:red; font-size:12px; margin-top:5px;">* EAD Card is compulsory</p>
    </div>

    <div id="driving_licence_container" style="margin-top:10px;">
        <button class="btn btn-primary file-btn" data-field="driving_licence">Upload Driving Licence</button>
    </div>

    <div id="old_resume_container" style="margin-top:10px;">
        <button class="btn btn-primary file-btn" data-field="old_resume">Upload Old Resume</button>
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
                options: `
                            <input type="file" accept="application/pdf" id="${input_id}">
                            <div style="margin-top:6px; font-size:12px; color:#cc0000;">
                                Max file size allowed: <b>1 MB</b>. Larger files will be rejected.
                            </div>
                        `
            },
            {
                label: "Preview",
                fieldname: "preview",
                fieldtype: "HTML",
                options: `<div id="pdf_preview_area" style="margin-top:10px; color:#666;">
                    No file selected
                </div>
                
                <!-- IMPORTANT NOTICE -->
                <p id="upload_notice"
                   style="
                        margin-top:15px;
                        font-size:13px;
                        color:#cc0000;
                        background:#ffe6e6;
                        padding:10px;
                        border-left: 3px solid #cc0000;
                        border-radius: 4px;
                   ">
                    <b>Note:</b> You may change your <span style="font-weight: 700;">${label_map[target_field]}</span> <u>only in this upload window</u>.
                            Once uploaded, the <span style="font-weight: 700;">${label_map[target_field]}</span> cannot be changed again.
                </p>`
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

    function reset_selection() {
        selected_file = null;
        $wrap.find(`#${input_id}`).val("");
        $wrap.find("#pdf_preview_area").html("No file selected");
    }

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
            reset_selection();
            return;
        }

        if (selected_file.size > MAX_PDF_SIZE) {
            frappe.msgprint({
                title: "File Too Large",
                message: "PDF size must not exceed 1 MB.",
                indicator: "red"
            });
            reset_selection();
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
        reset_selection();
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

// Show Uploaded File Below Buttons
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

// Disable/Enable the NEXT button dynamically
function controlNextButton() {
    let nextBtn = document.querySelector('.btn-next');
    if (!nextBtn) return;

    let c1 = frappe.web_form.get_value("my_electronic_signature_has_same_effect_as_handwritten");
    let c2 = frappe.web_form.get_value("i_consent_to_receive_sign_and_store_documents_electronically");
    let c3 = frappe.web_form.get_value("i_confirm_my_identity_and_signing_this_document_intentionally");

    if (c1 && c2 && c3) {
        nextBtn.disabled = false;
        nextBtn.classList.remove("btn-disabled");
    } else {
        nextBtn.disabled = true;
        nextBtn.classList.add("btn-disabled");
    }
}


// Attach listener to checkboxes
function attachCheckboxListeners() {

    const nextButtonFields = [
        "my_electronic_signature_has_same_effect_as_handwritten",
        "i_consent_to_receive_sign_and_store_documents_electronically",
        "i_confirm_my_identity_and_signing_this_document_intentionally"
    ];

    nextButtonFields.forEach(fieldname => {
        let input = document.querySelector(`[data-fieldname="${fieldname}"] input`);
        if (!input) return;

        input.addEventListener("change", () => {
            controlNextButton(); // Re-run validator when user checks/unchecks
        });
    });
}


function controlSubmitButton() {
    let submitBtn = document.querySelector('.submit-btn');
    if (!submitBtn) return;

    let visa_copy = frappe.web_form.get_value("visa_copy");
    let ead_card = frappe.web_form.get_value("ead_card");

    if (visa_copy && ead_card) {
        submitBtn.disabled = false;
        submitBtn.classList.remove("btn-disabled");
    } else {
        submitBtn.disabled = true;
        submitBtn.classList.add("btn-disabled");
    }
}