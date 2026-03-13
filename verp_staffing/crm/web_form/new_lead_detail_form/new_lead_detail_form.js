// Unique storage key per form
const AUDIT_KEY = "audit_trail_storage";
const AUTH_KEY = "auth_state";
// unique key for this webform
let storage_key = "webform_filled_lead_details_form";
// max file size
const MAX_PDF_SIZE = 1 * 1024 * 1024; // 1 MB in bytes

let REQUIRED_LEAD_DOCS_CONFIG = null;
let customerEmail = null;
let otpRequestInFlight = false;
let otpTimer = null;

const CONCERN_FIELDS = [
	{
		fieldname: "my_electronic_signature_has_same_effect_as_handwritten",
		label: "My electronic signature has same effect as handwritten.",
	},
	// {
	// 	fieldname: "i_consent_to_receive_sign_and_store_documents_electronically",
	// 	label: "I consent to receive, sign, and store documents electronically.",
	// },
	// {
	// 	fieldname: "i_confirm_my_identity_and_signing_this_document_intentionally",
	// 	label: "I confirm my identity and signing this document intentionally.",
	// },
];

frappe.ready(async function () {
	// Monkey-patch frappe.msgprint to intercept our signal
	const _orig_msgprint = frappe.msgprint.bind(frappe);
	frappe.msgprint = function (msg, title) {
		const text = typeof msg === "string" ? msg : msg?.message || "";
		if (text.includes("LEAD_UPDATED_SUCCESS")) {
			handle_form_success();
			return;
		}
		return _orig_msgprint(msg, title);
	};
	// Wait until Web Form UI loads
	fetch_server_fingerprint(function (fp) {
		add_audit_event("form", {
			event: "form_opened",
			ip: fp.ip,
			user_agent: fp.user_agent,
		});
	});

	disable_next_button();

	if (is_email_verified()) {
		enable_next_button();
	}

	// remove discard button
	document.querySelector(".discard-btn")?.remove();

	await initRequiredLeadDocsConfig();

	init_authentication_html();

	const auth = get_auth_state();
	apply_auth_ui(auth);

	if (auth && auth.state === "otp_sent" && auth.expires_at) {
		const remaining = Math.floor((auth.expires_at - Date.now()) / 1000);

		if (remaining > 0) {
			start_otp_timer(remaining);
		} else {
			set_auth_state("otp_expired");
		}
	}

	const fields_to_hide = [
		"agreement_link",
		"signature_image",
		"audit_trail",
		"customer",
		"visa_copy",
		"ead_card",
		"driving_licence",
		"old_resume",
		"certificate_id",
	];

	fields_to_hide.forEach((fieldname) => {
		frappe.web_form.set_df_property(fieldname, "hidden", 1);
	});

	// 1. Get PDF path from URL (?file=path/to.pdf)
	const urlParams = new URLSearchParams(window.location.search);

	// Supported key names
	const salesOrder = urlParams.get("so");
	const customerValue = urlParams.get("c");
	const agreementValue = urlParams.get("agr");
	const pdfValue = urlParams.get("p");
	customerEmail = urlParams.get("e");

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

	const candidateFields = await getCandidateFieldsFromSalesOrder(salesOrder);

	// wait until web form fully renders
	function waitForWebFormRender(callback) {
		const interval = setInterval(() => {
			if (
				frappe.web_form &&
				frappe.web_form.fields_dict &&
				Object.keys(frappe.web_form.fields_dict).length > 0
			) {
				clearInterval(interval);
				callback();
			}
		}, 100);
	}

	waitForWebFormRender(() => {
		applyCandidateFieldVisibility(candidateFields);
	});

	console.log("Candidate Fields:", candidateFields);

	function applyCandidateFieldVisibility(candidateFields) {
		const allowed = new Set(candidateFields);

		// const always_visible = [
		// 	"agreement_html",
		// 	"consent_and_electronic_signature_confirmation_section",
		// 	"files_custom_html",
		// ];

		let sectionMap = {};
		let currentSection = null;

		// build section → fields map dynamically
		frappe.web_form.fields.forEach((field) => {
			if (!field) return;

			if (field.fieldtype === "Section Break") {
				currentSection = field.fieldname;
				sectionMap[currentSection] = [];
			} else if (currentSection && field.fieldname) {
				sectionMap[currentSection].push(field.fieldname);
			}
		});

		// hide everything first
		frappe.web_form.fields.forEach((field) => {
			if (!field || !field.fieldname) return;

			const control = frappe.web_form.fields_dict[field.fieldname];
			if (!control) return;

			frappe.web_form.set_df_property(field.fieldname, "hidden", 1);
		});

		// show allowed fields
		const visibleFields = new Set();

		frappe.web_form.fields.forEach((field) => {
			if (!field || !field.fieldname) return;

			if (allowed.has(field.fieldname)) {
				const control = frappe.web_form.fields_dict[field.fieldname];
				if (!control) return;

				frappe.web_form.set_df_property(field.fieldname, "hidden", 0);
				visibleFields.add(field.fieldname);
			}
		});

		// determine which sections must be visible
		Object.keys(sectionMap).forEach((section) => {
			const fields = sectionMap[section];

			const hasVisibleField = fields.some((f) => visibleFields.has(f));

			if (hasVisibleField) {
				frappe.web_form.set_df_property(section, "hidden", 0);
			}
		});
	}

	if (pdfValue) {
		// fetch Agreement by Sales Order
		frappe.call({
			method: "verp_staffing.crm.api.pdf_to_image.pdf_to_images",
			args: {
				path: pdfValue,
			},
			callback: function (res) {
				if (!res.message || !res.message.length) {
					console.error("PDF to image conversion failed");
					return;
				}

				let html = "";

				res.message.forEach((img) => {
					html += `
                        <img 
                            src="${img}" 
                            style="width:100%; margin-bottom:20px; border:1px solid #ccc;"
                        >
                    `;
				});

				frappe.web_form.set_value("agreement_html", html);
			},
		});
	}

	frappe.web_form.on("signature_method", (field, value) => {
		if (value === "Upload") {
			show_upload_button();
		} else if (value === "Text") {
			show_text_button();
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

	function shouldValidate(fieldname, candidateFields) {
		return candidateFields.includes(fieldname);
	}

	// when submit button is clicked
	if (frappe.web_form) {
		frappe.web_form.validate = () => {
			if (!validate_concerns()) return false;
			if (!validateRequiredLeadDocuments()) return false;

			let signature_method = frappe.web_form.get_value("signature_method") || [];
			// if (!validate_signature(signature_method)) return false;

			if (shouldValidate("email", candidateFields)) {
				let email = frappe.web_form.get_value("email");
				if (!validate_email(email, "Email")) return false;
			}

			if (shouldValidate("personal_phone_number", candidateFields)) {
				let personal_phone = frappe.web_form.get_value("personal_phone_number");
				if (!validate_phone(personal_phone, "Personal Phone Number")) return false;
			}

			if (shouldValidate("entry_date", candidateFields)) {
				let entry_date = frappe.web_form.get_value("entry_date");
				if (!validate_entry_date(entry_date)) return false;
			}

			if (shouldValidate("ssn_digit", candidateFields)) {
				let ssn_digit = frappe.web_form.get_value("ssn_digit");
				if (!validate_ssn_digit(ssn_digit)) return false;
			}

			if (shouldValidate("educational_details", candidateFields)) {
				let lead_course = frappe.web_form.get_value("educational_details") || [];
				if (!validate_lead_course_table(lead_course)) return false;
			}

			if (shouldValidate("past_experience_table", candidateFields)) {
				let exp = frappe.web_form.get_value("past_experience_table") || [];
				if (!validate_past_experience_table(exp)) return false;
			}

			if (shouldValidate("address_history", candidateFields)) {
				let address_history = frappe.web_form.get_value("address_history") || [];
				if (!validate_address_history(address_history)) return false;
			}

			if (shouldValidate("number_for_marketing", candidateFields)) {
				let marketing_phone = frappe.web_form.get_value("number_for_marketing");
				if (!validate_phone(marketing_phone, "Marketing Phone Number")) return false;
			}

			return true;
		};

		// ✅ after_save handles normal first-time insert
		frappe.web_form.after_save = (doc) => {
			handle_form_success();
		};

		// ✅ Patch the submit button to also catch error responses
		setTimeout(() => {
			const submitBtn = document.querySelector(".btn-submit");
			if (submitBtn) {
				submitBtn.addEventListener("click", () => {
					// Wait for Frappe's own submit to finish, then check
					setTimeout(() => {
						// If localStorage already set, do nothing
						if (localStorage.getItem(storage_key) === "1") return;

						// Check if error alert appeared with our specific message
						const alerts = document.querySelectorAll(".modal-body, .msgprint");
						alerts.forEach((el) => {
							if (
								el.innerText &&
								el.innerText.includes("Record already exists. Updated instead.")
							) {
								// Close the error dialog
								document.querySelector(".btn-modal-close, .modal .close")?.click();
								handle_form_success();
							}
						});
					}, 2000);
				});
			}
		}, 1000);
	}

	frappe.web_form.on("signature", () => {
		fetch_server_fingerprint(function (fp) {
			add_audit_event("signature", {
				event: "signature_added",
				method: "Draw",
				ip: fp.ip,
				user_agent: fp.user_agent,
			});
		});
	});

	CONCERN_FIELDS.forEach(({ fieldname, label }) => {
		frappe.web_form.on(fieldname, (field, value) => {
			on_concern_checked(fieldname, label, value);
		});
	});
});

async function getCandidateFieldsFromSalesOrder(salesOrderName) {
	const r = await frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Sales Order",
			name: salesOrderName,
		},
	});

	const so = r.message;

	if (!so || !so.services) {
		return [];
	}

	// collect service names
	const serviceNames = so.services.map((row) => row.service).filter(Boolean);

	if (!serviceNames.length) {
		return [];
	}

	// fetch all services in one call
	const services = await frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Service",
			fields: ["name", "candidate_details_form_fields"],
			filters: {
				name: ["in", serviceNames],
			},
			limit_page_length: 100,
		},
	});

	let fields = [];

	services.message.forEach((service) => {
		if (service.candidate_details_form_fields) {
			fields.push(...service.candidate_details_form_fields.split(",").map((f) => f.trim()));
		}
	});

	// remove duplicates
	fields = [...new Set(fields)];

	return fields;
}

function handle_form_success() {
	if (localStorage.getItem(storage_key) === "1") return;

	localStorage.removeItem(AUDIT_KEY);
	localStorage.removeItem(AUTH_KEY);
	localStorage.setItem(storage_key, "1");

	$(".web-form-container").html(`
        <div style="
            padding: clamp(16px, 4vw, 24px);
            margin: 16px auto;
            background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
            border: 2px solid #48bb78;
            border-radius: 12px;
            text-align: center;
            max-width: 600px;
        ">
            <h3 style="color: #276749;">✅ Form Submitted Successfully!</h3>
            <p style="color: #2f855a;">Your details have been saved successfully.</p>
        </div>
    `);
}

function set_auth_state(state, extra = {}) {
	const auth = {
		state,
		updated_at: new Date().toISOString(),
		...extra,
	};

	localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
	apply_auth_ui(auth);
}

function get_auth_state() {
	try {
		return JSON.parse(localStorage.getItem(AUTH_KEY));
	} catch {
		return null;
	}
}

function apply_auth_ui(auth) {
	const sendBtn = document.getElementById("send-otp-btn");
	const otpSection = document.getElementById("otp-section");
	const otpInput = document.getElementById("otp-input");
	const verifyBtn = document.getElementById("verify-otp-btn");
	const statusBox = document.getElementById("otp-status");
	const timerBox = document.getElementById("otp-timer");

	if (!sendBtn || !otpSection) return;

	/* ---------------- HARD RESET ---------------- */
	sendBtn.style.display = "inline-block";
	sendBtn.disabled = false;

	otpSection.style.display = "none";
	otpInput.value = "";
	otpInput.disabled = false;

	verifyBtn.style.display = "none";

	timerBox.innerText = "";
	statusBox.innerText = "";
	statusBox.className = "";

	/* ---------------- IDLE ---------------- */
	if (!auth || auth.state === "idle") {
		sendBtn.innerText = "Send OTP";
		return;
	}

	/* ---------------- OTP SENT ---------------- */
	if (auth.state === "otp_sent") {
		sendBtn.disabled = true;
		sendBtn.innerText = "Send OTP";

		otpSection.style.display = "block";
		verifyBtn.style.display = "inline-block";

		statusBox.innerText = "OTP sent. Please verify.";
		return;
	}

	/* ---------------- OTP EXPIRED ---------------- */
	if (auth.state === "otp_expired") {
		sendBtn.disabled = false;
		sendBtn.innerText = "Resend OTP";

		statusBox.innerText = "OTP expired. Please resend.";
		statusBox.classList.add("text-warning");

		return;
	}

	/* ---------------- VERIFIED ---------------- */
	if (auth.state === "verified") {
		const headerDiv = document.getElementById("otp-header");
		if (headerDiv) headerDiv.style.display = "none";

		sendBtn.style.display = "none";
		otpSection.style.display = "block";
		verifyBtn.style.display = "none";

		otpInput.disabled = true;
		otpInput.style.display = "none";

		statusBox.innerText = "Email verified successfully.";
		statusBox.classList.add("text-success");
		return;
	}
}

function start_otp_timer(seconds) {
	clearInterval(otpTimer);

	const expiresAt = Date.now() + seconds * 1000;

	otpTimer = setInterval(() => {
		const remaining = Math.floor((expiresAt - Date.now()) / 1000);

		if (remaining <= 0) {
			clearInterval(otpTimer);

			set_auth_state("otp_expired");
			add_audit_event("authentication", { event: "otp_expired" });

			return;
		}

		update_timer_ui(remaining);
	}, 1000);
}

function update_timer_ui(seconds) {
	const min = Math.floor(seconds / 60);
	const sec = seconds % 60;

	document.getElementById("otp-timer").innerText =
		`Resend OTP in ${min}:${sec.toString().padStart(2, "0")}`;
}

/* ---------------- OTP ACTIONS ---------------- */

function send_otp() {
	if (otpRequestInFlight) return; // HARD LOCK

	const sendBtn = document.getElementById("send-otp-btn");
	const customer = frappe.web_form.get_value("customer");
	const email = customerEmail;

	if (!email) {
		frappe.msgprint("Email is required");
		return;
	}

	// 🔒 LOCK IMMEDIATELY
	otpRequestInFlight = true;
	sendBtn.disabled = true;
	sendBtn.innerText = "Sending OTP...";

	frappe.call({
		method: "verp_staffing.crm.doctype.lead_detail_form.lead_detail_form.send_otp",
		args: { customer, email },
		callback(r) {
			set_auth_state("otp_sent", {
				expires_at: Date.now() + 300000,
			});
			start_otp_timer(300);

			add_audit_event("authentication", {
				event: "otp_sent",
			});
		},
		error() {
			// 🔓 UNLOCK ONLY ON FAILURE
			otpRequestInFlight = false;
			sendBtn.disabled = false;
			sendBtn.innerText = "Send OTP";

			frappe.msgprint("Failed to send OTP. Please try again.");
		},
		always() {
			// keep lock if success
			if (get_auth_state()?.state !== "otp_sent") {
				otpRequestInFlight = false;
			}
		},
	});
}

function verify_otp() {
	const otp = document.getElementById("otp-input").value;
	const customer = frappe.web_form.get_value("customer");

	if (!otp || otp.length !== 6) {
		frappe.msgprint("Enter valid 6 digit OTP");
		return;
	}

	frappe.call({
		method: "verp_staffing.crm.doctype.lead_detail_form.lead_detail_form.verify_otp",
		args: { customer, otp },
		callback(r) {
			clearInterval(otpTimer);
			set_auth_state("verified");

			add_audit_event("authentication", {
				event: "otp_verified",
				ip: r.message.ip || null,
				user_agent: r.message.user_agent || null,
			});

			enable_next_button();

			frappe.msgprint("Email verified successfully");
		},
	});
}

function init_authentication_html() {
	const html = `
    <div id="otp-box" style="border:2px solid #e0e0e0;padding:24px;border-radius:12px;background:#ffffff;max-width:400px;margin:0 auto;box-shadow:0 2px 8px rgba(0,0,0,0.1)">
        <p style="margin:0 0 8px 0;font-weight:600;font-size:18px;color:#333">
            Email Verification
        </p>
        <div id="otp-header">
        <p style="margin:0 0 20px 0;font-size:14px;color:#666;line-height:1.5">
            We'll send a verification code to your email address
        </p>
        <button type="button" id="send-otp-btn" style="background:#007bff;color:#fff;border:none;padding:14px 24px;border-radius:6px;font-size:14px;font-weight:500;cursor:pointer;width:100%;transition:background 0.3s;height:48px">
            Send OTP
        </button>
        <div id="otp-section" style="display:none;margin-top:20px;padding-top:20px;border-top:1px solid #e0e0e0">
            <p style="margin:0 0 12px 0;font-size:14px;color:#333;font-weight:500">
                Enter the 6-digit code sent to your email
            </p>
            <input
                type="text"
                id="otp-input"
                placeholder="000000"
                maxlength="6"
                style="padding:14px 24px;border:2px solid #ddd;border-radius:6px;font-size:18px;width:calc(100% - 52px);margin-bottom:12px;text-align:center;letter-spacing:8px;font-weight:600;height:48px;box-sizing:border-box"
            />
            <button type="button" id="verify-otp-btn" style="background:#28a745;color:#fff;border:none;padding:14px 24px;border-radius:6px;font-size:14px;font-weight:500;cursor:pointer;width:100%;margin-bottom:16px;transition:background 0.3s;height:48px">
                Verify OTP
            </button>
            <p id="otp-timer" style="margin:0 0 10px 0;font-size:13px;color:#666;text-align:center"></p>
        </div>
        </div>
        <p id="otp-status" style="margin:16px 0 0 0;font-size:14px;text-align:center;padding-top:16px"></p>
    </div>
    <style>
        #send-otp-btn:disabled {
            background:#6c757d !important;
            cursor:not-allowed !important;
            opacity:0.6;
        }
        #verify-otp-btn:disabled {
            background:#6c757d !important;
            cursor:not-allowed !important;
            opacity:0.6;
        }
        #otp-input:disabled {
            background:#f5f5f5;
            cursor:not-allowed;
            opacity:0.6;
        }
        #send-otp-btn:not(:disabled):hover {
            background:#0056b3;
        }
        #verify-otp-btn:not(:disabled):hover {
            background:#218838;
        }
    </style>
`;

	frappe.web_form.set_value("authentication_html", html);

	// 🔥 THIS IS WHAT YOU WERE MISSING
	setTimeout(bind_auth_events, 0);
}

function bind_auth_events() {
	const sendBtn = document.getElementById("send-otp-btn");
	const verifyBtn = document.getElementById("verify-otp-btn");

	if (sendBtn) {
		sendBtn.addEventListener("click", send_otp);
	}

	if (verifyBtn) {
		verifyBtn.addEventListener("click", verify_otp);
	}
}

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
	if (!phone) {
		frappe.msgprint(`${label} is required`);
		return false;
	}

	phone = phone.trim();

	const phone_regex = /^[+]\d{10,15}$/;

	if (!phone_regex.test(phone)) {
		frappe.msgprint(`${label} must be in format +countrycode followed by numbers`);
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
			frappe.msgprint(
				`In Past Experience Table, Row ${idx + 1}:<br>Start Date must be MM-YYYY`,
			);
			return false;
		}

		if (!row.is_currently_working) {
			if (!row.end_date) {
				frappe.msgprint(
					`In Past Experience Table, Row ${idx + 1}:<br>End Date is required.`,
				);
				return false;
			}
			if (row.end_date && !is_valid_mm_yyyy(row.end_date)) {
				frappe.msgprint(
					`In Past Experience Table, Row ${idx + 1}:<br>End Date must be MM-YYYY`,
				);
				return false;
			}
		}

		if (row.description) {
			const desc = row.description.replace(/\s/g, "");
			if (desc.length < 800) {
				frappe.msgprint(
					`In Past Experience Table, Row ${idx + 1}:<br>Description must contain at least 800 characters`,
				);
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
			frappe.msgprint(
				`In Education Details Table, Row ${idx + 1}:<br>Start Date must be MM-YYYY`,
			);
			return false;
		}

		if (row.end_date && !is_valid_mm_yyyy(row.end_date)) {
			frappe.msgprint(
				`In Education Details Table, Row ${idx + 1}:<br>End Date must be MM-YYYY`,
			);
			return false;
		}

		let grade = Number(row.grade);
		if (row.grade && !(grade >= 0 && grade <= 10)) {
			frappe.msgprint(
				`In Education Details Table, Row ${idx + 1}:<br>Grade must be between 0 and 10.`,
			);
			return false;
		}
	}
	return true;
}

function validate_address_history(table) {
	for (let idx = 0; idx < table.length; idx++) {
		let row = table[idx];

		if (row.from_date && !is_valid_mm_yyyy(row.from_date)) {
			frappe.msgprint(
				`In Address History Table, Row ${idx + 1}:<br>From Date must be MM-YYYY`,
			);
			return false;
		}

		if (row.to_date && !is_valid_mm_yyyy(row.to_date)) {
			frappe.msgprint(
				`In Address History Table, Row ${idx + 1}:<br>To Date must be MM-YYYY`,
			);
			return false;
		}
	}
	return true;
}

function validate_entry_date(value) {
	if (value && !is_valid_mm_yyyy(value)) {
		frappe.msgprint("Entry Date Into USA/Canada must be in MM-YYYY format.");
		return false;
	}
	return true;
}

function validate_ssn_digit(value) {
	if (value && String(value).length !== 4) {
		frappe.msgprint("SSN must contain only last 4 digits.");
		return false;
	}
	return true;
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
	let audit = {};

	try {
		audit = JSON.parse(localStorage.getItem(AUDIT_KEY)) || {};
	} catch {
		audit = {};
	}

	// 🔒 HARD NORMALIZATION (NO ASSUMPTIONS)
	if (!Array.isArray(audit["form visit logs"])) {
		audit["form visit logs"] = [];
	}

	if (!Array.isArray(audit["signature update logs"])) {
		audit["signature update logs"] = [];
	}

	if (!Array.isArray(audit["authentication logs"])) {
		audit["authentication logs"] = [];
	}

	if (!Array.isArray(audit["concern accepted"])) {
		audit["concern accepted"] = [];
	}

	return audit;
}

function save_audit_trail(audit) {
	localStorage.setItem(AUDIT_KEY, JSON.stringify(audit));
}

// Unified reusable function for adding event logs
function add_audit_event(type, data = {}) {
	const audit = load_audit_trail();

	const entry = {
		event: data.event || null,
		timestamp: format_timestamp_utc(),
		...data,
	};

	if (type === "form") {
		audit["form visit logs"].push(entry);
	}

	if (type === "signature") {
		audit["signature update logs"].push(entry);
	}

	if (type === "authentication") {
		audit["authentication logs"].push(entry);
	}

	if (type === "concern") {
		audit["concern accepted"].push(entry);
	}

	save_audit_trail(audit);
	frappe.web_form.set_value("audit_trail", JSON.stringify(audit));
}

function fetch_server_fingerprint(callback) {
	frappe.call({
		method: "verp_staffing.crm.doctype.lead_detail_form.lead_detail_form.get_ip_and_device",
		callback: function (r) {
			if (r.message) {
				callback(r.message);
			}
		},
	});
}

function on_concern_checked(fieldname, label, newValue) {
	if (newValue === 1) {
		// only false -> true

		fetch_server_fingerprint(function (fp) {
			add_audit_event("concern", {
				event: "concern accepted",
				fieldname: fieldname,
				label: label,
				accepted: true,
				ip_address: fp.ip,
				user_agent: fp.user_agent,
			});
		});
	}
}

function format_timestamp_utc() {
	const d = new Date();

	const day = String(d.getUTCDate()).padStart(2, "0");
	const month = String(d.getUTCMonth() + 1).padStart(2, "0");
	const year = d.getUTCFullYear();

	const hours = String(d.getUTCHours()).padStart(2, "0");
	const minutes = String(d.getUTCMinutes()).padStart(2, "0");
	const seconds = String(d.getUTCSeconds()).padStart(2, "0");

	return `${day}-${month}-${year}, ${hours}:${minutes}:${seconds} UTC`;
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
		"Sacramento", // ⭐ most natural handwritten signature
		"Mr Dafoe", // bold, marker-style signature
		"Yellowtail", // smooth cursive signature
		"Marck Script", // clean handwritten look
		"Alex Brush", // elegant but still signature-like
	];

	let selectedFont = fonts[0];

	let d = new frappe.ui.Dialog({
		title: "Create Text Signature",
		fields: [
			{
				label: "Your Name",
				fieldname: "signature_text",
				fieldtype: "Data",
				reqd: 1,
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
                `,
			},
		],
		primary_action_label: "Upload Signature",
		primary_action(values) {
			if (!values.signature_text) {
				frappe.msgprint("Please enter your name.");
				return;
			}

			generate_signature_image(values.signature_text, selectedFont, d);
		},
	});

	d.show();

	const $wrap = d.wrapper;

	const rotate = (Math.random() * 1.5 - 0.75).toFixed(2);

	$wrap.find("#signature_text_preview").css("transform", `rotate(${rotate}deg)`);

	// Inject clean CSS once
	if (!document.getElementById("signature-style")) {
		$(
			"<style id='signature-style'>\
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
        </style>",
		).appendTo("head");
	}

	// Render font buttons
	let btnHtml = `<div class="signature-font-grid">`;

	fonts.forEach((font) => {
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
		$wrap.find("#signature_text_preview").css("font-family", selectedFont).text(text);
	});

	// Font selection
	$wrap.on("click", ".signature-font-btn", function () {
		selectedFont = $(this).data("font");

		$wrap.find(".signature-font-btn").removeClass("active");
		$(this).addClass("active");

		const text = $wrap.find('input[data-fieldname="signature_text"]').val();
		$wrap.find("#signature_text_preview").css("font-family", selectedFont).text(text);
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
			filedata: base64_img,
		},
		callback: function (r) {
			if (r.message && r.message.success) {
				fetch_server_fingerprint(function (fp) {
					add_audit_event("signature", {
						event: "signature_added",
						method: "Text",
						ip: fp.ip,
						user_agent: fp.user_agent,
					});
				});

				frappe.msgprint("Signature uploaded successfully.");
				dialog.hide();

				frappe.web_form.set_df_property("signature_method", "read_only", 1);

				frappe.web_form.set_value("signature_image", r.message.file_name);

				frappe.web_form.set_value(
					"signature_custom_html",
					`<img src="${r.message.file_url}" 
                              style="max-width:200px; margin-top:10px;">`,
				);
			}
		},
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
                        `,
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
                </p>`,
			},
		],
		primary_action_label: "Upload",
		primary_action(values) {
			if (!selected_image) {
				frappe.msgprint("Please select an image.");
				return;
			}
			upload_signature_file(selected_image, d);
		},
	});

	d.show();

	// file input listener
	$(document).on("change", "#signature_file_input", function (e) {
		selected_image = e.target.files[0];

		if (selected_image.size > MAX_PDF_SIZE) {
			frappe.msgprint({
				title: "File Too Large",
				message: "Image size must not exceed 1 MB.",
				indicator: "red",
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
				filedata: base64_img,
			},
			callback: function (r) {
				if (r.message && r.message.success) {
					fetch_server_fingerprint(function (fp) {
						add_audit_event("signature", {
							event: "signature_added",
							method: "Upload",
							ip: fp.ip,
							user_agent: fp.user_agent,
						});
					});

					frappe.msgprint("Image Uploaded Successfully!");
					dialog.hide();
					frappe.web_form.set_value("signature_image", r.message.file_name);
					frappe.web_form.set_df_property("signature_method", "read_only", 1);

					// Set image in HTML field
					frappe.web_form.set_value(
						"signature_custom_html",
						`<img src="${r.message.file_url}" 
                              style="max-width:200px; margin-top:10px;">`,
					);
				}
			},
		});
	};

	reader.readAsDataURL(file);
}

let label_map = {
	visa_copy: "Visa Copy",
	ead_card: "EAD Card",
	driving_licence: "Driving Licence",
	old_resume: "Old Resume",
};

async function initRequiredLeadDocsConfig() {
	const r = await frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "ERP Configuration",
			name: "ERP Configuration",
		},
	});

	const doc = r.message || {};

	REQUIRED_LEAD_DOCS_CONFIG = {
		driving_licence: doc.driving_licence || 0,
		ead_card: doc.ead_card || 0,
		old_resume: doc.old_resume || 0,
		visa_copy: doc.visa_copy || 0,
	};
}

function validate_concerns() {
	for (let concern of CONCERN_FIELDS) {
		const value = frappe.web_form.get_value(concern.fieldname);

		if (value !== 1) {
			frappe.msgprint({
				title: "Consent Required",
				message: `Please accept: <b>${concern.label}</b>`,
				indicator: "red",
			});
			return false;
		}
	}
	return true;
}

function validateRequiredLeadDocuments() {
	if (!REQUIRED_LEAD_DOCS_CONFIG) {
		frappe.msgprint({
			title: "Configuration Error",
			message: "ERP Configuration is not loaded. Please contact support.",
			indicator: "red",
		});
		return false; // nothing to validate
	}

	let missing = [];

	Object.entries(REQUIRED_LEAD_DOCS_CONFIG).forEach(([fieldname, is_required]) => {
		if (is_required === 1) {
			const value = frappe.web_form.get_value(fieldname);
			if (!value) {
				missing.push(fieldname);
			}
		}
	});

	if (missing.length) {
		frappe.msgprint({
			title: "Missing Required Documents",
			message: "Please upload required documents:<br><b>" + missing.join("<br>") + "</b>",
			indicator: "red",
		});
		return false;
	}

	return true;
}

async function render_file_upload_buttons() {
	let html = "";

	Object.entries(REQUIRED_LEAD_DOCS_CONFIG).forEach(([fieldname, is_required]) => {
		const label = label_map[fieldname] || fieldname;

		html += `
          <div id="${fieldname}_container" style="margin-bottom:15px;">
            <button class="btn btn-primary file-btn" data-field="${fieldname}">
              Upload ${label}
            </button>
            ${
				is_required
					? `<p style="color:red;font-size:12px;margin-top:5px;">
                    * ${label} is compulsory
                  </p>`
					: ""
			}
          </div>
        `;
	});

	frappe.web_form.set_value("files_custom_html", html);

	setTimeout(() => {
		$(".file-btn").on("click", function () {
			open_file_upload_dialog($(this).data("field"));
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
                        `,
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
                </p>`,
			},
		],
		primary_action_label: "Upload",
		primary_action(values) {
			if (!selected_file) {
				frappe.msgprint("Please select a PDF file.");
				return;
			}
			// call upload routine
			upload_pdf_file(selected_file, target_field, d);
		},
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
				indicator: "red",
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
				filedata: base64_pdf,
			},
			callback: function (r) {
				if (r.message && r.message.success) {
					dialog.hide();

					// Set File Name into Link Field
					frappe.web_form.set_value(target_field, r.message.file_name);

					// Show preview list below buttons
					add_file_preview(target_field, r.message.file_url, r.message.file_name);
				} else {
					frappe.msgprint(
						"Upload failed: " +
							(r.message && r.message.error ? r.message.error : "Unknown error"),
					);
				}
			},
			error: function (err) {
				frappe.msgprint("Upload failed. See console for details.");
				console.error(err);
			},
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

// disable next button
function disable_next_button() {
	const nextBtn = document.querySelector(".btn-next");
	if (!nextBtn) return;

	nextBtn.disabled = true;
	nextBtn.classList.add("btn-disabled");
}

// enable next button
function enable_next_button() {
	const nextBtn = document.querySelector(".btn-next");
	if (!nextBtn) return;

	nextBtn.disabled = false;
	nextBtn.classList.remove("btn-disabled");
}

function is_email_verified() {
	try {
		const raw = localStorage.getItem("auth_state");
		if (!raw) return false;

		const state = JSON.parse(raw);
		return state.state === "verified";
	} catch {
		return false;
	}
}
