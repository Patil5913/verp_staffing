window.LeadCourse = {
    validate_mm_yyyy(value) {
        return /^(0[1-9]|1[0-2])-[0-9]{4}$/.test(value);
    },

    validate_grade(value) {
        value = Number(value || 0);
        return value >= 0 && value <= 10;
    },

    check_row(row) {
        if (row.start_date && !this.validate_mm_yyyy(row.start_date)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("Start Date must be in MM-YYYY format (example: 02-2025)"),
                indicator: "red"
            });
            row.start_date = "";
        }

        if (row.end_date && !this.validate_mm_yyyy(row.end_date)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("End Date must be in MM-YYYY format (example: 02-2025)"),
                indicator: "red"
            });
            row.end_date = "";
        }

        if (row.grade && !this.validate_grade(row.grade)) {
            frappe.msgprint({
                title: __("Invalid Format"),
                message: __("Grade must be between 0 and 10"),
                indicator: "red"
            });
            row.grade = "";
        }
    }
};

window.render_customer_related_html = function ({
    frm,
    html_field,
    source_doctype,
    customer,
    fields,
    label_map = {}
}) {
    console.log("hisduhgisdu");

    if (!customer) {
        frm.set_df_property(html_field, "options", "<p>No customer selected</p>");
        return;
    }

    frappe.call({
        method: "verp_staffing.vrugle_staffing_erp.utils.customer_data.get_data_by_customer",
        args: {
            source_doctype,
            customer,
            fields
        },
        callback(r) {
            const rows = r.message || [];

            if (!rows.length) {
                frm.set_df_property(html_field, "options", "<p>No records found</p>");
                return;
            }

            let html = `
                <style>
                .customer-related-data {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
                    gap: 16px;
                    padding: 4px;
                }

                .data-card {
                    background: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 16px;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                    transition: all 0.2s ease;
                }

                .data-card:hover {
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    border-color: #cbd5e0;
                }

                .data-field {
                    display: flex;
                    flex-direction: column;
                    margin-bottom: 12px;
                    padding-bottom: 12px;
                    border-bottom: 1px solid #f7fafc;
                }

                .data-field:last-child {
                    margin-bottom: 0;
                    padding-bottom: 0;
                    border-bottom: none;
                }

                .field-label {
                    font-size: 12px;
                    font-weight: 600;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 4px;
                }

                .field-value {
                    font-size: 14px;
                    color: #1e293b;
                    word-break: break-word;
                    line-height: 1.5;
                }

                /* Tablet devices */
                @media (max-width: 768px) {
                    .customer-related-data {
                        grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr));
                        gap: 12px;
                    }
                    
                    .data-card {
                        padding: 5px;
                    }
                }

                /* Mobile devices */
                @media (max-width: 480px) {
                    .customer-related-data {
                        grid-template-columns: 1fr;
                        gap: 12px;
                        padding: 2px;
                    }
                    
                    .data-card {
                        padding: 5px;
                    }
                    
                    .field-label {
                        font-size: 11px;
                    }
                    
                    .field-value {
                        font-size: 13px;
                    }
                }

                /* Dark mode support (optional) */
                @media (prefers-color-scheme: dark) {
                    .data-card {
                        border-color: #334155;
                    }
                    
                    .field-label {
                        color: #1e293b;
                    }
                    
                    .field-value {
                        color: #334155;
                    }
                    
                    .data-field {
                        border-bottom-color: #334155;
                    }
                }
                </style>

                <div class="customer-related-data">
                `;

            rows.forEach((row) => {
                html += `<div class="data-card">`;

                fields.forEach(field => {
                    if (row[field]) {
                        const label = label_map[field] || frappe.model.unscrub(field);
                        const value = frappe.utils.escape_html(row[field]);
                        html += `
                <div class="data-field">
                    <span class="field-label">${label}</span>
                    <span class="field-value">${value}</span>
                </div>
            `;
                    }
                });

                html += `</div>`;
            });

            html += `</div>`;

            frm.set_df_property(html_field, "options", html);
        }
    });
};
