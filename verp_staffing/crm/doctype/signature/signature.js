// Copyright (c) 2026, Vrugle and contributors
// For license information, please see license.txt
let activeBox = null;
let actionType = null;
let offsetX = 0;
let offsetY = 0;
let activeOverlay = null;

frappe.ui.form.on("Signature", {
  refresh(frm) {
    if (!frm.doc.original_pdf) return;
    if (!frm._pdf_loaded) {
      load_pdf_pages(frm);
      frm._pdf_loaded = true;
    }
    render_signers_panel(frm);
  }

});


function render_signers_panel(frm) {

  if (!frm.doc.signature_fields || !frm.doc.signature_fields.length) {
    frm.fields_dict.signers_panel.$wrapper.html(
      `<div style="padding:10px;">No signers yet.</div>`
    );
    return;
  }

  // 🔹 Group fields by signer email
  const grouped = {};

  frm.doc.signature_fields.forEach(row => {
    if (!grouped[row.signer_email]) {
      grouped[row.signer_email] = [];
    }
    grouped[row.signer_email].push(row);
  });

  let html = `
    <div style="padding:15px;">
      <h4>Signers</h4>
  `;

  Object.keys(grouped).forEach(email => {

    const rows = grouped[email];

    const allSigned = rows.every(r => r.signed);
    const firstSignedRow = rows.find(r => r.signed);

    html += `
      <div style="
        display:flex;
        justify-content:space-between;
        align-items:center;
        padding:10px 0;
        border-bottom:1px solid #eee;
      ">
        <div>
          <div style="font-weight:500;">${email}</div>
    `;

    // ✅ IF SIGNED → show signature image + datetime



    if (allSigned && firstSignedRow?.signature_image) {
      html += `
          <div style="margin-top:6px;">
            <img src="${firstSignedRow.signature_image}"
                 style="height:40px; object-fit:contain; border:black; display:block;">
            <div style="font-size:12px; color:#666; margin-top:4px;">
              Signed on: ${firstSignedRow.signed_on || ""}
            </div>
          </div>
      `;
    }

    html += `</div>`;

    // ❌ IF NOT SIGNED → show Send button
    if (!allSigned) {
      html += `
        <button class="btn btn-sm btn-primary send-btn"
                data-email="${email}">
          Send
        </button>
      `;
    } else {
      html += `
        <span style="color:green; font-weight:500;">
          ✔ Signed
        </span>
      `;
    }

    html += `</div>`;
  });

  html += `</div>`;

  frm.fields_dict.signers_panel.$wrapper.html(html);

  // 🔹 Attach send button click
  frm.fields_dict.signers_panel.$wrapper
    .find(".send-btn")
    .on("click", function () {

      const email = $(this).data("email");

      frappe.call({
        method: "verp_staffing.crm.doctype.signature.signature.send_signer_email",
        args: {
          agreement: frm.doc.name,
          email: email
        },
        callback: function (r) {
          frappe.msgprint(r.message);
        }
      });

    });
}

async function load_pdf_pages(frm) {

  const wrapper = frm.fields_dict.original_pdf.$wrapper;

  wrapper.html(`
    <div id="pdf-container"
      style="height:85vh; overflow:auto; padding:20px; background:#f3f4f6;">
    </div>
  `);

  const response = await frappe.call({
    method: "verp_staffing.crm.doctype.signature.signature.generate_pdf_pages",
    args: { docname: frm.doc.name }
  });

  const pages = response.message;
  const container = document.getElementById("pdf-container");

  pages.forEach(page => {

    const pageWrapper = document.createElement("div");
    pageWrapper.style.position = "relative";
    pageWrapper.style.marginBottom = "20px";
    pageWrapper.dataset.page = page.page_number;

    const img = document.createElement("img");
    img.src = page.url;
    img.style.width = "100%";
    img.style.display = "block";

    const overlay = document.createElement("div");
    overlay.className = "page-overlay";
    overlay.dataset.page = page.page_number;
    overlay.style.position = "absolute";
    overlay.style.inset = "0";

    pageWrapper.appendChild(img);
    pageWrapper.appendChild(overlay);
    container.appendChild(pageWrapper);


    enable_drawing(frm, overlay);
  });
  render_existing_boxes(frm);

}

function enable_drawing(frm, overlay) {

  let isDrawing = false;
  let startX, startY;
  let box;

  overlay.addEventListener("mousedown", function (e) {

    if (e.target !== overlay) return;

    const rect = overlay.getBoundingClientRect();
    startX = e.clientX - rect.left;
    startY = e.clientY - rect.top;

    box = create_box(frm);
    box.style.left = startX + "px";
    box.style.top = startY + "px";

    overlay.appendChild(box);
    isDrawing = true;
  });

  overlay.addEventListener("mousemove", function (e) {

    if (!isDrawing) return;

    const rect = overlay.getBoundingClientRect();
    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top;

    box.style.width = Math.abs(currentX - startX) + "px";
    box.style.height = Math.abs(currentY - startY) + "px";
  });

  overlay.addEventListener("mouseup", function () {

    if (!isDrawing) return;
    isDrawing = false;
    const email = prompt("Enter signer email:");

    if (!email) {
      box.remove();
      return;
    }

    box.dataset.signer_email = email;

    attach_box_events(frm, box, overlay);
    save_box(frm, box, overlay);
  });
}

function create_box(frm) {

  const box = document.createElement("div");

  box.style.position = "absolute";
  box.style.border = "2px solid #2563eb";
  box.style.background = "rgba(37,99,235,0.1)";
  box.style.minWidth = "80px";
  box.style.minHeight = "30px";
  box.style.cursor = "move";

  // 🔥 DELETE BUTTON
  const deleteBtn = document.createElement("div");
  deleteBtn.innerHTML = "✕";
  deleteBtn.style.position = "absolute";
  deleteBtn.style.top = "-10px";
  deleteBtn.style.right = "-10px";
  deleteBtn.style.width = "18px";
  deleteBtn.style.height = "18px";
  deleteBtn.style.borderRadius = "50%";
  deleteBtn.style.background = "#ef4444";
  deleteBtn.style.color = "white";
  deleteBtn.style.display = "flex";
  deleteBtn.style.alignItems = "center";
  deleteBtn.style.justifyContent = "center";
  deleteBtn.style.fontSize = "12px";
  deleteBtn.style.cursor = "pointer";
  deleteBtn.style.zIndex = "10";

  deleteBtn.addEventListener("click", function (e) {
    e.stopPropagation();

    if (!confirm("Delete this signature box?")) return;

    const rowname = box.dataset.rowname;

    if (rowname) {
      frm.doc.signature_fields = frm.doc.signature_fields.filter(
        row => row.name !== rowname
      );

      frm.dirty();
      frm.refresh_field("signature_fields");
    }
    
    box.remove();
    
    frm.save()
    render_existing_boxes(frm);
  });

  box.appendChild(deleteBtn);

  // Resize Handle
  const resize = document.createElement("div");
  resize.style.position = "absolute";
  resize.style.right = "0";
  resize.style.bottom = "0";
  resize.style.width = "10px";
  resize.style.height = "10px";
  resize.style.background = "#2563eb";
  resize.style.cursor = "se-resize";

  box.appendChild(resize);

  return box;
}

function attach_box_events(frm, box, overlay) {

  const resizeHandle = box.lastChild;

  box.addEventListener("mousedown", function (e) {

    e.stopPropagation();

    activeBox = box;
    activeOverlay = overlay;

    if (e.target === resizeHandle) {
      actionType = "resize";
    } else {
      actionType = "drag";
      offsetX = e.offsetX;
      offsetY = e.offsetY;
    }
  });
}

document.addEventListener("mousemove", function (e) {

  if (!activeBox || !actionType) return;

  const rect = activeOverlay.getBoundingClientRect();

  if (actionType === "drag") {
    activeBox.style.left = e.clientX - rect.left - offsetX + "px";
    activeBox.style.top = e.clientY - rect.top - offsetY + "px";
  }

  if (actionType === "resize") {
    const boxRect = activeBox.getBoundingClientRect();
    activeBox.style.width = e.clientX - boxRect.left + "px";
    activeBox.style.height = e.clientY - boxRect.top + "px";
  }
});

document.addEventListener("mouseup", function () {

  if (activeBox && activeOverlay) {
    update_child_table(cur_frm, activeBox, activeOverlay);
  }

  activeBox = null;
  actionType = null;
});

function save_box(frm, box, overlay) {

  const rect = overlay.getBoundingClientRect();

  const child = frm.add_child("signature_fields", {
    page_number: overlay.dataset.page,
    signer_email: box.dataset.signer_email,
    x_percent: (box.offsetLeft / rect.width) * 100,
    y_percent: (box.offsetTop / rect.height) * 100,
    width_percent: (box.offsetWidth / rect.width) * 100,
    height_percent: (box.offsetHeight / rect.height) * 100
  });

  box.dataset.rowname = child.name;

  frm.refresh_field("signature_fields");
}

function update_child_table(frm, box, overlay) {

  const rect = overlay.getBoundingClientRect();
  const rowname = box.dataset.rowname;

  if (!rowname) return;

  const row = frm.doc.signature_fields.find(r => r.name === rowname);
  if (!row) return;

  row.x_percent = (box.offsetLeft / rect.width) * 100;
  row.y_percent = (box.offsetTop / rect.height) * 100;
  row.width_percent = (box.offsetWidth / rect.width) * 100;
  row.height_percent = (box.offsetHeight / rect.height) * 100;

  frm.refresh_field("signature_fields");
}

function render_existing_boxes(frm) {

  // Prevent duplicate rendering
  document.querySelectorAll(".page-overlay").forEach(o => o.innerHTML = "");
  setTimeout(() => {

    frm.doc.signature_fields.forEach(field => {

      const overlay = document.querySelector(
        `.page-overlay[data-page="${field.page_number}"]`
      );

      if (!overlay) return;

      // 🔥 IF SIGNED → SHOW SIGNATURE IMAGE
      if (field.signed && field.signature_image) {

        const img = document.createElement("img");
        img.src = field.signature_image;

        img.style.position = "absolute";
        img.style.left = field.x_percent + "%";
        img.style.top = field.y_percent + "%";
        img.style.width = field.width_percent + "%";
        img.style.height = field.height_percent + "%";
        img.style.objectFit = "contain";

        overlay.appendChild(img);
        return;
      }

      // 🔹 ELSE render editable box
      const box = create_box(frm);

      box.style.left = field.x_percent + "%";
      box.style.top = field.y_percent + "%";
      box.style.width = field.width_percent + "%";
      box.style.height = field.height_percent + "%";

      box.dataset.rowname = field.name;
      box.dataset.signer_email = field.signer_email;

      overlay.appendChild(box);
      attach_box_events(frm, box, overlay);

    });

  }, 400);
}

