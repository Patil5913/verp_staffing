// Copyright (c) 2025, Vrugle and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hierarchy", {
    async refresh(frm) {
        // Only render if wrapper is empty or force re-render is needed
        if (!frm.get_field("role_table_html").$wrapper.find("#role-table-wrapper").length) {
            render_role_table_html(frm);
        }

        frm.department_roles = await load_department_roles(frm);


        init_role_table(frm);
        render_hierarchy_diagram(frm);

        frm.set_query("department", () => {
            return {
                filters: [
                    ["Department", "name", "not in", frm.used_departments || []]
                ]
            };
        });

        load_used_departments(frm);
        render_auto_assign_section(frm);
        // If document already exists
        if (!frm.is_new()) {
            frm.set_df_property("department", "read_only", 1);
        }
    },

    role_hierarchy_json(frm) {
        render_hierarchy_diagram(frm);
    },

    async department(frm) {
        frm.department_roles = await load_department_roles(frm);
        // Clear invalid auto-assign config
        if (frm.doc.auto_assign_config) {
            try {
                const cfg = JSON.parse(frm.doc.auto_assign_config);
                if (!frm.department_roles.includes(cfg.role)) {
                    frm.set_value("auto_assign_config", "");
                }
            } catch { }
        }
        render_auto_assign_section(frm);
        init_role_table(frm);
    },

    before_save(frm) {
        // Force save before actual save to ensure latest data
        save_table_to_json(frm);

        // Validate that we have data
        if (!frm.doc.role_hierarchy_json) {
            frappe.msgprint(__("Please add at least one role hierarchy"));
            frappe.validated = false;
        }
        if (!frm.doc.auto_assign_config) {
            frappe.msgprint(
                __("Please select a role for Auto Assignment so the system knows who can receive records.")
            );
            frappe.validated = false;
        }

        // Extra safety: prevent change even before save
        if (!frm.is_new() && frm.doc.__unsaved === false) {
            frm.set_df_property("department", "read_only", 1);
        }
    }
});

function load_used_departments(frm) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Hierarchy",
            fields: ["department"],
            filters: {
                name: ["!=", frm.doc.name]
            },
            limit_page_length: 1000
        },
        callback(r) {
            frm.used_departments = r.message.map(d => d.department);
            frm.refresh_field("department");
        }
    });
}

async function load_department_roles(frm) {
    if (!frm.doc.department) return [];

    const res = await frappe.call({
        method: "frappe.client.get",
        args: {
            doctype: "Department",
            name: frm.doc.department
        }
    });

    let roles = [];

    if (res?.message?.role && Array.isArray(res.message.role)) {
        roles = res.message.role
            .map(row => row.role)
            .filter(r => r); 
    }

    if (!roles.length) {
        frappe.msgprint({
            title: "No Roles Configured",
            indicator: "orange",
            message: `
                The selected department <b>${frm.doc.department}</b> does not have any roles assigned.
                <br><br>
                Please add roles to this department first.
                <br>
                Path: <b>Department → Roles</b>
                <br><br>
                Once roles are configured, you can define the hierarchy and continue.
            `
        });

        return [];
    }

    return roles;
}



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
        console.log("Error parsing role_hierarchy_json:", e);
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
            <td><button class="btn btn-danger btn-sm delete-row">Delete</button> </td>
        </tr>
    `);

    $("#role-table tbody").append(tr);

    let parent_container = tr.find(".parent-role-container");
    let child_container = tr.find(".child-role-container");

    /* ---------------- Parent Role ---------------- */
    let parent_control = frappe.ui.form.make_control({
        parent: parent_container,
        df: {
            fieldtype: "Link",
            fieldname: "parent_role_" + row_id,
            placeholder: "Choose Parent Role",
            options: "Role",
            get_query: () => ({
                filters: {
                    name: ["in", frm.department_roles || []]
                }
            })
        },
        render_input: true
    });

    parent_container.data("control", parent_control);

    if (rowData?.parent_role) {
        parent_control.set_value(rowData.parent_role);
    }

    parent_control.$input.on("change", () => {
        setTimeout(() => save_table_to_json(frm), 300);
    });

    /* ---------------- Child Roles (CUSTOM MULTISELECT) ---------------- */
    let selected_roles = [];

    let multiselect = $(`
        <div class="custom-multiselect">
            <div class="multiselect-content">
                <div class="selected-items"></div>
                <input type="text" class="multiselect-input" placeholder="Choose Child Roles">
            </div>
            <div class="multiselect-dropdown hidden"></div>
        </div>
    `);

    child_container.append(multiselect);
    child_container.data("control", { get_value: () => selected_roles });

    const content_area = multiselect.find(".multiselect-content");
    const chips = multiselect.find(".selected-items");
    const input = multiselect.find(".multiselect-input");
    const dropdown = multiselect.find(".multiselect-dropdown");

    function render_chips() {
        chips.empty();

        if (selected_roles.length === 0) {
            input.show();
            return;
        }

        selected_roles.forEach(role => {
            chips.append(`
                <span class="chip">
                    ${frappe.utils.escape_html(role)}
                    <span class="remove" data-role="${frappe.utils.escape_html(role)}">×</span>
                </span>
            `);
        });

        input.show();
    }

    function render_dropdown(filter = "") {
        dropdown.empty();

        let roles = (frm.department_roles || [])
            .filter(r =>
                r.toLowerCase().includes(filter.toLowerCase()) &&
                !selected_roles.includes(r)
            );

        if (!roles.length) {
            dropdown.addClass("hidden");
            return;
        }

        roles.forEach(role => {
            dropdown.append(`<div class="item">${frappe.utils.escape_html(role)}</div>`);
        });

        dropdown.removeClass("hidden");
    }

    // Show dropdown on focus or input
    input.on("focus", () => {
        render_dropdown(input.val());
    });

    input.on("keyup", (e) => {
        // Don't trigger on special keys
        if (e.key === "Escape") {
            dropdown.addClass("hidden");
            input.val("");
            return;
        }
        render_dropdown(input.val());
    });

    // Allow input to be clicked even when there are chips
    multiselect.on("click", function (e) {
        if (!$(e.target).hasClass("remove")) {
            input.focus();
        }
    });

    // Select item from dropdown
    multiselect.on("click", ".item", function () {
        let role = $(this).text();
        selected_roles.push(role);
        input.val("");
        render_chips();
        dropdown.addClass("hidden");
        save_table_to_json(frm);
        input.focus();
    });

    // Remove chip
    multiselect.on("click", ".remove", function (e) {
        e.stopPropagation();
        let role = $(this).data("role");
        selected_roles = selected_roles.filter(r => r !== role);
        render_chips();
        save_table_to_json(frm);
    });

    // Close dropdown when clicking outside
    $(document).on("click", function (e) {
        if (!multiselect.is(e.target) && !multiselect.has(e.target).length) {
            dropdown.addClass("hidden");
        }
    });

    /* ---- Load existing child roles ---- */
    if (rowData?.child_roles?.length) {
        selected_roles = rowData.child_roles.map(r =>
            typeof r === "string" ? r : r.role
        );
        render_chips();
    }

    /* ---------------- Delete Row ---------------- */
    tr.find(".delete-row").on("click", function () {
        tr.remove();
        setTimeout(() => save_table_to_json(frm), 300);
    });
}


function save_table_to_json(frm) {
    let data = [];

    $("#role-table tbody tr.role-row").each(function () {
        let row = $(this);

        let parent_control = row.find(".parent-role-container").data("control");
        let child_control = row.find(".child-role-container").data("control");

        if (!parent_control) return;

        let parent = parent_control.get_value() || "";

        // Skip empty rows
        if (!parent) return;

        let children = child_control?.get_value?.() || [];

        data.push({
            parent_role: parent,
            child_roles: children
        });
    });

    let newJson = JSON.stringify(data);
    let oldJson = frm.doc.role_hierarchy_json || "[]";

    if (newJson !== oldJson) {
        frm.set_value("role_hierarchy_json", newJson);
        render_hierarchy_diagram(frm);
    }
}



// Detect duplicate children in same row
function detect_duplicate_children(data) {
    let duplicates = [];

    data.forEach(row => {
        let children = row.child_roles || [];
        let seen = new Set();
        let dups = [];

        children.forEach(child => {
            if (seen.has(child)) {
                dups.push(child);
            }
            seen.add(child);
        });

        if (dups.length > 0) {
            duplicates.push({
                parent: row.parent_role,
                duplicates: [...new Set(dups)]
            });
        }
    });

    return duplicates;
}

// Detect if a role is its own ancestor (self-loop)
function detect_self_loops(data) {
    let loops = [];

    data.forEach(row => {
        let children = row.child_roles || [];
        if (children.includes(row.parent_role)) {
            loops.push(row.parent_role);
        }
    });

    return loops;
}

// Enhanced render with better error messages and fixed arrows
function render_hierarchy_diagram(frm) {
    let wrapper = frm.get_field("hierarchy_diagram").$wrapper;
    wrapper.empty();

    let data = [];
    try {
        data = frm.doc.role_hierarchy_json ? JSON.parse(frm.doc.role_hierarchy_json) : [];
    } catch {
        wrapper.html(`<div style="color:red;padding:10px;background:#ffe6e6;border-radius:4px;"><strong>Error:</strong> Invalid JSON data</div>`);
        return;
    }

    if (!data.length) {
        wrapper.html(`<div style="color:#888;padding:10px;">No hierarchy defined yet. Add roles above to get started.</div>`);
        return;
    }

    // Validation 1: Check for empty parent roles
    let emptyParents = data.filter(r => !r.parent_role);
    if (emptyParents.length > 0) {
        wrapper.html(`<div style="color:red;padding:10px;background:#ffe6e6;border-radius:4px;"><strong>Error:</strong> Found rows with empty parent roles. Please fill in all parent roles.</div>`);
        return;
    }

    // Validation 2: Check for self-loops
    let selfLoops = detect_self_loops(data);
    if (selfLoops.length > 0) {
        wrapper.html(`
            <div style="color:red;padding:10px;background:#ffe6e6;border-radius:4px;">
                <strong>Error: Self-Reference Detected</strong><br>
                The following role(s) cannot be their own child:<br>
                <ul style="margin-top:8px;">
                    ${selfLoops.map(role => `<li><strong>${role}</strong> is listed as its own child</li>`).join('')}
                </ul>
                <em>Fix: Remove the role from its own children list.</em>
            </div>
        `);
        return;
    }

    // Validation 3: Check for duplicate children in same row
    let duplicates = detect_duplicate_children(data);
    if (duplicates.length > 0) {
        wrapper.html(`
            <div style="color:red;padding:10px;background:#ffe6e6;border-radius:4px;">
                <strong>Error: Duplicate Children Detected</strong><br>
                <ul style="margin-top:8px;">
                    ${duplicates.map(d => `<li><strong>${d.parent}</strong> has duplicate children: ${d.duplicates.join(', ')}</li>`).join('')}
                </ul>
                <em>Fix: Remove duplicate roles from the children list.</em>
            </div>
        `);
        return;
    }

    // Validation 5: Check for root
    let roots = find_roots(data);
    if (roots.length === 0) {
        wrapper.html(`
            <div style="color:red;padding:10px;background:#ffe6e6;border-radius:4px;">
                <strong>Error: No Root Role Found</strong><br>
                A hierarchy needs at least one root role (a parent that is not anyone's child).<br>
                <em>Fix: Make sure at least one parent role doesn't appear in any children list.</em>
            </div>
        `);
        return;
    }

    // Validation 6: Check for cycles
    let graph = build_hierarchy_tree(data);
    let cycle = detect_cycle(graph);
    if (cycle) {
        wrapper.html(`
            <div style="color:red;padding:10px;background:#ffe6e6;border-radius:4px;">
                <strong>Error: Circular Reference Detected</strong><br>
                Found a cycle involving role: <strong>${cycle}</strong><br>
                This means a role eventually becomes its own descendant, which creates an infinite loop.<br>
                <em>Fix: Review the parent-child relationships and remove the circular reference.</em>
            </div>
        `);
        return;
    }

    // Build nodes and edges
    let allRoles = new Set();
    data.forEach(r => {
        allRoles.add(r.parent_role);
        (r.child_roles || []).forEach(c => allRoles.add(c));
    });

    let nodes = [...allRoles].map(role => ({ id: role, label: role }));
    let edges = [];
    data.forEach(r => {
        (r.child_roles || []).forEach(c => {
            edges.push({ from: r.parent_role, to: c });
        });
    });

    // Add virtual [Start] node and connect to all roots
    nodes.unshift({ id: "[Start]", label: "[Start]" });
    roots.forEach(root => {
        edges.push({ from: "[Start]", to: root });
    });

    // Prepare html and svg
    let html = `
    <style>
        .hier-wrapper {
            overflow: auto;
            border: 1px solid #d1d1d1;
            border-radius: 4px;
            background: #fafafa;
            padding: 10px;
        }
        .hier-wrapper svg {
            display: block;
        }
    </style>
    <div class="hier-wrapper">
        <svg id="role-svg" width="1200" height="600"></svg>
    </div>
    `;

    wrapper.html(html);
    drawTreeWithArrowsUnique(nodes, edges);
}

function drawTreeWithArrowsUnique(nodes, edges) {
    const svg = document.getElementById("role-svg");
    if (!svg) return;

    svg.innerHTML = "";

    const minSpacingX = 250;
    const spacingY = 150;
    const marginX = 50;
    const marginY = 50;

    // Build maps
    let childrenMap = {};
    let parentMap = {};
    nodes.forEach(n => {
        childrenMap[n.id] = [];
        parentMap[n.id] = [];
    });
    edges.forEach(e => {
        if (!childrenMap[e.from].includes(e.to)) childrenMap[e.from].push(e.to);
        if (!parentMap[e.to].includes(e.from)) parentMap[e.to].push(e.from);
    });

    // BFS to compute levels
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

    // Set SVG height
    let levelCount = Object.keys(levels).length;
    svg.setAttribute("height", Math.max(400, (levelCount + 1) * spacingY + marginY * 2));

    const svgWidth = parseInt(svg.getAttribute("width")) || 1200;
    const centerX = svgWidth / 2;
    let nodePos = {};

    // Position [Start] at center
    if (levels[0] && levels[0].includes("[Start]")) {
        nodePos["[Start]"] = { x: centerX, y: marginY + 20 };
    }

    // Position other levels
    let maxLevel = Math.max(...Object.keys(levels).map(k => parseInt(k)));
    for (let lvl = 1; lvl <= maxLevel; lvl++) {
        let ids = levels[lvl] || [];
        if (!ids || ids.length === 0) continue;

        // Calculate positions based on parent positions
        let desired = [];
        ids.forEach(id => {
            let parents = parentMap[id] || [];
            let parentXs = parents.map(p => nodePos[p]?.x).filter(x => x != null);
            if (parentXs.length) {
                let avg = parentXs.reduce((a, b) => a + b, 0) / parentXs.length;
                desired.push({ id, x: avg });
            } else {
                desired.push({ id, x: null });
            }
        });

        let defined = desired.filter(d => d.x !== null);
        let undefined = desired.filter(d => d.x === null);

        if (defined.length === 0) {
            // Center all nodes
            let totalWidth = ids.length * minSpacingX;
            let startX = centerX - totalWidth / 2 + minSpacingX / 2;
            ids.forEach((id, idx) => {
                nodePos[id] = {
                    x: startX + idx * minSpacingX,
                    y: lvl * spacingY + marginY
                };
            });
        } else {
            // Place defined nodes
            defined.forEach(d => {
                nodePos[d.id] = { x: d.x, y: lvl * spacingY + marginY };
            });

            // Place undefined nodes
            if (undefined.length > 0) {
                let occupiedX = defined.map(d => d.x);
                let minX = Math.min(...occupiedX) - minSpacingX * 2;
                let maxX = Math.max(...occupiedX) + minSpacingX * 2;

                undefined.forEach((d, idx) => {
                    let x = maxX + (idx + 1) * minSpacingX;
                    nodePos[d.id] = { x: x, y: lvl * spacingY + marginY };
                });
            }
        }

        // Resolve collisions
        resolveCollisionsInLevel(ids, nodePos, minSpacingX, centerX);
    }

    // Center parents over children
    Object.keys(childrenMap).forEach(parent => {
        let kids = childrenMap[parent] || [];
        let validKids = kids.filter(k => nodePos[k]);
        if (validKids.length && parent !== "[Start]" && nodePos[parent]) {
            let avg = validKids.reduce((s, k) => s + nodePos[k].x, 0) / validKids.length;
            nodePos[parent].x = avg;
        }
    });

    // Final collision resolution
    Object.keys(levels).forEach(lvl => {
        resolveCollisionsInLevel(levels[lvl], nodePos, minSpacingX, centerX);
    });

    // Draw arrow marker
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill="#555"/>
        </marker>
    `;
    svg.appendChild(defs);

    // Draw edges with proper routing
    edges.forEach(e => {
        let from = nodePos[e.from];
        let to = nodePos[e.to];
        if (!from || !to) return;

        const rectHeight = 40;
        const rectWidth = 150;

        let path = document.createElementNS("http://www.w3.org/2000/svg", "path");

        // Check if nodes are on the same level (siblings)
        let fromLevel = nodeLevel[e.from];
        let toLevel = nodeLevel[e.to];

        if (fromLevel === toLevel) {
            // Horizontal connection for siblings
            // Determine direction based on x position
            let isLeftToRight = from.x < to.x;
            let startX, endX;

            if (isLeftToRight) {
                startX = from.x + rectWidth / 2;
                endX = to.x - rectWidth / 2;
            } else {
                startX = from.x - rectWidth / 2;
                endX = to.x + rectWidth / 2;
            }

            let y = from.y;

            // Simple horizontal line
            let d = `M ${startX} ${y} L ${endX} ${y}`;
            path.setAttribute("d", d);
            path.setAttribute("stroke", "#555");
            path.setAttribute("stroke-width", "2");
            path.setAttribute("fill", "none");
            path.setAttribute("marker-end", "url(#arrow)");
        } else {
            // Vertical connection for parent-child
            let startY = from.y + rectHeight / 2;
            let endY = to.y - rectHeight / 2;

            let dx = to.x - from.x;
            let dy = endY - startY;

            if (Math.abs(dx) < 10) {
                // Straight vertical line when nodes are aligned
                let d = `M ${from.x} ${startY} L ${to.x} ${endY}`;
                path.setAttribute("d", d);
            } else {
                // Smooth curve for diagonal connections
                let curve = Math.min(Math.abs(dy) * 0.4, 60);
                let d = `M ${from.x} ${startY} C ${from.x} ${startY + curve}, ${to.x} ${endY - curve}, ${to.x} ${endY}`;
                path.setAttribute("d", d);
            }

            path.setAttribute("stroke", "#555");
            path.setAttribute("stroke-width", "2");
            path.setAttribute("fill", "none");
            path.setAttribute("marker-end", "url(#arrow)");
        }

        svg.appendChild(path);
    });

    // Draw nodes
    Object.keys(nodePos).forEach(id => {
        let pos = nodePos[id];
        let g = document.createElementNS("http://www.w3.org/2000/svg", "g");

        let rectWidth = 150;
        let rectHeight = 40;
        let rx = 6;

        // Different style for [Start] node
        let isStart = id === "[Start]";
        let fillColor = isStart ? "#e3f2fd" : "#ffffff";
        let strokeColor = isStart ? "#1976d2" : "#666";
        let strokeWidth = isStart ? "2" : "1.5";

        let rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", pos.x - rectWidth / 2);
        rect.setAttribute("y", pos.y - rectHeight / 2);
        rect.setAttribute("width", rectWidth);
        rect.setAttribute("height", rectHeight);
        rect.setAttribute("rx", rx);
        rect.setAttribute("ry", rx);
        rect.setAttribute("fill", fillColor);
        rect.setAttribute("stroke", strokeColor);
        rect.setAttribute("stroke-width", strokeWidth);
        g.appendChild(rect);

        let text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", pos.x);
        text.setAttribute("y", pos.y + 5);
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("font-size", "14");
        text.setAttribute("font-weight", isStart ? "bold" : "normal");
        text.setAttribute("font-family", "Arial, sans-serif");
        text.setAttribute("fill", "#333");
        text.textContent = id;
        g.appendChild(text);

        svg.appendChild(g);
    });

    function resolveCollisionsInLevel(ids, positions, minSpacing, centerX) {
        if (!ids || ids.length <= 1) return;

        ids.sort((a, b) => (positions[a]?.x || 0) - (positions[b]?.x || 0));

        for (let i = 1; i < ids.length; i++) {
            let left = ids[i - 1];
            let right = ids[i];
            let leftX = positions[left]?.x || 0;
            let rightX = positions[right]?.x || 0;

            if (rightX - leftX < minSpacing) {
                let shift = minSpacing - (rightX - leftX);
                for (let j = i; j < ids.length; j++) {
                    if (positions[ids[j]]) {
                        positions[ids[j]].x += shift;
                    }
                }
            }
        }

        // Center the level
        let xs = ids.map(id => positions[id]?.x).filter(x => x != null);
        if (xs.length > 0) {
            let minX = Math.min(...xs);
            let maxX = Math.max(...xs);
            let levelCenter = (minX + maxX) / 2;
            let shiftToCenter = centerX - levelCenter;

            ids.forEach(id => {
                if (positions[id]) {
                    positions[id].x += shiftToCenter;
                }
            });
        }
    }
}

// Helper functions
function build_hierarchy_tree(data) {
    let graph = {};
    data.forEach(r => {
        if (!r.parent_role) return;
        if (!graph[r.parent_role]) graph[r.parent_role] = [];
        graph[r.parent_role].push(...(r.child_roles || []));
    });
    return graph;
}

function find_roots(data) {
    let parents = new Set(data.map(d => d.parent_role));
    let children = new Set(data.flatMap(d => d.child_roles || []));
    let roots = [...parents].filter(p => !children.has(p));
    return roots;
}

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

function render_auto_assign_section(frm) {
    const wrapper = frm.get_field("role_table_html").$wrapper;

    // Remove old section if exists
    wrapper.find("#auto-assign-wrapper").remove();
    frm._auto_assign_control = null;

    if (!frm.department_roles || !frm.department_roles.length) return;

    wrapper.append(`
        <div id="auto-assign-wrapper" style="margin-top:20px; padding:15px; border:1px solid #ddd; border-radius:6px; background:#f9f9f9;">
            <h4 style="margin-bottom:8px;">Auto Assignment Rule</h4>
            <p style="color:#555; font-size:13px; margin-bottom:10px;">
                Select one role to enable automatic assignment.
                Only users with this role will be considered for auto and manual assignment.
            </p>
            <div class="auto-assign-role" data="control"></div>
        </div>
    `);

    create_auto_assign_control(frm);
}

function create_auto_assign_control(frm) {
    const container = $("#auto-assign-wrapper .auto-assign-role");

    const roles = Array.isArray(frm.department_roles) ? frm.department_roles : [];

    let saved_role = "";

    if (frm.doc.auto_assign_config) {
        try {
            const cfg = JSON.parse(frm.doc.auto_assign_config);
            saved_role = cfg.role || "";
        } catch {
            saved_role = "";
        }
    }

    frm._auto_assign_control = frappe.ui.form.make_control({
        parent: container,
        df: {
            fieldtype: "Select",
            label: "Role for Auto Assignment",
            fieldname: "auto_assign_role",
            options: ["", ...roles],
            description: "This role will be used for automatic assignment"
        },
        render_input: true
    });

    const control = frm._auto_assign_control;

    // Force render before setting value
    control.refresh();

    // Restore value ONLY if valid
    if (saved_role && roles.includes(saved_role)) {
        control.set_value(saved_role);
    } else {
        control.set_value("");
    }

    control.$input.on("change", () => {
        save_auto_assign_config(frm);
    });
}

function save_auto_assign_config(frm) {
    const control = frm._auto_assign_control;

    if (!control) {
        console.warn("Auto assign control not initialized");
        return;
    }

    const role = control.get_value();

    if (!role) {
        frm.set_value("auto_assign_config", "");
        return;
    }

    frm.set_value("auto_assign_config", JSON.stringify({ role }));
}

