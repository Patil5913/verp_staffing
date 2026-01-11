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
    fields
}) {
    if (!customer) {
        frm.set_df_property(html_field, "options", "<p style='text-align: center; color: #6b7280; padding: 20px;'>No customer selected</p>");
        return;
    }

    frappe.call({
        method: "verp_staffing.vrugle_staffing_erp.utils.customer_data.get_data_by_customer",
        args: { source_doctype, customer, fields },
        callback(r) {
            const records = r.message || [];

            if (!Array.isArray(records) || !records.length) {
                frm.set_df_property(html_field, "options", "<p style='text-align: center; color: #6b7280; padding: 20px;'>No records found</p>");
                return;
            }

            let html = `
            <style>
                .customer-data-container {
                    width: 100%;
                    max-width: 100%;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                }
                
                .record-section {
                    margin-bottom: 30px;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    overflow: hidden;
                    background: #ffffff;
                }
                
                .fields-container {
                    padding: 16px;
                }
                
                .field-row {
                    display: grid;
                    grid-template-columns: 200px 1fr;
                    gap: 16px;
                    padding: 10px 0;
                    border-bottom: 1px solid #f1f3f5;
                    align-items: start;
                }
                
                .field-row:last-child {
                    border-bottom: none;
                }
                
                .field-label {
                    font-size: 13px;
                    font-weight: 600;
                    color: #495057;
                    line-height: 1.5;
                }
                
                .field-value {
                    font-size: 13px;
                    color: #212529;
                    word-wrap: break-word;
                    line-height: 1.5;
                }
                
                .field-value a {
                    color: #2563eb !important;
                    text-decoration: none;
                    font-weight: 500;
                    transition: color 0.2s;
                    cursor: pointer;
                }
                
                .field-value a:hover {
                    color: #1d4ed8 !important;
                    text-decoration: underline;
                }
                
                .link-field {
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                }
                
                .table-section {
                    margin-top: 20px;
                    padding: 16px;
                    background: #f8f9fa;
                    border-top: 2px solid #dee2e6;
                }
                
                .table-title {
                    font-size: 14px;
                    font-weight: 600;
                    color: #495057;
                    margin-bottom: 12px;
                }
                
                .table-wrapper {
                    overflow-x: auto;
                    background: #ffffff;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }
                
                table.data-table {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 13px;
                    min-width: 600px;
                }
                
                table.data-table thead {
                    background: #e9ecef;
                }
                
                table.data-table th {
                    padding: 10px 12px;
                    text-align: left;
                    font-weight: 600;
                    color: #495057;
                    border-bottom: 2px solid #dee2e6;
                    white-space: nowrap;
                }
                
                table.data-table td {
                    padding: 10px 12px;
                    border-bottom: 1px solid #f1f3f5;
                    color: #212529;
                }
                
                table.data-table tbody tr:last-child td {
                    border-bottom: none;
                }
                
                table.data-table tbody tr:hover {
                    background-color: #f8f9fa;
                }
                
                @media (max-width: 768px) {
                    .field-row {
                        grid-template-columns: 1fr;
                        gap: 6px;
                    }
                    
                    .field-label {
                        font-size: 12px;
                    }
                    
                    .field-value {
                        font-size: 12px;
                    }
                    
                    .fields-container {
                        padding: 12px;
                    }
                    
                    .table-section {
                        padding: 12px;
                    }
                    
                    table.data-table {
                        font-size: 12px;
                    }
                    
                    table.data-table th,
                    table.data-table td {
                        padding: 8px 10px;
                    }
                }
            </style>

            <div class="customer-data-container">
            `;

            records.forEach((record, index) => {
                html += `
                    <div class="record-section">
                `;

                // Display simple fields
                if (record.fields && record.fields.length > 0) {
                    html += `<div class="fields-container">`;
                    
                    record.fields.forEach(f => {
                        // Skip empty values
                        if (f.value === null || f.value === undefined || f.value === "") {
                            return;
                        }

                        let valueHtml = '';
                        
                        // Check if field is a Link type
                        if (f.fieldtype === 'Link' && f.options) {
                            // Create clickable link that opens the document
                            const doctype_slug = f.options.toLowerCase().replace(/ /g, '-');
                            const url = `/app/${doctype_slug}/${encodeURIComponent(f.value)}`;
                            
                            valueHtml = `<a href="${url}" 
                                           target="_blank" 
                                           class="link-field"
                                           style="color: #2563eb; text-decoration: none; font-weight: 500; cursor: pointer;">
                                ${frappe.utils.escape_html(String(f.value))}
                                <svg style="display: inline-block; width: 14px; height: 14px; margin-left: 4px; vertical-align: middle;" 
                                     fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                                </svg>
                            </a>`;
                        } else {
                            // Regular text value
                            valueHtml = frappe.utils.escape_html(String(f.value));
                        }

                        html += `
                            <div class="field-row">
                                <div class="field-label">${frappe.utils.escape_html(f.label)}</div>
                                <div class="field-value">${valueHtml}</div>
                            </div>
                        `;
                    });
                    
                    html += `</div>`;
                }

                // Display table fields
                if (record.tables && record.tables.length > 0) {
                    record.tables.forEach(table => {
                        if (!table.rows || !table.rows.length) return;

                        const tableLabel = table.label || table.fieldname.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                        html += `
                            <div class="table-section">
                                <div class="table-title">${frappe.utils.escape_html(tableLabel)}</div>
                                <div class="table-wrapper">
                                    <table class="data-table">
                                        <thead>
                                            <tr>
                        `;

                        table.columns.forEach(col => {
                            html += `<th>${frappe.utils.escape_html(col.label)}</th>`;
                        });

                        html += `
                                            </tr>
                                        </thead>
                                        <tbody>
                        `;

                        table.rows.forEach(row => {
                            html += `<tr>`;
                            table.columns.forEach(col => {
                                const cellValue = row[col.fieldname];
                                html += `<td>${
                                    frappe.utils.escape_html(
                                        cellValue != null ? String(cellValue) : ""
                                    )
                                }</td>`;
                            });
                            html += `</tr>`;
                        });

                        html += `
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        `;
                    });
                }

                html += `</div>`;
            });

            html += `</div>`;

            frm.set_df_property(html_field, "options", html);
        }
    });
};