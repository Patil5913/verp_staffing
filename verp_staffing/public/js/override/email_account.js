frappe.ui.form.on("Email Account", {
    refresh(frm) {
        configure_email_account(frm);
    }
});

function configure_email_account(frm) {
    const is_admin = frappe.user.has_role("System Manager");
    const allowed = [
        "brand_logo",
        "footer",
        "auto_reply_message",
        "enable_auto_reply",
        "signature",
        "add_signature",
        "attachment_limit",
        "password",
        "email_account_name",
        "email_id",
        "domain"
    ];
    
    // Force values
    frm.set_value("enable_outgoing", 1);
    frm.set_value("enable_incoming", 1);
    frm.set_value("auth_method", "Basic");

    frm.set_df_property("enable_outgoing", "hidden", 1);
    frm.set_df_property("enable_incoming", "hidden", 1);
    frm.set_df_property("auth_method", "hidden", 1);

    if(is_admin){
        allowed.push("default_outgoing")
    } else {
        frm.set_df_property("default_outgoing", "hidden", 1);
    }

    const layout_fields = [
        "Section Break",
        "Column Break",
        "Tab Break",
        "HTML",
        "Heading"
    ];

    frm.meta.fields.forEach(df => {
        if (!df.fieldname) return;

        // Never hide layout fields
        if (layout_fields.includes(df.fieldtype)) return;

        frm.set_df_property(
            df.fieldname,
            "hidden",
            !allowed.includes(df.fieldname)
        );
    });    
}