let _otp_state = "idle";
let _timer_iv = null;
let _events_bound = false;

let token = null;
let customerEmail = null;

document.addEventListener("DOMContentLoaded", function () {
	start_otp_bootstrap();
});

async function start_otp_bootstrap() {
	const root = await wait_for_root("#otp-root", 3000);
	token = new URLSearchParams(window.location.search).get("t");

	// ✅ otherwise load OTP UI
	customerEmail = decode_token_email(token);

	if (!root) return;

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
	try {

		await fetch(
			"/api/method/verp_staffing.utils.customer_page.logout_otp_web?token=" + token
		);
		
		// document.getElementById("otp-box").style.display = "none";
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

async function restore_otp_state() {
	const data = await safe_frappe_call({
		method: "verp_staffing.utils.customer_page.get_otp_status_web", // 🔧 update path
		args: { token: token },
	});

	if (!data) {
		apply_state("idle");
		return;
	}

	const state = data.state;
	const expiresIn = parseInt(data.expires_in, 10) || 0;

	if (state === "verified") {
		apply_state("verified");
	} else if (state === "otp_sent") {
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

async function handle_send_otp() {
	// Block re-entry
	if (_otp_state === "otp_sent" || _otp_state === "sending" || _otp_state === "verified") return;

	if (!customerEmail) {
		set_status("⚠️ Unable to find your email address.", "orange");
		return;
	}

	apply_state("sending");

	const data = await safe_frappe_call({
		method: "verp_staffing.utils.customer_page.send_otp_web", // 🔧 update path
		args: { token: token, email: customerEmail },
	});

	if (!data) {
		apply_state("idle");
		set_status("❌ Failed to send OTP. Please try again.", "red");
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

	const data = await safe_frappe_call({
		method: "verp_staffing.utils.customer_page.verify_otp_web", // 🔧 update path
		args: { token: token, otp: otp },
		return_error: true,
	});

	if (data && data._error) {
		if (verifyBtn) {
			verifyBtn.disabled = false;
			verifyBtn.textContent = "Verify OTP";
		}

		const msg = (data.message || "").toLowerCase();
		if (msg.includes("expired")) {
			apply_state("expired");
		} else if (msg.includes("invalid")) {
			set_status("❌ Wrong OTP. Please try again.", "red");
			if (otpInput) {
				otpInput.style.borderColor = "#dc3545";
				setTimeout(function () {
					otpInput.style.borderColor = "#ddd";
				}, 1500);
			}
		} else {
			set_status("❌ Verification failed. Please try again.", "red");
		}
		return;
	}

	if (data && data.status === "verified") {
		apply_state("verified");
		document.getElementById("otp-box").style.display = "none";
		location.reload();
	} else {
		if (verifyBtn) {
			verifyBtn.disabled = false;
			verifyBtn.textContent = "Verify OTP";
		}
		set_status("❌ Unexpected response. Please try again.", "red");
	}
}

// Returns: the message object on success, null on error (or error object if return_error:true)
async function safe_frappe_call(opts) {
	const return_error = opts.return_error || false;
	return _frappe_call_with_retry(opts, return_error, 0);
}

async function _frappe_call_with_retry(opts, return_error, attempt) {
	let r;

	try {
		const response = await fetch("/api/method/" + opts.method, {
			method: "POST",
			credentials: "include",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(opts.args || {}),
		});

		r = await response.json();
	} catch (ex) {
		const isAbort = ex && typeof ex === "object" && ex.name === "AbortError";

		if (isAbort && attempt < 2) {
			console.warn("[OTP] fetch aborted, retrying attempt", attempt + 1, opts.method);

			await new Promise((res) => setTimeout(res, 300));
			return _frappe_call_with_retry(opts, return_error, attempt + 1);
		}

		console.error("[OTP] fetch failed:", opts.method, ex);

		if (return_error) return { _error: true, message: "Network error. Please try again." };

		return null;
	}

	// Frappe API returns { message: ..., exc: ... }
	// If backend explicitly sends error
	if (r && r.exc) {
		const user_msg = parse_frappe_exc(r.exc);
		console.error("[OTP] server error:", opts.method, r.exc);

		if (return_error) return { _error: true, message: user_msg };

		return null;
	}

	// Success response (direct JSON from Python)
	if (r && typeof r === "object") {
		return r.message || r;
	}

	console.error("[OTP] empty response:", opts.method, r);

	if (return_error) return { _error: true, message: "Unexpected server response." };

	return null;
}

// Extract the human-readable error from a Frappe exc traceback string
function parse_frappe_exc(exc) {
	if (!exc) return "server error";
	const lines = String(exc)
		.split("\n")
		.map(function (l) {
			return l.trim();
		})
		.filter(Boolean);
	const last = lines[lines.length - 1] || "";
	// Strip the exception class prefix if present
	const colon = last.indexOf(":");
	return colon >= 0 ? last.slice(colon + 1).trim() : last;
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


