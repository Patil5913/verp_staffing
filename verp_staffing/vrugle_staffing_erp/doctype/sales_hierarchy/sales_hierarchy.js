// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt


// frappe.ui.form.on("Sales Hierarchy", {
//     refresh(frm) {
//         render_role_table_html(frm);
//         init_role_table(frm);
//     },
// });

// function render_role_table_html(frm) {
//     let html = `
//         <div id="role-table-wrapper">
//             <table class="table table-bordered" id="role-table">
//                 <thead>
//                     <tr>
//                         <th>Parent Role</th>
//                         <th>Child Roles</th>
//                     </tr>
//                 </thead>
//                 <tbody></tbody>
//             </table>

//             <button class="btn btn-primary" id="add-row-btn">Add Row</button>
//         </div>
//     `;

//     // Inject HTML into your HTML field
//     frm.get_field("role_table_html").$wrapper.html(html);
// }


// function init_role_table(frm) {

//     // Load existing json
//     let data = frm.doc.hierarchy_json ? JSON.parse(frm.doc.hierarchy_json) : [];

//     $("#add-row-btn").off("click").on("click", function () {
//         add_row(frm, null);
//     });

//     $("#role-table tbody").empty();
//     data.forEach(row => {
//         add_row(frm, row);
//     });
// }


// function add_row(frm, rowData) {
//     let row_id = frappe.utils.get_random(8);

//     let tr = $(`
//         <tr data-id="${row_id}">
//             <td><div class="parent-role-container"></div></td>
//             <td><div class="child-role-container"></div></td>
//             <td><button class="btn btn-danger delete-row">X</button></td>
//         </tr>
//     `);

//     $("#role-table tbody").append(tr);

//     let parent_container = tr.find(".parent-role-container");
//     let child_container = tr.find(".child-role-container");

//     // Parent Role control
//     let parent_control = frappe.ui.form.make_control({
//         parent: parent_container,
//         df: {
//             fieldtype: "Link",
//             placeholder: "Choose Parent Role",
//             options: "Role"
//         },
//         render_input: true
//     });

//     parent_control.set_value(rowData ? rowData.parent_role : null);
//     parent_container.data("control", parent_control);

//     // REAL event binding (correct one)
//     parent_control.$input.on("change input", () => {
//         save_table_to_json(frm);
//     });

//     // Child Roles (Table MultiSelect)
//     let child_control = frappe.ui.form.make_control({
//         parent: child_container,
//         df: {
//             fieldtype: "Table MultiSelect",
//             placeholder: "Choose Child Roles",
//             options: "Child Roles"
//         },
//         render_input: true
//     });

//     child_control.set_value(rowData ? rowData.child_roles : []);
//     child_container.data("control", child_control);

//     // detect selection
//     child_control.$input.on("awesomplete-selectcomplete", () => {
//         save_table_to_json(frm);
//     });

//     // detect typing
//     child_control.$input.on("change input", () => {
//         save_table_to_json(frm);
//     });

//     // detect chip removal using MutationObserver
//     const observer = new MutationObserver(() => {
//         save_table_to_json(frm);
//     });

//     observer.observe(child_container[0], {
//         childList: true,
//         subtree: true
//     });


//     // delete row
//     tr.find(".delete-row").on("click", function () {
//         tr.remove();
//         save_table_to_json(frm);
//     });

//     // initial sync
//     save_table_to_json(frm);
// }


// function save_table_to_json(frm) {
//     let data = [];

//     $("#role-table tbody tr").each(function () {
//         let row = $(this);

//         let parent_control = row.find(".parent-role-container").data("control");
//         let child_control = row.find(".child-role-container").data("control");

//         if (!parent_control) return;

//         let parent = parent_control.get_value() || "";

//         // Table MultiSelect returns array of child table rows
//         let children = [];
//         if (child_control && child_control.get_value()) {
//             children = child_control.get_value().map(d => d.role);
//         }

//         if (parent) {
//             data.push({
//                 parent_role: parent,
//                 child_roles: children
//             });
//         }
//     });

//     frm.set_value("role_hierarchy_json", JSON.stringify(data));
// }




// frappe.ui.form.on("Sales Hierarchy", {
//     refresh(frm) {
//         render_role_table_html(frm);
//         init_role_table(frm);
//         render_hierarchy_diagram(frm);
//     },

//     role_hierarchy_json(frm) {
//         render_hierarchy_diagram(frm);
//     },

//     validate(frm) {
//         let data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];

//         for (let row of data) {
//             if (!row.parent_role || row.child_roles.length === 0) {
//                 frappe.throw("Every row must have a parent role and at least one child role before saving.");
//             }
//         }
//     },
// });

// function render_role_table_html(frm) {
//     let html = `
//         <div id="role-table-wrapper">
//             <table class="table table-bordered" id="role-table">
//                 <thead>
//                     <tr>
//                         <th>Parent Role</th>
//                         <th>Child Roles</th>
//                         <th>Action</th>
//                     </tr>
//                 </thead>
//                 <tbody></tbody>
//             </table>

//             <button class="btn btn-primary" id="add-row-btn">Add Row</button>
//         </div>
//         <div id="hierarchy-tree-wrapper" style="margin-top:20px;"></div>
//     `;

//     frm.get_field("role_table_html").$wrapper.html(html);
// }

// function init_role_table(frm) {
//     let data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];

//     $("#add-row-btn").off("click").on("click", function () {
//         add_row(frm, null);
//     });

//     $("#role-table tbody").empty();
//     data.forEach(row => add_row(frm, row));
// }

// function add_row(frm, rowData) {
//     let row_id = frappe.utils.get_random(8);

//     let tr = $(`
//         <tr data-id="${row_id}">
//             <td><div class="parent-role-container"></div></td>
//             <td><div class="child-role-container"></div></td>
//             <td><button class="btn btn-danger delete-row">X</button></td>
//         </tr>
//     `);

//     $("#role-table tbody").append(tr);

//     let parent_container = tr.find(".parent-role-container");
//     let child_container = tr.find(".child-role-container");

//     // Parent Role control
//     let parent_control = frappe.ui.form.make_control({
//         parent: parent_container,
//         df: {
//             fieldtype: "Link",
//             placeholder: "Choose Parent Role",
//             options: "Role"
//         },
//         render_input: true
//     });

//     parent_control.set_value(rowData ? rowData.parent_role : "");
//     parent_container.data("control", parent_control);

//     parent_control.$input.on("change input", () => {
//         save_table_to_json(frm);
//     });

//     // Child Roles (Table MultiSelect)
//     let child_control = frappe.ui.form.make_control({
//         parent: child_container,
//         df: {
//             fieldtype: "Table MultiSelect",
//             placeholder: "Choose Child Roles",
//             options: "Child Roles"
//         },
//         render_input: true
//     });

//     child_control.set_value(rowData ? rowData.child_roles : []);
//     child_container.data("control", child_control);

//     // Events
//     child_control.$input.on("awesomplete-selectcomplete change input", () => {
//         save_table_to_json(frm);
//     });

//     // Detect chip removal
//     new MutationObserver(() => save_table_to_json(frm)).observe(child_container[0], {
//         childList: true,
//         subtree: true
//     });

//     // Delete row
//     tr.find(".delete-row").on("click", function () {
//         tr.remove();
//         save_table_to_json(frm);
//     });

//     save_table_to_json(frm);
// }

// function save_table_to_json(frm) {
//     let data = [];

//     $("#role-table tbody tr").each(function () {
//         let row = $(this);

//         let parent_control = row.find(".parent-role-container").data("control");
//         let child_control = row.find(".child-role-container").data("control");

//         if (!parent_control) return;

//         let parent = parent_control.get_value() || "";
//         let children = [];

//         if (child_control && child_control.get_value()) {
//             children = child_control.get_value().map(d => d.role);
//         }

//         // DO NOT validate during typing
//         // Only store valid rows (both fields non-empty)
//         // Ignore incomplete rows safely during editing
//         // store all rows including incomplete ones - needed for validation
//         data.push({
//             parent_role: parent,
//             child_roles: children
//         });

//     });

//     // soft validation only for UI, do not block typing
//     for (let r of data) {
//         if ((r.parent_role && r.child_roles.length === 0) || (!r.parent_role && r.child_roles.length > 0)) {
//             frm.set_df_property("hierarchy_diagram", "options",
//                 `<div style="color:red;font-weight:bold">Each row needs both parent and child roles.</div>`
//             );
//             return;
//         }
//     }


//     frm.set_value("role_hierarchy_json", JSON.stringify(data));
//     frm.dirty();
//     render_hierarchy_diagram(frm);
// }


// function detect_sibling_child_conflicts(data) {
//     let conflicts = [];

//     for (let row of data) {
//         let parent = row.parent_role;
//         let siblings = [];

//         // find siblings
//         data.forEach(r => {
//             if (r !== row && r.parent_role === parent) {
//                 siblings.push(...r.child_roles);
//             }
//         });

//         // check if siblings appear also as children in the same row
//         row.child_roles.forEach(child => {
//             if (siblings.includes(child)) {
//                 conflicts.push({
//                     parent,
//                     child,
//                 });
//             }
//         });
//     }

//     return conflicts;
// }



// function render_hierarchy_diagram(frm) {
//     let wrapper = frm.get_field("hierarchy_diagram").$wrapper;
//     wrapper.empty();

//     let data = [];
//     try {
//         data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];
//     } catch {
//         wrapper.html(`<div style="color:red">Invalid JSON</div>`);
//         return;
//     }

//     if (!data.length) {
//         wrapper.html(`<div style="color:#888">No hierarchy defined</div>`);
//         return;
//     }

//     let graph = build_hierarchy_tree(data);
//     let roots = find_roots(data);
//     let cycle = detect_cycle(graph);

//     let sibling_conflicts = detect_sibling_child_conflicts(data);
//     if (sibling_conflicts.length) {
//         let msg = sibling_conflicts
//             .map(c => `${c.child} appears both as a child and a sibling under ${c.parent}`)
//             .join("<br>");

//         wrapper.html(
//             `<div style="color:red;font-weight:bold;padding:10px;">
//             Invalid Hierarchy.<br>${msg}
//         </div>`
//         );
//         return;
//     }


//     if (cycle) {
//         wrapper.html(`
//             <div style="color:red;font-weight:bold;padding:10px;">
//                 Error: Hierarchy contains a loop involving role <b>${cycle}</b>.<br>
//                 Remove the circular relationship to display the hierarchy.
//             </div>
//         `);
//         return;
//     }

//     // No cycles, render the tree
//     function render_node(node) {
//         let children = graph[node] || [];
//         let html = `<li>${node}`;

//         if (children.length) {
//             html += `<ul>`;
//             children.forEach(c => {
//                 html += render_node(c);
//             });
//             html += `</ul>`;
//         }

//         html += `</li>`;
//         return html;
//     }

//     let html = `<div class="role-tree"><ul>`;
//     roots.forEach(r => {
//         html += render_node(r);
//     });
//     html += `</ul></div>`;

//     wrapper.html(html);

//     // basic clean vertical style
//     wrapper.find(".role-tree ul").css({
//         "list-style": "none",
//         "padding-left": "20px",
//         "margin": "4px 0"
//     });

//     wrapper.find(".role-tree li").css({
//         "margin": "4px 0",
//         "padding": "4px 8px",
//         "border": "1px solid #aaa",
//         "border-radius": "6px",
//         "display": "inline-block",
//         "background": "#f7f7f7"
//     });
// }


// function build_hierarchy_tree(data) {
//     let graph = {};

//     data.forEach(r => {
//         if (!graph[r.parent_role]) graph[r.parent_role] = [];
//         graph[r.parent_role].push(...r.child_roles);
//     });

//     return graph;
// }

// // find root nodes: parent that is never a child
// function find_roots(data) {
//     let parents = new Set(data.map(d => d.parent_role));
//     let children = new Set(data.flatMap(d => d.child_roles));
//     let roots = [...parents].filter(p => !children.has(p));
//     return roots;
// }

// // detect cycles using DFS
// function detect_cycle(graph) {
//     let visited = new Set();
//     let stack = new Set();

//     function dfs(node) {
//         if (stack.has(node)) {
//             return node;         // cycle detected
//         }
//         if (visited.has(node)) return null;

//         visited.add(node);
//         stack.add(node);

//         let children = graph[node] || [];
//         for (let c of children) {
//             let result = dfs(c);
//             if (result) return result;
//         }

//         stack.delete(node);
//         return null;
//     }

//     for (let node in graph) {
//         let result = dfs(node);
//         if (result) return result;
//     }

//     return null;
// }




// frappe.ui.form.on("Sales Hierarchy", {
//     refresh(frm) {
//         render_role_table_html(frm);
//         init_role_table(frm);
//         render_hierarchy_diagram(frm);
//     },

//     role_hierarchy_json(frm) {
//         render_hierarchy_diagram(frm);
//     },

//     validate(frm) {
//         let data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];

//         for (let row of data) {
//             if (!row.parent_role || row.child_roles.length === 0) {
//                 frappe.throw("Every row must have a parent role and at least one child role before saving.");
//             }
//         }
//     },
// });

// function render_role_table_html(frm) {
//     let html = `
//         <div id="role-table-wrapper">
//             <table class="table table-bordered" id="role-table">
//                 <thead>
//                     <tr>
//                         <th>Parent Role</th>
//                         <th>Child Roles</th>
//                         <th>Action</th>
//                     </tr>
//                 </thead>
//                 <tbody></tbody>
//             </table>

//             <button class="btn btn-primary" id="add-row-btn">Add Row</button>
//         </div>
//         <div id="hierarchy-tree-wrapper" style="margin-top:20px;"></div>
//     `;

//     frm.get_field("role_table_html").$wrapper.html(html);
// }

// function init_role_table(frm) {
//     let data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];

//     $("#add-row-btn").off("click").on("click", function () {
//         add_row(frm, null);
//     });

//     $("#role-table tbody").empty();
//     data.forEach(row => add_row(frm, row));
// }

// function add_row(frm, rowData) {
//     let row_id = frappe.utils.get_random(8);

//     let tr = $(`
//         <tr data-id="${row_id}">
//             <td><div class="parent-role-container"></div></td>
//             <td><div class="child-role-container"></div></td>
//             <td><button class="btn btn-danger delete-row">X</button></td>
//         </tr>
//     `);

//     $("#role-table tbody").append(tr);

//     let parent_container = tr.find(".parent-role-container");
//     let child_container = tr.find(".child-role-container");

//     // Parent Role control
//     let parent_control = frappe.ui.form.make_control({
//         parent: parent_container,
//         df: {
//             fieldtype: "Link",
//             placeholder: "Choose Parent Role",
//             options: "Role"
//         },
//         render_input: true
//     });

//     parent_control.set_value(rowData ? rowData.parent_role : "");
//     parent_container.data("control", parent_control);

//     parent_control.$input.on("change input", () => {
//         save_table_to_json(frm);
//     });

//     // Child Roles (Table MultiSelect)
//     let child_control = frappe.ui.form.make_control({
//         parent: child_container,
//         df: {
//             fieldtype: "Table MultiSelect",
//             placeholder: "Choose Child Roles",
//             options: "Child Roles"
//         },
//         render_input: true
//     });

//     child_control.set_value(rowData ? rowData.child_roles : []);
//     child_container.data("control", child_control);

//     // Events
//     child_control.$input.on("awesomplete-selectcomplete change input", () => {
//         save_table_to_json(frm);
//     });

//     // Detect chip removal
//     new MutationObserver(() => save_table_to_json(frm)).observe(child_container[0], {
//         childList: true,
//         subtree: true
//     });

//     // Delete row
//     tr.find(".delete-row").on("click", function () {
//         tr.remove();
//         save_table_to_json(frm);
//     });

//     save_table_to_json(frm);
// }

// function save_table_to_json(frm) {
//     let data = [];

//     $("#role-table tbody tr").each(function () {
//         let row = $(this);

//         let parent_control = row.find(".parent-role-container").data("control");
//         let child_control = row.find(".child-role-container").data("control");

//         if (!parent_control) return;

//         let parent = parent_control.get_value() || "";
//         let children = [];

//         if (child_control && child_control.get_value()) {
//             children = child_control.get_value().map(d => d.role);
//         }

//         // DO NOT validate during typing
//         // Only store valid rows (both fields non-empty)
//         // Ignore incomplete rows safely during editing
//         // store all rows including incomplete ones - needed for validation
//         data.push({
//             parent_role: parent,
//             child_roles: children
//         });

//     });

//     // soft validation only for UI, do not block typing
//     for (let r of data) {
//         if ((r.parent_role && r.child_roles.length === 0) || (!r.parent_role && r.child_roles.length > 0)) {
//             frm.set_df_property("hierarchy_diagram", "options",
//                 `<div style="color:red;font-weight:bold">Each row needs both parent and child roles.</div>`
//             );
//             return;
//         }
//     }


//     frm.set_value("role_hierarchy_json", JSON.stringify(data));
//     frm.dirty();
//     render_hierarchy_diagram(frm);
// }


// function detect_sibling_child_conflicts(data) {
//     let conflicts = [];

//     for (let row of data) {
//         let parent = row.parent_role;
//         let siblings = [];

//         // find siblings
//         data.forEach(r => {
//             if (r !== row && r.parent_role === parent) {
//                 siblings.push(...r.child_roles);
//             }
//         });

//         // check if siblings appear also as children in the same row
//         row.child_roles.forEach(child => {
//             if (siblings.includes(child)) {
//                 conflicts.push({
//                     parent,
//                     child,
//                 });
//             }
//         });
//     }

//     return conflicts;
// }



// function render_hierarchy_diagram(frm) {
//     let wrapper = frm.get_field("hierarchy_diagram").$wrapper;
//     wrapper.empty();

//     let data = [];
//     try {
//         data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];
//     } catch {
//         wrapper.html(`<div style="color:red">Invalid JSON</div>`);
//         return;
//     }

//     if (!data.length) {
//         wrapper.html(`<div style="color:#888">No hierarchy defined</div>`);
//         return;
//     }

//     let graph = build_hierarchy_tree(data);
//     let roots = find_roots(data);

//     let cycle = detect_cycle(graph);
//     if (cycle) {
//         wrapper.html(`
//             <div style="color:red;font-weight:bold;padding:10px;">
//                 Cycle detected at role ${cycle}
//             </div>
//         `);
//         return;
//     }

//     let conflicts = detect_sibling_child_conflicts(data);
//     if (conflicts.length) {
//         let msg = conflicts.map(c =>
//             `${c.child} cannot be both child and sibling under ${c.parent}`
//         ).join("<br>");
//         wrapper.html(`
//             <div style="color:red;font-weight:bold;padding:10px;">${msg}</div>
//         `);
//         return;
//     }

//     // Build nodes list
//     let nodes = [];
//     let edges = [];

//     let allRoles = new Set();
//     data.forEach(r => {
//         allRoles.add(r.parent_role);
//         r.child_roles.forEach(c => allRoles.add(c));
//     });

//     allRoles.forEach(role => {
//         nodes.push({ id: role, label: role });
//     });

//     data.forEach(r => {
//         r.child_roles.forEach(c => {
//             edges.push({ from: r.parent_role, to: c });
//         });
//     });

//     let html = `
//     <style>
//         .hier-tree-node {
//             padding: 6px 12px;
//             border: 1px solid #444;
//             border-radius: 6px;
//             background: #f2f2f2;
//             display: inline-block;
//             margin: 6px;
//         }
//     </style>
//     <svg id="role-svg" width="100%" height="600"></svg>
//     `;

//     wrapper.html(html);

//     drawTreeWithArrows(nodes, edges);
// }


// function drawTreeWithArrows(nodes, edges) {
//     let svg = document.getElementById("role-svg");
//     let spacingX = 200;
//     let spacingY = 100;

//     // simple layered layout: root top, children below
//     let levels = {};
//     let assigned = new Set();

//     // find roots
//     let roots = nodes.filter(n =>
//         !edges.some(e => e.to === n.id)
//     );

//     roots.forEach(root => placeNode(root.id, 0));

//     function placeNode(id, level) {
//         if (assigned.has(id)) return;
//         assigned.add(id);

//         if (!levels[level]) levels[level] = [];
//         levels[level].push(id);

//         edges.filter(e => e.from === id).forEach(e => {
//             placeNode(e.to, level + 1);
//         });
//     }

//     // draw nodes
//     let nodePositions = {};

//     Object.keys(levels).forEach(level => {
//         let items = levels[level];
//         items.forEach((id, idx) => {
//             let x = (idx + 1) * spacingX;
//             let y = level * spacingY + 40;

//             nodePositions[id] = { x, y };

//             let g = document.createElementNS("http://www.w3.org/2000/svg", "g");
//             g.innerHTML = `
//                 <rect x="${x - 60}" y="${y - 20}" width="120" height="40"
//                       rx="6" ry="6" fill="#f8f8f8" stroke="#333"/>
//                 <text x="${x}" y="${y + 4}" text-anchor="middle" font-size="14">${id}</text>
//             `;
//             svg.appendChild(g);
//         });
//     });

//     // draw arrows
//     edges.forEach(e => {
//         let p1 = nodePositions[e.from];
//         let p2 = nodePositions[e.to];

//         let line = document.createElementNS("http://www.w3.org/2000/svg", "line");
//         line.setAttribute("x1", p1.x);
//         line.setAttribute("y1", p1.y + 20);
//         line.setAttribute("x2", p2.x);
//         line.setAttribute("y2", p2.y - 20);
//         line.setAttribute("stroke", "#333");
//         line.setAttribute("marker-end", "url(#arrow)");

//         svg.appendChild(line);
//     });

//     // define arrow head
//     let defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
//     defs.innerHTML = `
//         <marker id="arrow" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto">
//             <path d="M0,0 L0,6 L9,3 z" fill="#333"/>
//         </marker>
//     `;
//     svg.appendChild(defs);
// }



// function build_hierarchy_tree(data) {
//     let graph = {};

//     data.forEach(r => {
//         if (!graph[r.parent_role]) graph[r.parent_role] = [];
//         graph[r.parent_role].push(...r.child_roles);
//     });

//     return graph;
// }

// // find root nodes: parent that is never a child
// function find_roots(data) {
//     let parents = new Set(data.map(d => d.parent_role));
//     let children = new Set(data.flatMap(d => d.child_roles));
//     let roots = [...parents].filter(p => !children.has(p));
//     return roots;
// }

// // detect cycles using DFS
// function detect_cycle(graph) {
//     let visited = new Set();
//     let stack = new Set();

//     function dfs(node) {
//         if (stack.has(node)) {
//             return node;         // cycle detected
//         }
//         if (visited.has(node)) return null;

//         visited.add(node);
//         stack.add(node);

//         let children = graph[node] || [];
//         for (let c of children) {
//             let result = dfs(c);
//             if (result) return result;
//         }

//         stack.delete(node);
//         return null;
//     }

//     for (let node in graph) {
//         let result = dfs(node);
//         if (result) return result;
//     }

//     return null;
// }


// function detect_sibling_child_conflicts(data) {
//     let conflicts = [];

//     // Build parent -> children map
//     let parentMap = {};
//     data.forEach(r => {
//         parentMap[r.parent_role] = r.child_roles;
//     });

//     data.forEach(row => {
//         let parent = row.parent_role;
//         let ownChildren = row.child_roles;

//         // siblings = all other children under same parent
//         let siblings = parentMap[parent]?.filter(c => !ownChildren.includes(c)) || [];

//         ownChildren.forEach(child => {
//             if (siblings.includes(child)) {
//                 conflicts.push({
//                     parent,
//                     child
//                 });
//             }
//         });
//     });

//     return conflicts;
// }


// Updated Sales Hierarchy JS - full file
// Behavior: single unique node per role, parent centered, children spread left/right,
// auto-shift siblings to avoid overlap, single root enforced (with [Start] virtual root)

// frappe.ui.form.on("Sales Hierarchy", {
//     refresh(frm) {
//         render_role_table_html(frm);
//         init_role_table(frm);
//         render_hierarchy_diagram(frm);
//     },

//     role_hierarchy_json(frm) {
//         render_hierarchy_diagram(frm);
//     },

//     before_save(frm) {
//         const table_data = [];

//         // read values from your HTML table
//         $(".role-row").each(function() {
//             const parent = $(this).find(".parent-role").val();
//             const children = $(this).find(".child-roles").val() || [];

//             table_data.push({
//                 parent_role: parent,
//                 child_roles: children
//             });
//         });

//         // now push this into actual field so Frappe saves it
//         frm.set_value("role_hierarchy_json", JSON.stringify(table_data));
//     }
// });

// function render_role_table_html(frm) {
//     let html = `
//         <div id="role-table-wrapper">
//             <table class="table table-bordered" id="role-table">
//                 <thead>
//                     <tr>
//                         <th>Parent Role</th>
//                         <th>Child Roles</th>
//                         <th>Action</th>
//                     </tr>
//                 </thead>
//                 <tbody></tbody>
//             </table>

//             <button class="btn btn-primary" id="add-row-btn">Add Row</button>
//         </div>
//         <div id="hierarchy-tree-wrapper" style="margin-top:20px;"></div>
//     `;

//     frm.get_field("role_table_html").$wrapper.html(html);
// }

// function init_role_table(frm) {
//     let data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];

//     $("#add-row-btn").off("click").on("click", function () {
//         add_row(frm, null);
//     });

//     $("#role-table tbody").empty();
//     data.forEach(row => add_row(frm, row));
// }

// function add_row(frm, rowData) {
//     let row_id = frappe.utils.get_random(8);

//     let tr = $(`
//         <tr data-id="${row_id}">
//             <td><div class="parent-role-container"></div></td>
//             <td><div class="child-role-container"></div></td>
//             <td><button class="btn btn-danger delete-row">X</button></td>
//         </tr>
//     `);

//     $("#role-table tbody").append(tr);

//     let parent_container = tr.find(".parent-role-container");
//     let child_container = tr.find(".child-role-container");

//     // Parent Role control
//     let parent_control = frappe.ui.form.make_control({
//         parent: parent_container,
//         df: {
//             fieldtype: "Link",
//             placeholder: "Choose Parent Role",
//             options: "Role"
//         },
//         render_input: true
//     });

//     parent_control.set_value(rowData ? rowData.parent_role : "");
//     parent_container.data("control", parent_control);

//     parent_control.$input.on("change input", () => {
//         save_table_to_json(frm);
//     });

//     // Child Roles (Table MultiSelect)
//     let child_control = frappe.ui.form.make_control({
//         parent: child_container,
//         df: {
//             fieldtype: "Table MultiSelect",
//             placeholder: "Choose Child Roles",
//             options: "Child Roles"
//         },
//         render_input: true
//     });

//     child_control.set_value(rowData ? rowData.child_roles : []);
//     child_container.data("control", child_control);

//     // Events
//     child_control.$input.on("awesomplete-selectcomplete change input", () => {
//         save_table_to_json(frm);
//     });

//     // Detect chip removal
//     new MutationObserver(() => save_table_to_json(frm)).observe(child_container[0], {
//         childList: true,
//         subtree: true
//     });

//     // Delete row
//     tr.find(".delete-row").on("click", function () {
//         tr.remove();
//         save_table_to_json(frm);
//     });

//     save_table_to_json(frm);
// }

// function save_table_to_json(frm) {
//     let data = [];

//     $("#role-table tbody tr").each(function () {
//         let row = $(this);

//         let parent_control = row.find(".parent-role-container").data("control");
//         let child_control = row.find(".child-role-container").data("control");

//         if (!parent_control) return;

//         let parent = parent_control.get_value() || "";
//         let children = [];

//         if (child_control && child_control.get_value()) {
//             children = child_control.get_value().map(d => d.role);   // FIXED
//         }

//         data.push({
//             parent_role: parent,
//             child_roles: children
//         });
//     });

//     frm.set_value("role_hierarchy_json", JSON.stringify(data));
//     frm.dirty();
//     render_hierarchy_diagram(frm);
// }

frappe.ui.form.on("Sales Hierarchy", {
    refresh(frm) {
        // Only render if wrapper is empty or force re-render is needed
        if (!frm.get_field("role_table_html").$wrapper.find("#role-table-wrapper").length) {
            render_role_table_html(frm);
        }
        init_role_table(frm);
        render_hierarchy_diagram(frm);
    },

    role_hierarchy_json(frm) {
        render_hierarchy_diagram(frm);
    },

    before_save(frm) {
        // Don't call save_table_to_json here - data should already be in role_hierarchy_json
        // The real-time updates handle this
        
        // Validate that we have data
        if (!frm.doc.role_hierarchy_json) {
            frappe.msgprint(__("Please add at least one role hierarchy"));
            frappe.validated = false;
        }
    }
});

function render_role_table_html(frm) {
    let html = `
        <div id="role-table-wrapper">
            <table class="table table-bordered" id="role-table">
                <thead>
                    <tr>
                        <th>Parent Role</th>
                        <th>Child Roles</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>

            <button class="btn btn-primary" id="add-row-btn">Add Row</button>
        </div>
        <div id="hierarchy-tree-wrapper" style="margin-top:20px;"></div>
    `;

    // Only set HTML if not already present
    let wrapper = frm.get_field("role_table_html").$wrapper;
    if (!wrapper.find("#role-table-wrapper").length) {
        wrapper.html(html);
    }
}

function init_role_table(frm) {
    let data = [];
    try {
        data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];
    } catch (e) {
        console.error("Error parsing role_hierarchy_json:", e);
        data = [];
    }

    // Set up add button handler
    $("#add-row-btn").off("click").on("click", function () {
        add_row(frm, null);
    });

    // Clear and rebuild table
    $("#role-table tbody").empty();
    
    // Add rows from saved data
    if (data.length > 0) {
        data.forEach(row => add_row(frm, row));
    } else {
        // Add one empty row if no data
        add_row(frm, null);
    }
}

function add_row(frm, rowData) {
    let row_id = frappe.utils.get_random(8);

    let tr = $(`
        <tr data-id="${row_id}" class="role-row">
            <td><div class="parent-role-container"></div></td>
            <td><div class="child-role-container"></div></td>
            <td><button class="btn btn-danger btn-sm delete-row">Delete</button></td>
        </tr>
    `);

    $("#role-table tbody").append(tr);

    let parent_container = tr.find(".parent-role-container");
    let child_container = tr.find(".child-role-container");

    // Parent Role control
    let parent_control = frappe.ui.form.make_control({
        parent: parent_container,
        df: {
            fieldtype: "Link",
            fieldname: "parent_role_" + row_id,
            placeholder: "Choose Parent Role",
            options: "Role"
        },
        render_input: true
    });

    // Set value after control is rendered
    setTimeout(() => {
        if (rowData && rowData.parent_role) {
            parent_control.set_value(rowData.parent_role);
        }
    }, 100);
    
    parent_container.data("control", parent_control);

    // Save on change
    parent_control.$input.on("change", () => {
        setTimeout(() => save_table_to_json(frm), 150);
    });

    // Child Roles (Table MultiSelect)
    let child_control = frappe.ui.form.make_control({
        parent: child_container,
        df: {
            fieldtype: "Table MultiSelect",
            fieldname: "child_roles_" + row_id,
            placeholder: "Choose Child Roles",
            options: "Child Roles"
        },
        render_input: true
    });

    // Set value after control is rendered
    setTimeout(() => {
        if (rowData && rowData.child_roles && rowData.child_roles.length > 0) {
            child_control.set_value(rowData.child_roles);
        }
    }, 100);
    
    child_container.data("control", child_control);

    // Events for child control
    child_control.$input.on("awesomplete-selectcomplete", () => {
        setTimeout(() => save_table_to_json(frm), 150);
    });

    // Detect chip removal using MutationObserver
    let observer = new MutationObserver(() => {
        setTimeout(() => save_table_to_json(frm), 150);
    });
    
    observer.observe(child_container[0], {
        childList: true,
        subtree: true
    });

    // Store observer reference for cleanup
    tr.data("observer", observer);

    // Delete row
    tr.find(".delete-row").on("click", function () {
        // Disconnect observer before removing
        let obs = tr.data("observer");
        if (obs) obs.disconnect();
        
        tr.remove();
        setTimeout(() => save_table_to_json(frm), 150);
    });
}

function save_table_to_json(frm) {
    // Prevent saving during form save operation
    if (frm.is_dirty() === undefined || frm.doc.__unsaved) {
        return;
    }

    let data = [];

    $("#role-table tbody tr.role-row").each(function () {
        let row = $(this);

        let parent_control = row.find(".parent-role-container").data("control");
        let child_control = row.find(".child-role-container").data("control");

        if (!parent_control) return;

        let parent = parent_control.get_value() || "";
        
        // Skip empty rows
        if (!parent) return;

        let children = [];
       if (child_control) {
            // Use _rows_list - it's the most reliable for Table MultiSelect
            if (child_control._rows_list && Array.isArray(child_control._rows_list)) {
                children = [...child_control._rows_list]; // Create a copy
            }
            // Fallback to value property
            else if (child_control.value && Array.isArray(child_control.value)) {
                children = child_control.value.map(d => d.role || d).filter(Boolean);
            }
            // Last fallback to last_value
            else if (child_control.last_value && Array.isArray(child_control.last_value)) {
                children = child_control.last_value.map(d => d.role || d).filter(Boolean);
            }
        }

        console.log("Parent:", parent, "Children:", children);


        data.push({
            parent_role: parent,
            child_roles: children
        });
    });

    // Only update if data has changed
    let currentJson = frm.doc.role_hierarchy_json || "[]";
    let newJson = JSON.stringify(data);
    
    if (currentJson !== newJson) {
        frm.set_value("role_hierarchy_json", newJson);
        render_hierarchy_diagram(frm);
    }
}

// ... rest of your code remains the same ...



// conflict detection improved
function detect_sibling_child_conflicts(data) {
    let conflicts = [];

    // Build parent -> all children list (flatten)
    let parentMap = {};
    data.forEach(r => {
        parentMap[r.parent_role] = parentMap[r.parent_role] || [];
        parentMap[r.parent_role].push(...(r.child_roles || []));
    });

    // For each parent, check duplicates across rows for same parent
    data.forEach(row => {
        let parent = row.parent_role;
        let ownChildren = row.child_roles || [];

        // siblings under same parent are any children listed for that parent except own children from same row
        let siblings = (parentMap[parent] || []).filter(c => !ownChildren.includes(c));

        ownChildren.forEach(child => {
            if (siblings.includes(child)) {
                conflicts.push({ parent, child });
            }
        });
    });

    return conflicts;
}



// render with single unique node per role
function render_hierarchy_diagram(frm) {
    let wrapper = frm.get_field("hierarchy_diagram").$wrapper;
    wrapper.empty();

    let data = [];
    try {
        data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];
    } catch {
        wrapper.html(`<div style="color:red">Invalid JSON</div>`);
        return;
    }

    if (!data.length) {
        wrapper.html(`<div style="color:#888">No hierarchy defined</div>`);
        return;
    }

    // strict single-root rule: find_roots returns parents that are not children
    let roots = find_roots(data);
    if (roots.length === 0) {
        wrapper.html(`<div style="color:red;font-weight:bold;padding:10px;">Error: No root found.</div>`);
        return;
    }
    // if (roots.length > 1) {
    //     wrapper.html(`<div style="color:red;font-weight:bold;padding:10px;">Error: Only one root role is allowed. Found: ${roots.join(", ")}</div>`);
    //     return;
    // }

    // conflict detection
    let conflicts = detect_sibling_child_conflicts(data);
    if (conflicts.length) {
        let msg = conflicts.map(c => `${c.child} cannot be both child and sibling under ${c.parent}`).join("<br>");
        wrapper.html(`<div style="color:red;font-weight:bold;padding:10px;">${msg}</div>`);
        return;
    }

    // build graph
    let graph = build_hierarchy_tree(data);
    let cycle = detect_cycle(graph);
    if (cycle) {
        wrapper.html(`<div style="color:red;font-weight:bold;padding:10px;">Cycle detected at role ${cycle}</div>`);
        return;
    }

    // Build nodes and edges
    let allRoles = new Set();
    data.forEach(r => {
        allRoles.add(r.parent_role);
        (r.child_roles || []).forEach(c => allRoles.add(c));
    });

    // create node objects
    let nodes = [...allRoles].map(role => ({ id: role, label: role }));

    // edges
    let edges = [];
    data.forEach(r => {
        (r.child_roles || []).forEach(c => {
            edges.push({ from: r.parent_role, to: c });
        });
    });

    // Add virtual [Start] node and connect to root
    nodes.unshift({ id: "[Start]", label: "[Start]" });
    let root = roots[0];
    edges.push({ from: "[Start]", to: root });

    // Prepare html and svg
    let html = `
    <style>
        .hier-tree-node {
            padding: 6px 12px;
            border: 1px solid #444;
            border-radius: 6px;
            background: #f2f2f2;
            display: inline-block;
            margin: 6px;
            font-family: Arial, sans-serif;
        }
        .hier-wrapper {
            overflow: auto;
        }
    </style>
    <div class="hier-wrapper">
        <svg id="role-svg" width="1200" height="600"></svg>
    </div>
    `;

    wrapper.html(html);

    drawTreeWithArrowsUnique(nodes, edges);
}


// Layout engine that produces unique node positions,
// parents roughly centered over their children, children alternate left/right,
// and a collision resolver shifts nodes horizontally to maintain minimum spacing.
function drawTreeWithArrowsUnique(nodes, edges) {
    const svg = document.getElementById("role-svg");
    svg.innerHTML = "";

    const minSpacingX = 180;    // minimum horizontal spacing between nodes
    const spacingY = 120;       // vertical spacing between levels
    const marginX = 40;
    const marginY = 40;

    // Build maps
    let childrenMap = {};
    let parentMap = {};
    nodes.forEach(n => {
        childrenMap[n.id] = [];
        parentMap[n.id] = [];
    });
    edges.forEach(e => {
        // guard against duplicated edges
        if (!childrenMap[e.from].includes(e.to)) childrenMap[e.from].push(e.to);
        if (!parentMap[e.to].includes(e.from)) parentMap[e.to].push(e.from);
    });

    // BFS to compute levels from [Start]
    let levels = {};
    let nodeLevel = {};
    let queue = [{ id: "[Start]", level: 0 }];
    let visited = new Set();

    while (queue.length) {
        let { id, level } = queue.shift();
        if (visited.has(id)) continue;
        visited.add(id);
        nodeLevel[id] = level;
        if (!levels[level]) levels[level] = [];
        levels[level].push(id);

        (childrenMap[id] || []).forEach(child => {
            if (!visited.has(child)) queue.push({ id: child, level: level + 1 });
        });
    }

    // Ensure svg height fits levels
    let levelCount = Object.keys(levels).length;
    svg.setAttribute("height", Math.max(300, (levelCount + 1) * spacingY + marginY));

    // initial x assignment
    // center [Start] at centerX
    const svgWidth = svg.clientWidth || 1200;
    let nodePos = {}; // id -> {x, y}

    // assign [Start] center
    const centerX = Math.floor(svgWidth / 2);
    if (levels[0] && levels[0].includes("[Start]")) {
        nodePos["[Start]"] = { x: centerX, y: marginY + 20 };
    }

    // For levels > 0, compute initial desired x as average of parents x if possible,
    // else assign sequentially from left to right.
    let maxLevel = Math.max(...Object.keys(levels).map(k => parseInt(k)));
    for (let lvl = 1; lvl <= maxLevel; lvl++) {
        let ids = levels[lvl] || [];
        // If none, continue
        if (!ids || ids.length === 0) continue;

        // compute desiredX for each node
        let desired = [];
        ids.forEach(id => {
            let parents = parentMap[id] || [];
            let parentXs = parents.map(p => (nodePos[p] && nodePos[p].x) || null).filter(x => x !== null);
            if (parentXs.length) {
                // average parent positions
                let avg = parentXs.reduce((a, b) => a + b, 0) / parentXs.length;
                desired.push({ id, x: avg });
            } else {
                // fallback placeholder; will be assigned sequentially
                desired.push({ id, x: null });
            }
        });

        // assign sequential positions for nodes with null desired x
        // determine a starting x: if any desired exists, choose min desired - spacing * i, else start from left margin
        let defined = desired.filter(d => d.x !== null);
        let undefinedNodes = desired.filter(d => d.x === null).map(d => d.id);

        // sort defined by x
        defined.sort((a, b) => a.x - b.x);

        // if none defined, lay out sequentially centered at centerX
        if (defined.length === 0) {
            // spread nodes around centerX
            let totalWidth = ids.length * minSpacingX;
            let startX = centerX - Math.floor(totalWidth / 2);
            ids.forEach((id, idx) => {
                nodePos[id] = {
                    x: startX + idx * minSpacingX,
                    y: lvl * spacingY + marginY
                };
            });
        } else {
            // place defined nodes at their x, then place undefined nodes into gaps
            defined.forEach(d => {
                nodePos[d.id] = { x: d.x, y: lvl * spacingY + marginY };
            });

            // create slots: minSpacingX intervals across a reasonable span
            // determine span min and max from defined nodes
            let minX = Math.min(...defined.map(d => d.x)) - minSpacingX * 2;
            let maxX = Math.max(...defined.map(d => d.x)) + minSpacingX * 2;

            // build candidate positions from minX to maxX stepping by minSpacingX
            let candidates = [];
            for (let cx = minX; cx <= maxX; cx += minSpacingX) candidates.push(cx);

            // remove occupied candidates near defined nodes
            let occupied = new Set();
            Object.keys(nodePos).forEach(k => {
                if (nodePos[k] && nodeLevel[k] === lvl) {
                    // occupy closest candidate
                    let nearest = candidates.reduce((best, cur) => {
                        return Math.abs(cur - nodePos[k].x) < Math.abs(best - nodePos[k].x) ? cur : best;
                    }, candidates[0]);
                    occupied.add(nearest);
                }
            });

            // fill undefined nodes into nearest non-occupied candidate positions
            undefinedNodes.forEach((id, idx) => {
                // choose candidate closest to centerX which is not occupied
                let chosen = null;
                let bestDist = Infinity;
                candidates.forEach(c => {
                    if (occupied.has(c)) return;
                    let dist = Math.abs(c - centerX);
                    if (dist < bestDist) {
                        bestDist = dist;
                        chosen = c;
                    }
                });
                if (chosen === null) {
                    // expand to right
                    let last = candidates[candidates.length - 1];
                    chosen = last + (idx + 1) * minSpacingX;
                    candidates.push(chosen);
                }
                occupied.add(chosen);
                nodePos[id] = { x: chosen, y: lvl * spacingY + marginY };
            });
        }

        // after initial placement, resolve collisions in this level
        resolveCollisionsInLevel(ids, nodePos, minSpacingX);
    }

    // After all positions assigned, final pass: ensure parent roughly centered above children
    // Adjust parent x to average of children if children exist and parent is not [Start]
    Object.keys(childrenMap).forEach(parent => {
        let kids = childrenMap[parent] || [];
        let validKids = kids.filter(k => nodePos[k]);
        if (validKids.length && parent !== "[Start]" && nodePos[parent]) {
            let avg = validKids.reduce((s, k) => s + nodePos[k].x, 0) / validKids.length;
            // move parent toward avg but do not override root [Start] centering
            nodePos[parent].x = avg;
        }
    });

    // second collision resolution across all levels: sweep through each level and ensure spacing
    Object.keys(levels).forEach(lvl => {
        let ids = levels[lvl];
        resolveCollisionsInLevel(ids, nodePos, minSpacingX);
    });

    // Draw defs first (arrow marker)
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L9,3 z" fill="#333"/>
        </marker>
    `;
    svg.appendChild(defs);

    // Draw edges as curved paths for readability
    edges.forEach(e => {
        let from = nodePos[e.from];
        let to = nodePos[e.to];
        if (!from || !to) return;

        // compute control points for a gentle curve
        let dx = to.x - from.x;
        let dy = to.y - from.y;
        let mx = from.x + dx * 0.5;
        let controlYOffset = Math.max(20, Math.abs(dx) * 0.15);

        // choose curve direction depending on relative positions
        let c1x = from.x;
        let c1y = from.y + controlYOffset;
        let c2x = to.x;
        let c2y = to.y - controlYOffset;

        let path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        let d = `M ${from.x} ${from.y + 22} C ${c1x} ${c1y} ${c2x} ${c2y} ${to.x} ${to.y - 22}`;
        path.setAttribute("d", d);
        path.setAttribute("stroke", "#333");
        path.setAttribute("fill", "none");
        path.setAttribute("marker-end", "url(#arrow)");
        path.setAttribute("stroke-width", "1");
        svg.appendChild(path);
    });

    // Draw nodes (rect + text)
    Object.keys(nodePos).forEach(id => {
        let pos = nodePos[id];
        let g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        // accessible title
        let title = document.createElementNS("http://www.w3.org/2000/svg", "title");
        title.textContent = id;
        g.appendChild(title);

        // create rect and text
        let rectWidth = 140;
        let rectHeight = 36;
        let rx = 8;
        let rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", pos.x - rectWidth / 2);
        rect.setAttribute("y", pos.y - rectHeight / 2);
        rect.setAttribute("width", rectWidth);
        rect.setAttribute("height", rectHeight);
        rect.setAttribute("rx", rx);
        rect.setAttribute("ry", rx);
        rect.setAttribute("fill", "#f8f8f8");
        rect.setAttribute("stroke", "#333");
        rect.setAttribute("stroke-width", "1");
        g.appendChild(rect);

        let text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", pos.x);
        text.setAttribute("y", pos.y + 5);
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("font-size", "13");
        text.setAttribute("font-family", "Arial, sans-serif");
        text.textContent = id;
        g.appendChild(text);

        svg.appendChild(g);
    });


    // Utility: resolve collisions within a single level by shifting nodes horizontally
    function resolveCollisionsInLevel(ids, positions, minSpacing) {
        if (!ids || ids.length <= 1) return;
        // sort ids by x
        ids.sort((a, b) => (positions[a].x || 0) - (positions[b].x || 0));
        for (let i = 1; i < ids.length; i++) {
            let left = ids[i - 1];
            let right = ids[i];
            let leftX = positions[left].x;
            let rightX = positions[right].x;
            if (rightX - leftX < minSpacing) {
                // shift right node (and subsequent ones) to the right just enough
                let shift = minSpacing - (rightX - leftX);
                for (let j = i; j < ids.length; j++) {
                    positions[ids[j]].x += shift;
                }
            }
        }

        // after shifting rightwards, attempt to center the level around centerX if far off
        let xs = ids.map(id => positions[id].x);
        let minX = Math.min(...xs);
        let maxX = Math.max(...xs);
        let levelCenter = (minX + maxX) / 2;
        let shiftToCenter = centerX - levelCenter;
        ids.forEach(id => {
            positions[id].x += shiftToCenter;
        });
    }
}



// Helper: build parent -> children map
function build_hierarchy_tree(data) {
    let graph = {};
    data.forEach(r => {
        if (!r.parent_role) return;
        if (!graph[r.parent_role]) graph[r.parent_role] = [];
        graph[r.parent_role].push(...(r.child_roles || []));
    });
    return graph;
}

// find root nodes: parents that are not children
function find_roots(data) {
    let parents = new Set(data.map(d => d.parent_role));
    let children = new Set(data.flatMap(d => d.child_roles || []));
    let roots = [...parents].filter(p => !children.has(p));
    return roots;
}

// detect cycles using DFS
function detect_cycle(graph) {
    let visited = new Set();
    let stack = new Set();

    function dfs(node) {
        if (stack.has(node)) return node;
        if (visited.has(node)) return null;
        visited.add(node);
        stack.add(node);
        let children = graph[node] || [];
        for (let c of children) {
            let result = dfs(c);
            if (result) return result;
        }
        stack.delete(node);
        return null;
    }

    for (let node in graph) {
        let result = dfs(node);
        if (result) return result;
    }
    return null;
}
