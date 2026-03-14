// // Copyright (c) 2025, Vrugle and contributors
// // For license information, please see license.txt

// frappe.ui.form.on("Sales Order", {
//     refresh(frm) {
//         if (frm.doc.agreement) {
//             frm.add_custom_button("Download Agreement", function () {
//                 frappe.call({
//                     method: "verp_staffing.crm.api.agreement.download_agreement",
//                     args: {
//                         agreement: frm.doc.agreement
//                     },
//                     callback(r) {
//                         if (!r.message) {
//                             frappe.msgprint("No agreement file found.");
//                             return;
//                         }

//                         // Trigger download
//                         window.open(r.message.file_url);
//                     }
//                 });
//             });
//         } else {
//             frm.add_custom_button("Show Agreement Form Tour", () => {
//                 const tour_name = "Sales Order Agreement Form";

//                 // Find the Agreement tab button and click it
//                 const agreement_tab = frm.$wrapper
//                     .find('.nav-link')
//                     .filter(function () {
//                         return $(this).text().trim() === "Agreement";
//                     });

//                 if (!agreement_tab.length) {
//                     frappe.msgprint("Agreement tab not found");
//                     return;
//                 }

//                 agreement_tab.trigger("click");

//                 // Wait until the HTML field is visible, then start tour
//                 const wait_for_tab = setInterval(() => {
//                     const field = frm.get_field("agreement_html");
//                     if (field && field.$wrapper && field.$wrapper.is(":visible")) {
//                         clearInterval(wait_for_tab);

//                         frm.tour.init({ tour_name })
//                             .then(() => frm.tour.start());
//                     }
//                 }, 200);
//             });
//         }

//         render_agreement_ui(frm);
//     }
// });

// //load agreement tab
// function render_agreement_ui(frm) {
//     const wrapper = frm.get_field("agreement_html").$wrapper;
//     wrapper.empty();

//     // Stop if Agreement already exists
//     // If Agreement Already Exists
//     if (frm.doc.agreement) {
//         frappe.call({
//             method: "frappe.client.get",
//             args: { doctype: "Agreement", name: frm.doc.agreement },
//             callback(r) {

//                 if (!r.message) {
//                     frappe.msgprint("Agreement not found.");
//                 } else {
//                     const pdf_url = r.message.pdf || "";  // assuming you saved file_url into agreement_pdf_file

//                     if (pdf_url) {
//                         wrapper.append(`
//                             <div style="padding: 10px;">
//                                 <h3>Agreement Already Created</h3>

//                                 <a href="${pdf_url}" class="btn btn-primary" download style="margin-bottom: 15px;">
//                                     Download Agreement PDF
//                                 </a>

//                                 <div style="margin-top:20px;">
//                                     <embed src="${pdf_url}" type="application/pdf" width="100%" height="600px" />
//                                 </div>
//                             </div>
//                         `);
//                     } else {
//                         wrapper.append(`
//                 <p style="color:red;">Agreement already created, but PDF file missing.</p>
//             `);
//                     }
//                 }
//             }
//         })
//         return; // stop here, do not load UI builder
//     }

//     wrapper.append(`
//             <div id="agreement_container">
//                 <h3>Agreement Builder</h3>

//                 <label>Choose Template</label>
//                 <select id="ag_template" class="form-control"></select>

//                 <div id="ag_dynamic_form" style="margin-top: 20px;"></div>

//                 <button class="btn btn-primary" id="ag_preview" style="margin-top: 15px;">
//                     Preview
//                 </button>

//                 <button class="btn btn-success" id="ag_submit" style="margin-left: 10px; margin-top: 15px;">
//                     Save & Send
//                 </button>
//             </div>
//         `);
//     load_templates(frm);
//     bind_events(frm);
// }

// function load_templates(frm) {
//     const select = frm.get_field("agreement_html").$wrapper.find("#ag_template");

//     frappe.call({
//         method: "frappe.client.get_list",
//         args: {
//             doctype: "Pdf Agreement Template",
//             filters: { is_active: 1 },
//             fields: ["name", "title"]
//         },
//         callback(r) {
//             select.append(`<option value="">Select</option>`);
//             (r.message || []).forEach(t => {
//                 select.append(`<option value="${t.name}">${t.title || t.name}</option>`);
//             });
//         }
//     });
// }

// function bind_events(frm) {
//     const wrap = frm.get_field("agreement_html").$wrapper;

//     // When template changes → load dynamic fields
//     wrap.on("change", "#ag_template", function () {
//         load_form_fields(frm);
//     });

//     // Preview Button
//     wrap.on("click", "#ag_preview", function () {
//         preview_inline(frm);
//     });

//     // Submit Button
//     wrap.on("click", "#ag_submit", function () {
//         submit_inline(frm);
//     });
// }

// function load_form_fields(frm) {
//     const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
//     const form_div = frm.get_field("agreement_html").$wrapper.find("#ag_dynamic_form");

//     if (!template) {
//         form_div.empty();
//         return;
//     }

//     frappe.call({
//         method: "frappe.client.get",
//         args: { doctype: "Pdf Agreement Template", name: template },
//         callback(r) {
//             const tpl = r.message;

//             const blocks = JSON.parse(tpl.fields_json || "[]");

//             form_div.empty();

//             blocks.forEach(b => {
//                 if (b.type == "Text" || b.type == "Number" || b.type == "Date") {

//                     form_div.append(`
//                         <div style="margin-bottom: 10px;">
//                                 <label>${b.label || b.name}</label>
//                                 <input type="${b.type ?? "text"}" class="form-control ag-field"
//                                 data-field="${b.name}"
//                                 >
//                                 </div>
//                                 `);
//                 }
//             });
//         }
//     });
// }

// function preview_inline(frm) {
//     const wrap = frm.get_field("agreement_html").$wrapper;
//     const template = wrap.find("#ag_template").val();
//     if (!template) {
//         frappe.msgprint("Choose a template first");
//         return;
//     }

//     const data = collect_so_agreement_data(frm);

//     frappe.call({
//         method: "verp_staffing.crm.api.agreement.preview_agreement",
//         args: {
//             template: template,
//             data: JSON.stringify(data),
//         },
//         callback(r) {
//             if (!r.message) return frappe.msgprint("Preview error");
//             // const frame = frm.fields_dict.agreement_html.$wrapper.find("#so_preview_frame");
//             // frame.html(`<iframe src="${r.message.file_url}" style="width:100%; height:600px; border:none;"></iframe>`);
//             window.open(r.message.file_url);
//         }
//     });
// }

// async function submit_inline(frm) {

//     const wrap = frm.get_field("agreement_html").$wrapper;
//     const template = wrap.find("#ag_template").val();

//     if (!template) {
//         frappe.msgprint("Choose a template first");
//         return;
//     }

//     if (!frm.doc.customer) {
//         frappe.msgprint("Customer is required.");
//         return;
//     }

//     try {

//         // 🔥 Step 1: Find Lead Details linked to Customer
//         let ref = await frappe.db.get_value(
//             "Doctype Reference",
//             {
//                 reference_doctype: "Customer",
//                 reference_person: frm.doc.customer
//             },
//             "parent"
//         );

//         if (!ref.message || !ref.message.parent) {
//             frappe.msgprint("No Lead Details found for this Customer.");
//             return;
//         }

//         let lead_details_name = ref.message.parent;

//         // 🔥 Step 2: Get Email from Lead Details
//         let ld = await frappe.db.get_value(
//             "Lead Details",
//             lead_details_name,
//             "email"
//         );

//         let recipient = ld.message?.email;

//         if (!recipient) {
//             frappe.msgprint(`Email not found in Lead Details for Customer: ${frm.doc.customer}.`);
//             return;
//         }

//         const data = collect_so_agreement_data(frm);

//         frappe.confirm(
//             "Save and send agreement? This will lock the agreement.",
//             function () {

//                 frappe.call({
//                     method: "verp_staffing.crm.api.agreement.submit_and_generate",
//                     args: {
//                         sales_order: frm.doc.name,
//                         template: template,
//                         recipient,
//                         data: JSON.stringify(data)
//                     },
//                     callback(r) {
//                         if (!r.message) {
//                             frappe.throw("Agreement generation failed.");
//                         }
//                     }
//                 });

//             }
//         );

//     } catch (err) {
//         console.error(err);
//         frappe.msgprint("Error while validating customer email.");
//     }
// }

// function collect_so_agreement_data(frm) {
//     const data = {};
//     frm.fields_dict.agreement_html.$wrapper.find(".ag-field").each(function () {
//         const key = $(this).data("field");
//         data[key] = $(this).val();
//     });

//     // If payment_terms exist in Sales Order, include them
//     // fetch child table rows
//     data["Payment_Terms"] = (frm.doc.payment_terms || []).map(r => ({
//         date: r.date,
//         amount: r.amount,
//         is_received: r.is_received
//     }));

//     // frappe.call({
//     //     method: "verp_staffing.crm.api.agreement.submit_and_generate",
//     //     args: {
//     //         sales_order: frm.doc.name,
//     //         template,
//     //         data: values
//     //     },
//     //     callback(r) {
//     //         frappe.msgprint("Agreement saved & sent.");
//     //         frm.reload_doc();
//     //         // in this collect the lead from customer of this sales order and send that in url to webform via search params
//     //         // collect aggrement file url from this callback response and send in agreement html in webform to display
//     //     }
//     // });

//     return data;
// }

// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		frm.add_custom_button(__("Send Details Form"), () => send_details_form(frm), __("Send"));
		if (frm.doc.agreement) {
			frm.add_custom_button("Download Agreement", function () {
				frappe.call({
					method: "verp_staffing.crm.api.agreement.download_agreement",
					args: { agreement: frm.doc.agreement },
					callback(r) {
						if (!r.message) {
							frappe.msgprint("No agreement file found.");
							return;
						}
						window.open(r.message.file_url);
					},
				});
			});
			frm.add_custom_button(__("Send Agreement"), () => send_agreement(frm), __("Send"));
		} else {
			frm.add_custom_button("Show Agreement Form Tour", () => {
				const tour_name = "Sales Order Agreement Form";
				const agreement_tab = frm.$wrapper.find(".nav-link").filter(function () {
					return $(this).text().trim() === "Agreement";
				});

				if (!agreement_tab.length) {
					frappe.msgprint("Agreement tab not found");
					return;
				}

				agreement_tab.trigger("click");

				const wait_for_tab = setInterval(() => {
					const field = frm.get_field("agreement_html");
					if (field && field.$wrapper && field.$wrapper.is(":visible")) {
						clearInterval(wait_for_tab);
						frm.tour.init({ tour_name }).then(() => frm.tour.start());
					}
				}, 200);
			});
		}

		render_agreement_ui(frm);
	},
});

function render_agreement_ui(frm) {
	const wrapper = frm.get_field("agreement_html").$wrapper;
	wrapper.empty();

	if (frm.doc.agreement) {
		frappe.call({
			method: "frappe.client.get",
			args: { doctype: "Agreement", name: frm.doc.agreement },
			callback(r) {
				if (!r.message) {
					frappe.msgprint("Agreement not found.");
					return;
				}

				const pdf_url = r.message.pdf || "";
				if (pdf_url) {
					wrapper.append(`
                        <div style="padding: 10px;">
                            <h3>Agreement Already Created</h3>
                            <a href="${pdf_url}" class="btn btn-primary" download style="margin-bottom: 15px;">
                                Download Agreement PDF
                            </a>
                            <div style="margin-top:20px;">
                                <embed src="${pdf_url}" type="application/pdf" width="100%" height="600px" />
                            </div>
                        </div>
                    `);
				} else {
					wrapper.append(
						`<p style="color:red;">Agreement already created, but PDF file missing.</p>`,
					);
				}
			},
		});
		return; // Stop loading the builder if agreement exists
	}

	wrapper.append(`
        <div id="agreement_container">
            <h3>Agreement Builder</h3>
            <label>Choose Template</label>
            <select id="ag_template" class="form-control"></select>
            <div id="ag_dynamic_form" style="margin-top: 20px;"></div>
            <button class="btn btn-primary" id="ag_preview" style="margin-top: 15px;">Preview</button>
            <button class="btn btn-success" id="ag_submit" style="margin-left: 10px; margin-top: 15px;">Save & Send</button>
        </div>
    `);

	load_templates(frm);
	bind_events(frm);
}

function load_templates(frm) {
	const select = frm.get_field("agreement_html").$wrapper.find("#ag_template");

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Pdf Agreement Template",
			filters: { is_active: 1 },
			fields: ["name", "title"],
		},
		callback(r) {
			select.empty();
			select.append(`<option value="">Select</option>`);
			(r.message || []).forEach((t) => {
				select.append(`<option value="${t.name}">${t.title || t.name}</option>`);
			});
		},
	});
}

function bind_events(frm) {
	const wrap = frm.get_field("agreement_html").$wrapper;

	wrap.on("change", "#ag_template", () => load_form_fields(frm));
	wrap.on("click", "#ag_preview", () => preview_inline(frm));
	wrap.on("click", "#ag_submit", () => submit_inline(frm));
}

function load_form_fields(frm) {
	const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
	const form_div = frm.get_field("agreement_html").$wrapper.find("#ag_dynamic_form");

	if (!template) {
		form_div.empty();
		return;
	}

	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Pdf Agreement Template", name: template },
		callback(r) {
			const tpl = r.message;
			const blocks = JSON.parse(tpl.fields_json || "[]");
			form_div.empty();

			blocks.forEach((b) => {
				if (["Text", "Number", "Date"].includes(b.type)) {
					form_div.append(`
                        <div style="margin-bottom: 10px;">
                            <label>${b.label || b.name}</label>
                            <input type="${b.type ?? "text"}" class="form-control ag-field"
                                data-field="${b.name}">
                        </div>
                    `);
				}
			});
		},
	});
}

function preview_inline(frm) {
	const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
	if (!template) return frappe.msgprint("Choose a template first");

	const data = collect_so_agreement_data(frm);

	frappe.call({
		method: "verp_staffing.crm.api.agreement.preview_agreement",
		args: { template, data: JSON.stringify(data) },
		callback(r) {
			if (!r.message) return frappe.msgprint("Preview error");
			window.open(r.message.file_url);
		},
	});
}

async function submit_inline(frm) {
	const template = frm.get_field("agreement_html").$wrapper.find("#ag_template").val();
	if (!template) return frappe.msgprint("Choose a template first");
	if (!frm.doc.customer) return frappe.msgprint("Customer is required.");

	try {
		// Get Customer email safely
		let recipient = await frappe.call({
			method: "verp_staffing.crm.api.agreement.get_customer_email",
			args: { customer: frm.doc.customer },
		});
		recipient = recipient.message;

		if (!recipient) {
			frappe.msgprint(`Email not found for Customer: ${frm.doc.customer}`);
			return;
		}

		const data = collect_so_agreement_data(frm);

		frappe.confirm("Save and send agreement? This will lock the agreement.", () => {
			frappe.call({
				method: "verp_staffing.crm.api.agreement.submit_and_generate",
				args: {
					sales_order: frm.doc.name,
					template,
					recipient,
					data: JSON.stringify(data),
				},
				callback(r) {
					if (!r.message) frappe.throw("Agreement generation failed.");
					frappe.msgprint("Agreement created and sent successfully.");
					frm.reload_doc();
				},
			});
		});
	} catch (err) {
		console.error(err);
		frappe.msgprint("Error while validating customer email.");
	}
}

function collect_so_agreement_data(frm) {
	const data = {};
	frm.fields_dict.agreement_html.$wrapper.find(".ag-field").each(function () {
		const key = $(this).data("field");
		data[key] = $(this).val();
	});

	// Include payment_terms
	data["Payment_Terms"] = (frm.doc.payment_terms || []).map((r) => ({
		date: r.date,
		amount: r.amount,
		is_received: r.is_received,
	}));

	return data;
}

async function send_agreement(frm) {
	let recipient = await frappe.call({
		method: "verp_staffing.crm.api.agreement.get_customer_email",
		args: { customer: frm.doc.customer },
	});
	recipient = recipient.message;

	if (!recipient) {
		frappe.msgprint(`Email not found for Customer: ${frm.doc.customer}`);
		return;
	}
	frappe.call({
		method: "verp_staffing.accounts.doctype.sales_order.sales_order.send_agreement_notification",
		args: {
			recipient,
			agreement_url: frm.doc.agreement,
		},
		callback(r) {
			if (!r.message) frappe.throw("Failed to send email, retry again.");
			frappe.msgprint("Agreement created and sent successfully.");
			frm.reload_doc();
		},
	});
}

async function send_details_form(frm) {
	let recipient = await frappe.call({
		method: "verp_staffing.crm.api.agreement.get_customer_email",
		args: { customer: frm.doc.customer },
	});
	recipient = recipient.message;

	if (!recipient) {
		frappe.msgprint(`Email not found for Customer: ${frm.doc.customer}`);
		return;
	}
	frappe.call({
		method: "verp_staffing.accounts.doctype.sales_order.sales_order.send_details_form_notification",
		args: {
			recipient,
			agreement: frm.doc.agreement,
			sales_order: frm.doc.name,
		},
		callback(r) {
			if (!r.message) frappe.throw("Failed to send email, retry again.");
			frappe.msgprint("Agreement created and sent successfully.");
			frm.reload_doc();
		},
	});
}
