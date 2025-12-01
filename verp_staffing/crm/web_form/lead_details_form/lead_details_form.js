console.log("Webform JS Loaded!!!");

frappe.ready(function () {

    // unique key for this webform
    let storage_key = "webform_filled_lead_details_form";

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
        frappe.web_form.after_save = () => {
            console.log("Form saved successfully, storing in local storage...");
            localStorage.setItem(storage_key, "1");
        };
    }
});

