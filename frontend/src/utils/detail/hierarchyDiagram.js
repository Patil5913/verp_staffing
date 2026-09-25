// Pure port of the old desk hierarchy.js's render_hierarchy_diagram() +
// drawTreeWithArrowsUnique(): same validations (in the same order, so the
// same input always reports the same first error), same BFS-level layout
// and collision resolution, same virtual "[Start]" root node - just
// returning data for HierarchyDiagram.vue to render as SVG instead of
// building the <svg> via direct DOM calls.

const MIN_SPACING_X = 250
const SPACING_Y = 150
const MARGIN_X = 50
const MARGIN_Y = 50
const SVG_WIDTH = 1200
const RECT_WIDTH = 150
const RECT_HEIGHT = 40

function findRoots(data) {
  const parents = new Set(data.map((d) => d.parent_role))
  const children = new Set(data.flatMap((d) => d.child_roles || []))
  return [...parents].filter((p) => !children.has(p))
}

function buildHierarchyTree(data) {
  const graph = {}
  data.forEach((r) => {
    if (!r.parent_role) return
    if (!graph[r.parent_role]) graph[r.parent_role] = []
    graph[r.parent_role].push(...(r.child_roles || []))
  })
  return graph
}

function detectCycle(graph) {
  const visited = new Set()
  const stack = new Set()

  function dfs(node) {
    if (stack.has(node)) return node
    if (visited.has(node)) return null
    visited.add(node)
    stack.add(node)
    for (const child of graph[node] || []) {
      const result = dfs(child)
      if (result) return result
    }
    stack.delete(node)
    return null
  }

  for (const node in graph) {
    const result = dfs(node)
    if (result) return result
  }
  return null
}

function detectDuplicateChildren(data) {
  const duplicates = []
  data.forEach((row) => {
    const children = row.child_roles || []
    const seen = new Set()
    const dups = []
    children.forEach((child) => {
      if (seen.has(child)) dups.push(child)
      seen.add(child)
    })
    if (dups.length > 0) duplicates.push({ parent: row.parent_role, duplicates: [...new Set(dups)] })
  })
  return duplicates
}

function detectSelfLoops(data) {
  return data.filter((row) => (row.child_roles || []).includes(row.parent_role)).map((row) => row.parent_role)
}

function resolveCollisionsInLevel(ids, positions, minSpacing, centerX) {
  if (!ids || ids.length <= 1) return

  ids.sort((a, b) => (positions[a]?.x || 0) - (positions[b]?.x || 0))

  for (let i = 1; i < ids.length; i++) {
    const left = ids[i - 1]
    const right = ids[i]
    const leftX = positions[left]?.x || 0
    const rightX = positions[right]?.x || 0

    if (rightX - leftX < minSpacing) {
      const shift = minSpacing - (rightX - leftX)
      for (let j = i; j < ids.length; j++) {
        if (positions[ids[j]]) positions[ids[j]].x += shift
      }
    }
  }

  const xs = ids.map((id) => positions[id]?.x).filter((x) => x != null)
  if (xs.length > 0) {
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const levelCenter = (minX + maxX) / 2
    const shiftToCenter = centerX - levelCenter
    ids.forEach((id) => {
      if (positions[id]) positions[id].x += shiftToCenter
    })
  }
}

function layout(nodes, edges) {
  const childrenMap = {}
  const parentMap = {}
  nodes.forEach((n) => {
    childrenMap[n.id] = []
    parentMap[n.id] = []
  })
  edges.forEach((e) => {
    if (!childrenMap[e.from].includes(e.to)) childrenMap[e.from].push(e.to)
    if (!parentMap[e.to].includes(e.from)) parentMap[e.to].push(e.from)
  })

  const levels = {}
  const nodeLevel = {}
  const queue = [{ id: '[Start]', level: 0 }]
  const visited = new Set()

  while (queue.length) {
    const { id, level } = queue.shift()
    if (visited.has(id)) continue
    visited.add(id)
    nodeLevel[id] = level
    if (!levels[level]) levels[level] = []
    levels[level].push(id)
    ;(childrenMap[id] || []).forEach((child) => {
      if (!visited.has(child)) queue.push({ id: child, level: level + 1 })
    })
  }

  const levelCount = Object.keys(levels).length
  const svgHeight = Math.max(400, (levelCount + 1) * SPACING_Y + MARGIN_Y * 2)
  const centerX = SVG_WIDTH / 2
  const nodePos = {}

  if (levels[0] && levels[0].includes('[Start]')) {
    nodePos['[Start]'] = { x: centerX, y: MARGIN_Y + 20 }
  }

  const maxLevel = Math.max(...Object.keys(levels).map((k) => parseInt(k)))
  for (let lvl = 1; lvl <= maxLevel; lvl++) {
    const ids = levels[lvl] || []
    if (!ids.length) continue

    const desired = ids.map((id) => {
      const parents = parentMap[id] || []
      const parentXs = parents.map((p) => nodePos[p]?.x).filter((x) => x != null)
      if (parentXs.length) {
        return { id, x: parentXs.reduce((a, b) => a + b, 0) / parentXs.length }
      }
      return { id, x: null }
    })

    const defined = desired.filter((d) => d.x !== null)
    const undef = desired.filter((d) => d.x === null)

    if (defined.length === 0) {
      const totalWidth = ids.length * MIN_SPACING_X
      const startX = centerX - totalWidth / 2 + MIN_SPACING_X / 2
      ids.forEach((id, idx) => {
        nodePos[id] = { x: startX + idx * MIN_SPACING_X, y: lvl * SPACING_Y + MARGIN_Y }
      })
    } else {
      defined.forEach((d) => {
        nodePos[d.id] = { x: d.x, y: lvl * SPACING_Y + MARGIN_Y }
      })
      if (undef.length > 0) {
        const occupiedX = defined.map((d) => d.x)
        const maxX = Math.max(...occupiedX) + MIN_SPACING_X * 2
        undef.forEach((d, idx) => {
          nodePos[d.id] = { x: maxX + (idx + 1) * MIN_SPACING_X, y: lvl * SPACING_Y + MARGIN_Y }
        })
      }
    }

    resolveCollisionsInLevel(ids, nodePos, MIN_SPACING_X, centerX)
  }

  Object.keys(childrenMap).forEach((parent) => {
    const kids = (childrenMap[parent] || []).filter((k) => nodePos[k])
    if (kids.length && parent !== '[Start]' && nodePos[parent]) {
      nodePos[parent].x = kids.reduce((s, k) => s + nodePos[k].x, 0) / kids.length
    }
  })

  Object.keys(levels).forEach((lvl) => {
    resolveCollisionsInLevel(levels[lvl], nodePos, MIN_SPACING_X, centerX)
  })

  const renderedNodes = Object.keys(nodePos).map((id) => ({
    id,
    x: nodePos[id].x,
    y: nodePos[id].y,
    isStart: id === '[Start]',
  }))

  const renderedEdges = []
  edges.forEach((e) => {
    const from = nodePos[e.from]
    const to = nodePos[e.to]
    if (!from || !to) return

    const fromLevel = nodeLevel[e.from]
    const toLevel = nodeLevel[e.to]
    let d

    if (fromLevel === toLevel) {
      const isLeftToRight = from.x < to.x
      const startX = isLeftToRight ? from.x + RECT_WIDTH / 2 : from.x - RECT_WIDTH / 2
      const endX = isLeftToRight ? to.x - RECT_WIDTH / 2 : to.x + RECT_WIDTH / 2
      d = `M ${startX} ${from.y} L ${endX} ${from.y}`
    } else {
      const startY = from.y + RECT_HEIGHT / 2
      const endY = to.y - RECT_HEIGHT / 2
      const dx = to.x - from.x
      const dy = endY - startY
      if (Math.abs(dx) < 10) {
        d = `M ${from.x} ${startY} L ${to.x} ${endY}`
      } else {
        const curve = Math.min(Math.abs(dy) * 0.4, 60)
        d = `M ${from.x} ${startY} C ${from.x} ${startY + curve}, ${to.x} ${endY - curve}, ${to.x} ${endY}`
      }
    }

    renderedEdges.push({ id: `${e.from}->${e.to}`, d })
  })

  return { nodes: renderedNodes, edges: renderedEdges, width: SVG_WIDTH, height: svgHeight }
}

// The single entry point HierarchyDiagram.vue calls. `data` is the parsed
// role_hierarchy_json array: [{ parent_role, child_roles: [] }, ...].
// Returns either { error, title } (nothing renders - show that message
// instead) or { nodes, edges, width, height } (a valid tree to draw).
export function computeHierarchyDiagram(data) {
  if (!data || !data.length) {
    return { error: 'No hierarchy defined yet. Add roles above to get started.', empty: true }
  }

  const emptyParents = data.filter((r) => !r.parent_role)
  if (emptyParents.length > 0) {
    return { error: 'Found rows with empty parent roles. Please fill in all parent roles.', title: 'Error' }
  }

  const selfLoops = detectSelfLoops(data)
  if (selfLoops.length > 0) {
    return {
      error: `Self-Reference Detected: the following role(s) cannot be their own child: ${selfLoops.join(', ')}. Remove the role from its own children list.`,
      title: 'Error',
    }
  }

  const duplicates = detectDuplicateChildren(data)
  if (duplicates.length > 0) {
    const msg = duplicates.map((d) => `${d.parent} has duplicate children: ${d.duplicates.join(', ')}`).join('; ')
    return { error: `Duplicate Children Detected: ${msg}. Remove duplicate roles from the children list.`, title: 'Error' }
  }

  const roots = findRoots(data)
  if (roots.length === 0) {
    return {
      error:
        'No Root Role Found: a hierarchy needs at least one root role (a parent that is not anyone\'s child). Make sure at least one parent role doesn\'t appear in any children list.',
      title: 'Error',
    }
  }

  const graph = buildHierarchyTree(data)
  const cycle = detectCycle(graph)
  if (cycle) {
    return {
      error: `Circular Reference Detected: found a cycle involving role "${cycle}". Review the parent-child relationships and remove the circular reference.`,
      title: 'Error',
    }
  }

  const allRoles = new Set()
  data.forEach((r) => {
    allRoles.add(r.parent_role)
    ;(r.child_roles || []).forEach((c) => allRoles.add(c))
  })

  const nodes = [...allRoles].map((role) => ({ id: role }))
  const edges = []
  data.forEach((r) => {
    ;(r.child_roles || []).forEach((c) => edges.push({ from: r.parent_role, to: c }))
  })

  nodes.unshift({ id: '[Start]' })
  roots.forEach((root) => edges.push({ from: '[Start]', to: root }))

  return layout(nodes, edges)
}
