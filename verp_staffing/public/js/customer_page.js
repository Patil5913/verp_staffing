let _otp_state = "idle";
let _timer_iv = null;
let _events_bound = false;

let token = null;
let customerEmail = null;

function escape_html(str) {
	return String(str == null ? "" : str)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}

function get_status_badge_style(status) {
	var s = (status || "").toLowerCase();
	var rules = [
		["rescheduled", "background:#ffedd5;color:#9a3412;"], // orange
		["scheduled", "background:#cffafe;color:#155e75;"], // cyan
		["today", "background:#fef9c3;color:#854d0e;"], // yellow
		["completed", "background:#dbeafe;color:#1e40af;"], // blue
		["cancelled", "background:#e2e8f0;color:#334155;"], // gray
		["get the offer", "background:#dcfce7;color:#166534;"], // green
		["accepted", "background:#dcfce7;color:#166534;"], // green (same as get the offer)
		["rejected", "background:#fee2e2;color:#991b1b;"], // red
	];

	for (var i = 0; i < rules.length; i++) {
		if (s.indexOf(rules[i][0]) !== -1) return rules[i][1];
	}
	return "background:#f1f5f9;color:#475569;";
}

function render_status_badge(status) {
	var style = get_status_badge_style(status);
	var text = status || "-";
	return '<span class="status-badge" style="' + style + '">' + escape_html(text) + "</span>";
}

// ============================================================
// LEAD DOCUMENTS (EAD Card, Driving Licence, Old Resume, Visa Copy)
// ============================================================
//
// 5 MB check here mirrors MAX_UPLOAD_SIZE_BYTES in customer.py —
// this is just the fast-fail UX path; the backend re-checks and does
// not trust this.
var LEAD_DOCUMENT_MAX_BYTES = 5 * 1024 * 1024;

document.addEventListener("click", function (e) {
	if (!e.target.classList || !e.target.classList.contains("lead-document-update-btn")) {
		return;
	}
	var row = e.target.closest(".lead-document-row");
	if (!row) return;
	var fileInput = row.querySelector(".lead-document-file-input");
	if (fileInput) fileInput.click();
});

function extract_frappe_error(data) {
	if (!data) return null;
	if (data._server_messages) {
		try {
			var msgs = JSON.parse(data._server_messages);
			var first = JSON.parse(msgs[0]);
			return first.message;
		} catch (e) {
			/* fall through */
		}
	}
	return data.exception || data.message || null;
}

document.addEventListener("change", function (e) {
	if (!e.target.classList || !e.target.classList.contains("lead-document-file-input")) {
		return;
	}

	var input = e.target;
	var file = input.files && input.files[0];
	if (!file) return;

	if (file.size > LEAD_DOCUMENT_MAX_BYTES) {
		alert("File size must be under 1 MB.");
		input.value = "";
		return;
	}

	var row = input.closest(".lead-document-row");
	var field = row.dataset.field;
	var updateBtn = row.querySelector(".lead-document-update-btn");
	var t = new URLSearchParams(window.location.search).get("t");
	var csrfToken = document.querySelector('[name="csrf_token"]');

	var formData = new FormData();
	formData.append("file", file);
	formData.append("token", t);
	formData.append("field", field);

	updateBtn.disabled = true;
	var originalLabel = updateBtn.textContent;
	updateBtn.textContent = "Uploading…";

	fetch("/api/method/verp_staffing.www.customer.upload_lead_document", {
		method: "POST",
		headers: csrfToken ? { "X-Frappe-CSRF-Token": csrfToken.value } : {},
		body: formData,
	})
		.then(function (res) {
			return res.json().then(function (data) {
				return { ok: res.ok, data: data };
			});
		})
		.then(function (result) {
			updateBtn.disabled = false;
			input.value = "";

			if (result.ok && result.data.message && result.data.message.status === "success") {
				updateBtn.textContent = "Update";
			} else {
				updateBtn.textContent = originalLabel;
				var errMsg = extract_frappe_error(result.data);
				alert(errMsg || "Upload failed. Please try again.");
			}
		})
		.catch(function (err) {
			console.error("Lead document upload error:", err);
			updateBtn.disabled = false;
			updateBtn.textContent = originalLabel;
			input.value = "";
			alert("Something went wrong");
		});
});

document.addEventListener("DOMContentLoaded", function () {
	start_otp_bootstrap();
});

async function start_otp_bootstrap() {
	const root = await wait_for_root("#otp-root", 3000);

	if (!root) return;

	token = new URLSearchParams(window.location.search).get("t");

	// ✅ otherwise load OTP UI
	customerEmail = decode_token_email(token);
	init_otp_ui(token);
}

function decode_token_email(token) {
	if (!token) return null;

	try {
		const decoded = safe_atob(token);
		const parts = decoded.split("|");

		if (parts.length < 1) return null;

		return parts[0]; // email
	} catch (e) {
		console.error("Token decode failed:", e);
		return null;
	}
}

function safe_atob(base64) {
	// fix url-safe base64 + padding
	base64 = base64.replace(/-/g, "+").replace(/_/g, "/");

	while (base64.length % 4) {
		base64 += "=";
	}

	return atob(base64);
}

function wait_for_root(selector, timeout = 3000) {
	return new Promise((resolve) => {
		let elapsed = 0;

		const iv = setInterval(() => {
			const el = document.querySelector(selector);

			if (el) {
				clearInterval(iv);
				resolve(el);
			}

			elapsed += 100;

			if (elapsed >= timeout) {
				clearInterval(iv);
				resolve(null);
			}
		}, 100);
	});
}

document.addEventListener("click", async function (e) {
	if (e.target && e.target.id === "logout-btn") {
		await handle_logout();
	}
});

async function handle_logout() {
	const t = new URLSearchParams(window.location.search).get("t");
	if (t) {
		sessionStorage.removeItem("customer_verification_key_" + t);
	}

	try {
		await api_call("verp_staffing.utils.customer_page.logout_otp_web", {
			token: t,
		});
		location.reload();
	} catch (e) {
		console.error("Logout failed", e);
	}
}

function init_otp_ui() {
	inject_otp_html();

	bind_otp_events();
	restore_otp_state();
}

function inject_otp_html() {
	const root = document.getElementById("otp-root");

	if (!root) {
		console.error("[OTP] #otp-root not found");
		return;
	}

	root.innerHTML = build_otp_html();
}

function poll_until(predicate, maxMs, errorMsg) {
	return new Promise(function (resolve) {
		if (predicate()) {
			resolve();
			return;
		}
		const deadline = Date.now() + (maxMs || 5000);
		const iv = setInterval(function () {
			if (predicate()) {
				clearInterval(iv);
				resolve();
			} else if (Date.now() >= deadline) {
				clearInterval(iv);
				if (errorMsg) console.error(errorMsg);
				resolve(); // resolve anyway — never block the pipeline
			}
		}, 50);
	});
}

function bind_otp_events() {
	if (_events_bound) return;
	_events_bound = true;

	const box = document.getElementById("otp-box");
	if (!box) {
		console.error("[OTP] #otp-box not found at bind time");
		return;
	}

	// Single delegated listener — survives any child re-renders
	box.addEventListener("click", function (e) {
		const id = e.target && e.target.id;
		if (id === "send-otp-btn") handle_send_otp();
		else if (id === "verify-otp-btn") handle_verify_otp();
	});

	box.addEventListener("keydown", function (e) {
		if (e.target && e.target.id === "otp-input" && e.key === "Enter") {
			handle_verify_otp();
		}
	});

	box.addEventListener("input", function (e) {
		if (e.target && e.target.id === "otp-input") {
			e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6);
		}
	});
}

async function api_call(method, args = {}) {
	const url = new URL("/api/method/" + method, window.location.origin);

	// attach params
	Object.keys(args).forEach((key) => {
		if (args[key] !== undefined && args[key] !== null) {
			url.searchParams.append(key, args[key]);
		}
	});

	let res, json;

	try {
		res = await fetch(url, {
			method: "GET",
			credentials: "include",
		});

		json = await res.json();
	} catch (e) {
		console.error("[API NETWORK ERROR]", method, e);
		return null;
	}

	if (!res.ok || json.exc) {
		console.error("[API ERROR]", method, json?.exc || res.statusText);
		return {
			_error: true,
			message: json?._server_messages
				? JSON.parse(json._server_messages)[0]
				: json?.exc || res.statusText,
		};
	}

	return json.message;
}

async function restore_otp_state() {
	const currentToken = token || new URLSearchParams(window.location.search).get("t") || "";
	const storedKey = sessionStorage.getItem("customer_verification_key_" + currentToken) || "";
	const res = await fetch(
		"/api/method/verp_staffing.utils.customer_page.get_otp_status_web?token=" +
			encodeURIComponent(currentToken) +
			"&verification_key=" +
			encodeURIComponent(storedKey),
		{
			method: "GET",
			credentials: "include",
		},
	);

	const data = await res.json();

	if (!data) {
		apply_state("idle");
		return;
	}

	const payload = data?.message || {};

	const state = payload.state;
	const expiresIn = parseInt(payload.expires_in, 10) || 0;

	if (state === "verified") {
		apply_state("verified");
	} else {
		if (storedKey) {
			sessionStorage.removeItem("customer_verification_key_" + currentToken);
		}
		if (state === "otp_sent") {
			if (expiresIn > 5) {
				apply_state("otp_sent", {
					seconds: expiresIn,
					message: "📬 OTP already sent. Check your inbox.",
					msgColor: "#007bff",
				});
			} else if (expiresIn === 0) {
				apply_state("otp_sent", {
					seconds: null, // null = skip timer entirely
					message: "📬 OTP already sent. Enter the code below.",
					msgColor: "#007bff",
				});
			} else {
				// expiresIn is 1–5 s: about to expire; show expired immediately
				apply_state("expired");
			}
		} else {
			apply_state("idle");
		}
	}
}

async function handle_send_otp() {
	const currentToken = token || new URLSearchParams(window.location.search).get("t") || "";
	// Block re-entry
	if (_otp_state === "otp_sent" || _otp_state === "sending" || _otp_state === "verified") return;

	if (!customerEmail) {
		set_status("⚠️ Unable to find your email address.", "orange");
		return;
	}

	apply_state("sending");

	const data = await api_call("verp_staffing.utils.customer_page.send_otp_web", {
		token: currentToken,
		email: customerEmail,
	});

	if (!data || data._error) {
		apply_state("idle");
		set_status("Failed to send OTP. Please try again.", "red");
		return;
	}

	let expiresIn = parseInt(data.expires_in, 10);
	if (!(expiresIn > 0)) expiresIn = 300;

	const isResend = data.status === "already_sent";

	apply_state("otp_sent", {
		seconds: expiresIn,
		message: isResend
			? "📬 OTP already sent. Check your inbox."
			: "✅ OTP sent! Check your email.",
		msgColor: isResend ? "#007bff" : "green",
	});
}

async function handle_verify_otp() {
	const currentToken = token || new URLSearchParams(window.location.search).get("t") || "";
	if (_otp_state !== "otp_sent") return;

	const otpInput = document.getElementById("otp-input");
	const otp = otpInput ? otpInput.value.trim() : "";

	if (otp.length !== 6) {
		set_status("⚠️ Please enter the complete 6-digit code.", "orange");
		return;
	}

	// Disable verify button during request — stay in otp_sent state
	const verifyBtn = document.getElementById("verify-otp-btn");
	if (verifyBtn) {
		verifyBtn.disabled = true;
		verifyBtn.textContent = "Verifying…";
	}
	set_status("", "");

	let data;

	try {
		data = await api_call("verp_staffing.utils.customer_page.verify_otp_web", {
			token: currentToken,
			otp: otp,
		});
	} catch (e) {
		console.error("verify error", e);
	}

	if (!data || data._error) {
		if (verifyBtn) {
			verifyBtn.disabled = false;
			verifyBtn.textContent = "Verify OTP";
		}
		const errMsg = typeof data?.message === "string" ? data.message : "";
		if (errMsg.toLowerCase().includes("too many failed attempts")) {
			apply_state("expired");
			if (otpInput) otpInput.value = "";
			set_status(
				"Too many failed attempts. Please try refreshing page and request a new verification code.",
				"red",
			);
		} else {
			set_status(`Verification failed. Please try again.`, "red");
		}
		return;
	}

	if (data.status === "verified") {
		if (data.verification_key && currentToken) {
			sessionStorage.setItem(
				"customer_verification_key_" + currentToken,
				data.verification_key,
			);
		}
		apply_state("verified");
		const otpBox = document.getElementById("otp-box");
		if (otpBox) otpBox.style.display = "none";
		location.reload();
	} else {
		if (verifyBtn) {
			verifyBtn.disabled = false;
			verifyBtn.textContent = "Verify OTP";
		}
		set_status("Invalid or expired OTP.", "red");
	}
}

// ─── State machine (single point of all DOM writes) ───────────────────────────
function apply_state(state, opts) {
	opts = opts || {};
	_otp_state = state;

	const sendBtn = document.getElementById("send-otp-btn");
	const verifyBtn = document.getElementById("verify-otp-btn");
	const otpSec = document.getElementById("otp-section");
	const subtext = document.getElementById("otp-subtext");
	const otpInput = document.getElementById("otp-input");

	// If the DOM isn't ready yet (edge case during restore), bail
	if (!sendBtn || !otpSec) {
		console.warn("[OTP] apply_state called before DOM ready, state:", state);
		return;
	}

	// ── Hard reset baseline ────────────────────────────────────────────────────
	stop_timer();
	otpSec.style.display = "none";
	sendBtn.disabled = false;
	sendBtn.style.background = "#007bff";
	sendBtn.style.color = "#fff";
	if (verifyBtn) verifyBtn.disabled = false;

	// ── Per-state logic ────────────────────────────────────────────────────────
	if (state === "idle") {
		sendBtn.textContent = "Send OTP";
		if (subtext)
			subtext.textContent = "We'll send a 6-digit code to your given email address.";
		set_status("", "");
	} else if (state === "sending") {
		sendBtn.textContent = "Sending…";
		sendBtn.disabled = true;
		sendBtn.style.background = "#6c757d";
		set_status("", "");
	} else if (state === "otp_sent") {
		otpSec.style.display = "block";
		sendBtn.textContent = "OTP Sent";
		sendBtn.disabled = true;
		sendBtn.style.background = "#6c757d";
		if (otpInput) {
			otpInput.value = "";
			otpInput.style.borderColor = "#ddd";
		}
		if (verifyBtn) {
			verifyBtn.disabled = false;
			verifyBtn.textContent = "Verify OTP";
		}
		set_status(opts.message || "✅ OTP sent! Check your email.", opts.msgColor || "green");
		// Start timer only if we have a valid positive seconds value
		if (opts.seconds && opts.seconds > 0) {
			start_timer(opts.seconds);
		}
	} else if (state === "verified") {
		otpSec.style.display = "none";
		sendBtn.style.display = "none";
		if (subtext) subtext.textContent = "Your email has been verified.";
		set_status("✅ Email verified successfully!", "green");
	} else if (state === "expired") {
		otpSec.style.display = "none";
		sendBtn.textContent = "Resend OTP";
		sendBtn.disabled = false;
		sendBtn.style.background = "#fd7e14";
		if (otpInput) otpInput.value = "";
		set_status("⏰ OTP expired. Request a new one.", "red");
	}
}

function start_timer(seconds) {
	stop_timer();
	let remaining = Math.max(parseInt(seconds, 10) || 1, 1);

	function tick() {
		// Always query live — never hold a stale reference
		const timerEl = document.getElementById("otp-timer");
		if (!timerEl) {
			stop_timer();
			return;
		}

		if (remaining <= 0) {
			stop_timer();
			timerEl.textContent = "";
			if (_otp_state === "otp_sent") apply_state("expired");
			return;
		}

		const m = String(Math.floor(remaining / 60)).padStart(2, "0");
		const s = String(remaining % 60).padStart(2, "0");
		timerEl.textContent = "Code expires in " + m + ":" + s;
		remaining--;
	}

	tick();
	_timer_iv = setInterval(tick, 1000);
}

function stop_timer() {
	if (_timer_iv) {
		clearInterval(_timer_iv);
		_timer_iv = null;
	}
}

function set_status(msg, color) {
	const el = document.getElementById("otp-status");
	if (!el) return;
	el.textContent = msg || "";
	el.style.color = color || "#333";
}

function build_otp_html() {
	// customerEmail is decoded from the URL token before this function runs
	const email = typeof customerEmail !== "undefined" && customerEmail ? customerEmail : "";
	const emailLine = email
		? '<p style="margin:0 0 16px 0;font-size:13px;color:#333;line-height:1.5;">' +
			'Sending code to: <strong style="color:#1a1a2e;">' +
			email +
			"</strong></p>"
		: "";

	return [
		'<div id="otp-box" style="border:2px solid #e0e0e0;padding:24px;border-radius:12px;',
		"background:#ffffff;max-width:420px;margin:0 auto;",
		'box-shadow:0 2px 12px rgba(0,0,0,0.08);font-family:inherit;">',

		'<p style="margin:0 0 4px 0;font-weight:700;font-size:17px;color:#1a1a2e;">',
		"Email Verification</p>",

		'<p id="otp-subtext" style="margin:0 0 12px 0;font-size:13px;color:#666;line-height:1.5;">',
		"We'll send a 6-digit verification code to your email address.</p>",

		emailLine,

		'<button type="button" id="send-otp-btn" style="',
		"background:#007bff;color:#fff;border:none;padding:0 24px;border-radius:6px;",
		"font-size:14px;font-weight:600;cursor:pointer;width:100%;height:46px;transition:background 0.25s;",
		'">Send OTP</button>',

		'<div id="otp-section" style="display:none;margin-top:20px;padding-top:20px;border-top:1px solid #ebebeb;">',
		'<p style="margin:0 0 10px 0;font-size:13px;color:#333;font-weight:500;">',
		"Enter the 6-digit code sent to your email:</p>",

		'<input type="text" id="otp-input" placeholder="0 0 0 0 0 0" maxlength="6"',
		' inputmode="numeric" autocomplete="one-time-code"',
		' style="display:block;padding:12px 16px;border:2px solid #ddd;border-radius:6px;',
		"font-size:22px;width:100%;margin-bottom:12px;text-align:center;letter-spacing:10px;",
		'font-weight:700;height:52px;box-sizing:border-box;transition:border-color 0.2s;" />',

		'<button type="button" id="verify-otp-btn" style="',
		"background:#28a745;color:#fff;border:none;padding:0 24px;border-radius:6px;",
		"font-size:14px;font-weight:600;cursor:pointer;width:100%;height:46px;",
		'margin-bottom:14px;transition:background 0.25s;">Verify OTP</button>',

		'<p id="otp-timer" style="margin:0;font-size:13px;color:#888;text-align:center;"></p>',
		"</div>",

		'<p id="otp-status" style="margin:14px 0 0 0;font-size:13px;text-align:center;min-height:20px;"></p>',
		"</div>",

		"<style>",
		"#send-otp-btn:disabled,#verify-otp-btn:disabled{background:#adb5bd!important;cursor:not-allowed!important;}",
		"#otp-input:disabled{background:#f5f5f5;cursor:not-allowed;color:#aaa;}",
		"#send-otp-btn:not(:disabled):hover{background:#0056b3;}",
		"#verify-otp-btn:not(:disabled):hover{background:#218838;}",
		"#otp-input:focus{outline:none;border-color:#007bff;}",
		"</style>",
	].join("");
}
