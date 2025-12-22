// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing", {
    refresh(frm) {
        frm.set_query("assigned_to", () => {
            return {
                query: "verp_staffing.crm.api.helpers.get_subordinate_employees",
                filters: {
                    department: "Marketing"
                }
            };
        });


        // to display the lead details 
        window.render_customer_related_html({
            frm: frm,
            html_field: "customer_details_html",
            source_doctype: "Lead Detail Form",
            customer: frm.doc.customer,
            fields: [
                "number_for_marketing",
            ],
            label_map: {
                number_for_marketing: "Lead number for marketing",
            }
        });

        if (!frm.is_new()) {
            frm.set_df_property("customer", "read_only", 1);
        }

        // to display the interview list
        render_interview_list(frm);
    },

    customer(frm) {
        frm.trigger("refresh");
    }
});

function render_interview_list(frm) {
    if (!frm.doc.name) return;

    frappe.call({
        method: "verp_staffing.crm.doctype.marketing.marketing.get_interviews_by_marketing",
        args: {
            marketing: frm.doc.name
        },
        callback(r) {
            const data = r.message || [];

            if (!data.length) {
                frm.fields_dict.interview_list.$wrapper.html(
                    "<div class='text-muted'>No interviews linked</div>"
                );
                return;
            }

            let html = "<ul style='padding-left:15px'>";

            data.forEach(d => {
                html += `
                    <li>
                        <a href="#" data-interview="${d.name}">
                            ${d.name}
                        </a>
                    </li>
                `;
            });

            html += "</ul>";

            frm.fields_dict.interview_list.$wrapper.html(html);

            // Click handler
            frm.fields_dict.interview_list.$wrapper
                .find("a")
                .on("click", function (e) {
                    e.preventDefault();

                    frappe.set_route(
                        "List",
                        "Interview",
                        "Kanban",
                        { marketing_link: frm.doc.name }
                    );
                });
        }
    })
}

