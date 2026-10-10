<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <StateBanner v-if="loadError" icon="alert-triangle" title="Couldn't load the tree" :description="loadError" />
    <div v-else-if="loading && !roots.length" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>
    <StateBanner v-else-if="!roots.length" icon="folder" :title="emptyTitle" :description="emptyDescription" />

    <div v-else class="min-h-0 flex-1 overflow-auto rounded-lg border border-app-border bg-app-panel">
      <table class="w-full min-w-[720px] table-fixed border-collapse text-p-sm">
        <colgroup>
          <col />
          <col v-for="col in columns" :key="col.key" :style="{ width: col.width || '9rem' }" />
          <col style="width: 7.5rem" />
        </colgroup>
        <thead class="sticky top-0 z-10 bg-app-panel-2">
          <tr class="text-left text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
            <th class="h-10 border-b border-app-border px-4">{{ nameLabel }}</th>
            <th
              v-for="col in columns"
              :key="col.key"
              class="h-10 border-b border-app-border px-3"
              :class="col.align === 'right' ? 'text-right' : ''"
            >
              {{ col.label }}
            </th>
            <th class="h-10 border-b border-app-border" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="node in visibleRows"
            :key="node.value"
            class="group cursor-pointer border-b border-app-border/60 transition-colors last:border-0 hover:bg-app-panel-2"
            @click="onRowClick(node)"
          >
            <td class="h-10 px-4">
              <div class="flex min-w-0 items-center" :style="{ paddingLeft: `${node._depth * 20}px` }">
                <button
                  v-if="node.expandable"
                  type="button"
                  class="mr-1 flex size-5 shrink-0 items-center justify-center rounded text-app-text-muted hover:bg-app-border/60 hover:text-app-text"
                  @click.stop="toggle(node)"
                >
                  <LoadingIndicator v-if="node._loading" class="size-3" />
                  <span v-else class="size-4" :class="node._open ? 'lucide-chevron-down' : 'lucide-chevron-right'" />
                </button>
                <span v-else class="mr-1 inline-block size-5 shrink-0" />
                <span
                  class="mr-2 size-4 shrink-0"
                  :class="node.expandable ? (node._open ? 'lucide-folder-open text-amber-500' : 'lucide-folder text-amber-500') : 'lucide-file-text text-app-text-muted'"
                />
                <slot name="label" :node="node">
                  <span class="truncate" :class="node.expandable ? 'font-semibold text-app-text' : 'text-app-text'">
                    {{ node.label }}
                  </span>
                </slot>
                <!-- A group node's own click toggles it open/closed (there's more useful to do
                     with a click than leave the tree for its detail page) - this is the way to
                     still get there, an explicit "go to this record" affordance next to the
                     name rather than folded into the row click. -->
                <button
                  v-if="node.expandable"
                  type="button"
                  class="ml-1.5 flex size-5 shrink-0 items-center justify-center rounded text-app-text-muted opacity-0 transition-opacity hover:bg-app-border/60 hover:text-app-primary group-hover:opacity-100"
                  title="Open"
                  @click.stop="emit('open', node)"
                >
                  <span class="lucide-arrow-right size-3.5" />
                </button>
              </div>
            </td>
            <td
              v-for="col in columns"
              :key="col.key"
              class="px-3"
              :class="col.align === 'right' ? 'text-right tabular-nums' : ''"
            >
              <slot :name="`cell-${col.key}`" :node="node">
                <span class="truncate text-app-text-muted">{{ node[col.key] ?? '' }}</span>
              </slot>
            </td>
            <td class="px-3" @click.stop>
              <div class="flex items-center justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                <slot name="actions" :node="node" />
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
// A doctype-agnostic tree rendered as an indented table - chevron/folder/leaf
// per row, extra columns, hover row actions - replacing the bare frappe-ui
// <Tree> list the tree page used to show. The page supplies `loader(parent)`
// (children of a node, or the roots when parent is null) and gets back
// expand/collapse-all, search that keeps matches' ancestors, and reload.
import { computed, ref } from 'vue'
import { LoadingIndicator } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'
import { normalizeError } from '@/utils/common/errors'

const props = defineProps({
  // async (parentValue | null) => [{ value, label?, expandable, ...extra }]
  loader: { type: Function, required: true },
  // Called with every batch of freshly loaded nodes - where a page enriches
  // them (e.g. Account balances) by mutating the node objects in place.
  afterLoad: { type: Function, default: null },
  columns: { type: Array, default: () => [] }, // [{ key, label, width?, align? }]
  nameLabel: { type: String, default: 'Name' },
  search: { type: String, default: '' },
  emptyTitle: { type: String, default: 'No records' },
  emptyDescription: { type: String, default: '' },
})
const emit = defineEmits(['open'])

const roots = ref([])
const loading = ref(false)
const loadError = ref('')

function decorate(raw, depth, parent) {
  return {
    ...raw,
    label: raw.title || raw.label || raw.value,
    children: [],
    _depth: depth,
    _parent: parent,
    _loaded: false,
    _loading: false,
    _open: false,
  }
}

async function fetchChildren(parent) {
  const raw = (await props.loader(parent ? parent.value : null)) || []
  const nodes = raw.map((r) => decorate(r, parent ? parent._depth + 1 : 0, parent))
  await props.afterLoad?.(nodes)
  return nodes
}

async function reload() {
  loading.value = true
  loadError.value = ''
  try {
    roots.value = await fetchChildren(null)
  } catch (error) {
    roots.value = []
    loadError.value = normalizeError(error).message
  } finally {
    loading.value = false
  }
}

async function ensureLoaded(node) {
  if (node._loaded || !node.expandable) return
  node._loading = true
  try {
    node.children = await fetchChildren(node)
    node._loaded = true
  } finally {
    node._loading = false
  }
}

async function toggle(node) {
  if (!node._open) await ensureLoaded(node)
  node._open = !node._open
}

// A group node's own row expands/collapses it on click (see the hover "open" arrow next to
// its name for going to its detail page instead); a leaf node has nothing to expand, so
// clicking it goes straight to its detail page, same as before.
function onRowClick(node) {
  if (node.expandable) toggle(node)
  else emit('open', node)
}

// Breadth-first so a big chart fills top-down and each level's loads run in
// parallel, rather than one request per node in sequence.
async function expandAll() {
  loading.value = true
  try {
    let level = roots.value
    while (level.length) {
      const expandable = level.filter((n) => n.expandable)
      await Promise.all(expandable.map(ensureLoaded))
      expandable.forEach((n) => (n._open = true))
      level = expandable.flatMap((n) => n.children)
    }
  } finally {
    loading.value = false
  }
}

function collapseAll() {
  const walk = (nodes) => nodes.forEach((n) => ((n._open = false), walk(n.children)))
  walk(roots.value)
}

// A client-side echo of useDocList's search syntax (list_view.py's
// resolve_search_filter) - field=value / comparisons / between / and/or -
// since a tree's nodes are already loaded in memory, there's no server
// round-trip to delegate this to.
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
function unquote(v) {
  if (v.length >= 2 && ((v[0] === '"' && v.at(-1) === '"') || (v[0] === "'" && v.at(-1) === "'"))) {
    return v.slice(1, -1)
  }
  return v
}

// Maps a search key (case-insensitive fieldname or column label) to how to
// read it off a node: 'label' for the name column, 'value' for its raw id,
// or the column's own key for anything else.
const fieldAliases = computed(() => {
  const map = {}
  map[props.nameLabel.toLowerCase()] = 'label'
  map.name = 'value'
  map.label = 'label'
  for (const col of props.columns) {
    map[col.key.toLowerCase()] = col.key
    if (col.label) map[col.label.toLowerCase()] = col.key
  }
  return map
})

function fieldValue(node, key) {
  const resolved = fieldAliases.value[key.toLowerCase()]
  if (!resolved) return undefined
  return resolved === 'label' ? node.label : resolved === 'value' ? node.value : node[resolved]
}

function compareValues(actual, op, expected) {
  const numA = Number(actual)
  const numE = Number(expected)
  const bothNumeric = actual !== '' && expected !== '' && !Number.isNaN(numA) && !Number.isNaN(numE)
  // Only ISO-style dates are compared as dates. Date.parse alone is far too forgiving - it reads
  // "Bank 2" or "Account 12" as a day in 2001 - which made `name=Account 1` miss "Account 12".
  const isoDate = (v) => /^\d{4}-\d{1,2}-\d{1,2}/.test(String(v))
  const dateA = isoDate(actual) ? Date.parse(actual) : NaN
  const dateE = isoDate(expected) ? Date.parse(expected) : NaN
  const bothDate = !bothNumeric && !Number.isNaN(dateA) && !Number.isNaN(dateE)
  const cmp = bothNumeric ? numA - numE : bothDate ? dateA - dateE : String(actual).localeCompare(String(expected))
  const exact = bothNumeric || bothDate
  switch (op) {
    case '!=':
      return exact ? cmp !== 0 : !String(actual).toLowerCase().includes(String(expected).toLowerCase())
    case '>':
      return cmp > 0
    case '>=':
      return cmp >= 0
    case '<':
      return cmp < 0
    case '<=':
      return cmp <= 0
    default:
      return exact ? cmp === 0 : String(actual).toLowerCase().includes(String(expected).toLowerCase())
  }
}

const TOKEN_RE = /"[^"]*"|'[^']*'|\S+/g

const parsedQuery = computed(() => {
  const keys = Object.keys(fieldAliases.value)
    .sort((a, b) => b.length - a.length)
    .map(escapeRegExp)
  const keyAlt = keys.join('|')
  const conditions = []
  let remaining = props.search.trim()

  if (keyAlt) {
    remaining = remaining.replace(
      new RegExp(`(${keyAlt})\\s+between\\s+("[^"]*"|'[^']*'|\\S+)\\s+(?:and|to)\\s+("[^"]*"|'[^']*'|\\S+)`, 'gi'),
      (_m, key, v1, v2) => {
        conditions.push({ key, op: 'between', value: [unquote(v1), unquote(v2)] })
        return ' '
      },
    )
    remaining = remaining.replace(
      new RegExp(`(${keyAlt})\\s*(>=|<=|!=|=|>|<)\\s*("[^"]*"|'[^']*'|\\S+)`, 'gi'),
      (_m, key, op, value) => {
        conditions.push({ key, op, value: unquote(value) })
        return ' '
      },
    )
  }

  let mode = 'and'
  const terms = []
  for (const raw of remaining.match(TOKEN_RE) || []) {
    const lower = raw.toLowerCase()
    if (lower === 'or') mode = 'or'
    else if (lower !== 'and') terms.push(unquote(raw))
  }

  return { conditions, mode, terms }
})

function conditionMatches(node, cond) {
  const actual = fieldValue(node, cond.key)
  if (actual === undefined || actual === null) return false
  if (cond.op === 'between') {
    return compareValues(actual, '>=', cond.value[0]) && compareValues(actual, '<=', cond.value[1])
  }
  return compareValues(actual, cond.op, cond.value)
}

function termMatches(node, term) {
  const text = [node.label, node.value, ...props.columns.map((c) => node[c.key])].join(' ').toLowerCase()
  return text.includes(term.toLowerCase())
}

// With a search term, show only nodes that match or that lead to a match (so
// the path down to it stays visible), regardless of expanded state.
function matches(node) {
  const q = parsedQuery.value
  if (!q.conditions.length && !q.terms.length) return true
  const results = [...q.conditions.map((c) => conditionMatches(node, c)), ...q.terms.map((t) => termMatches(node, t))]
  return q.mode === 'or' ? results.some(Boolean) : results.every(Boolean)
}
function hasMatch(node) {
  return matches(node) || node.children.some(hasMatch)
}

const visibleRows = computed(() => {
  const out = []
  const searching = Boolean(props.search.trim())
  const walk = (nodes) => {
    for (const node of nodes) {
      if (searching && !hasMatch(node)) continue
      out.push(node)
      if (searching ? node.children.length : node._open) walk(node.children)
    }
  }
  walk(roots.value)
  return out
})

async function refreshNode(node) {
  node._loaded = false
  await ensureLoaded(node)
  node._open = true
}

defineExpose({ reload, expandAll, collapseAll, refreshNode, roots })
reload()
</script>
