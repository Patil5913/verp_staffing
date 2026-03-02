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
				indicator: "red",
			});
			row.start_date = "";
		}

		if (row.end_date && !this.validate_mm_yyyy(row.end_date)) {
			frappe.msgprint({
				title: __("Invalid Format"),
				message: __("End Date must be in MM-YYYY format (example: 02-2025)"),
				indicator: "red",
			});
			row.end_date = "";
		}

		if (row.grade && !this.validate_grade(row.grade)) {
			frappe.msgprint({
				title: __("Invalid Format"),
				message: __("Grade must be between 0 and 10"),
				indicator: "red",
			});
			row.grade = "";
		}
	},
};

window.render_customer_related_html = function ({ frm, html_field, customer, fields }) {
	if (!customer) {
		frm.set_df_property(
			html_field,
			"options",
			"<p style='text-align: center; color: #6b7280; padding: 20px;'>No customer selected</p>",
		);
		return;
	}

	frappe.call({
		method: "verp_staffing.vrugle_staffing_erp.utils.customer_data.get_data_by_customer",
		args: { customer, fields },
		callback(r) {
			const records = r.message || [];

			if (!Array.isArray(records) || !records.length) {
				frm.set_df_property(
					html_field,
					"options",
					"<p style='text-align:center;color:#6b7280;padding:20px;'>No records found</p>",
				);
				return;
			}

			window.showFullPreview = function (content) {
				const existing = document.querySelector(".full-preview-overlay");
				if (existing) existing.remove();

				const overlay = document.createElement("div");
				overlay.className = "full-preview-overlay";

				overlay.innerHTML = `
                <div class="full-preview-box">
                    <div class="preview-header">
                        <span>Description</span>
                        <button class="close-preview-btn">Close</button>
                    </div>
                    <div class="preview-body">${content}</div>
                </div>
            `;

				overlay.querySelector(".close-preview-btn").onclick = () => overlay.remove();
				overlay.onclick = (e) => {
					if (e.target === overlay) overlay.remove();
				};

				document.body.appendChild(overlay);
			};

			let html = `
        <style>
            .customer-data-container {
                width: 100%;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            }

            .record-section {
                margin-bottom: 30px;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background: #ffffff;
                overflow: hidden;
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
            }

            .field-row:last-child {
                border-bottom: none;
            }

            .field-label {
                font-size: 13px;
                font-weight: 600;
                color: #495057;
            }

            .field-value {
                font-size: 13px;
                color: #212529;
                word-break: break-word;
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
                margin-bottom: 12px;
                color: #374151;
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
                table-layout: fixed;
                font-size: 13px;
                min-width: 600px;
            }

            table.data-table th,
            table.data-table td {
                padding: 10px 12px;
                border-bottom: 1px solid #f1f3f5;
                word-break: break-word;
                overflow-wrap: break-word;
                white-space: normal;
            }

            table.data-table thead {
                background: #e9ecef;
            }

            table.data-table tbody tr:hover {
                background-color: #f8f9fa;
            }

            .full-preview-overlay {
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.55);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            }

            .full-preview-box {
                background: #ffffff;
                width: 90%;
                max-width: 800px;
                max-height: 80vh;
                border-radius: 10px;
                padding: 20px;
                overflow-y: auto;
                box-shadow: 0 10px 30px rgba(0,0,0,0.25);
            }

            .preview-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                font-weight: 600;
                font-size: 16px;
            }

            .close-preview-btn {
                background: #ef4444;
                border: none;
                color: white;
                padding: 6px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
            }

            .close-preview-btn:hover {
                background: #dc2626;
            }

            .preview-body {
                font-size: 14px;
                line-height: 1.6;
                white-space: pre-wrap;
            }
        </style>

        <div class="customer-data-container">
        `;

			records.forEach((record) => {
				html += `<div class="record-section">`;

				if (record.fields?.length) {
					html += `<div class="fields-container">`;

					record.fields.forEach((f) => {
						if (!f.value) return;

						const value = frappe.utils.escape_html(String(f.value));

						html += `
                        <div class="field-row">
                            <div class="field-label">${frappe.utils.escape_html(f.label)}</div>
                            <div class="field-value">${value}</div>
                        </div>
                    `;
					});

					html += `</div>`;
				}

				if (record.tables?.length) {
					record.tables.forEach((table) => {
						if (!table.rows?.length) return;

						const tableLabel =
							table.label ||
							table.fieldname
								.replace(/_/g, " ")
								.replace(/\b\w/g, (l) => l.toUpperCase());

						const isWide = table.columns.length > 7;

						html += `
                        <div class="table-section">
                            <div class="table-title">${frappe.utils.escape_html(tableLabel)}</div>
                            <div class="table-wrapper">
                                <table class="data-table" style="${isWide ? "min-width:1200px;" : ""}">
                                    <thead>
                                        <tr>
                    `;

						table.columns.forEach((col) => {
							html += `<th>${frappe.utils.escape_html(col.label)}</th>`;
						});

						html += `
                                        </tr>
                                    </thead>
                                    <tbody>
                    `;

						table.rows.forEach((row) => {
							html += `<tr>`;

							table.columns.forEach((col) => {
								const cellValue = row[col.fieldname];
								const text = cellValue != null ? String(cellValue) : "";
								const escapedText = frappe.utils.escape_html(text);

								if (text.length > 100) {
									const shortText =
										frappe.utils.escape_html(text.substring(0, 35)) + "...";

									html += `
                                    <td style="width:500px; max-width:500px;">
                                        <span style="cursor:pointer; color:#2563eb; font-weight:500;"
                                              onclick="showFullPreview(\`${escapedText.replace(/`/g, "\\`")}\`)">
                                            ${shortText}
                                        </span>
                                    </td>
                                `;
								} else {
									html += `<td>${escapedText}</td>`;
								}
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
		},
	});
};
