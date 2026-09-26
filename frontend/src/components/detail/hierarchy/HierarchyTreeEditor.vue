<template>
  <div class="grid gap-4 md:grid-cols-[220px_1fr]">
    <div class="flex flex-col gap-2 rounded-lg border border-app-border bg-app-panel-2 p-3">
      <h4 class="text-p-sm font-semibold text-app-text">Available roles</h4>
      <p class="text-p-xs text-app-text-muted">Drag a role into the tree.</p>
      <p v-if="!available.length" class="text-p-xs text-app-text-muted">All roles are placed.</p>
      <span
        v-for="r in available"
        :key="r"
        draggable="true"
        class="flex cursor-grab items-center gap-2 rounded-md border border-app-border bg-app-panel px-2.5 py-1.5 text-p-sm text-app-text hover:border-app-primary"
        @dragstart="(e) => e.dataTransfer.setData('text/plain', r)"
      >
        <FeatherIcon name="menu" class="h-3.5 w-3.5 text-app-text-muted" />
        {{ r }}
      </span>
    </div>

    <div class="flex flex-col gap-2">
      <h4 class="text-p-sm font-semibold text-app-text">Reporting structure</h4>
      <p class="text-p-xs text-app-text-muted">
        Top = highest role. Drop a role <b>on another role</b> to make it report to it.
      </p>
      <div
        class="flex min-h-[160px] flex-col gap-2 rounded-lg border-2 border-dashed p-3 transition-colors"
        :class="rootOver ? 'border-app-primary bg-app-primary/5' : 'border-app-border'"
        @dragover.prevent="rootOver = true"
        @dragleave="rootOver = false"
        @drop.prevent="onRootDrop"
      >
        <p v-if="!tree.length" class="py-8 text-center text-p-sm text-app-text-muted">
          Drop the top-most role here to start.
        </p>
        <ul v-else class="flex flex-col gap-2">
          <HierarchyTreeNode
            v-for="n in tree"
            :key="n.role"
            :node="n"
            :available="available"
            @move="moveRole"
            @remove="removeRole"
          />
        </ul>
        <p v-if="tree.length" class="text-center text-p-xs text-app-text-muted">
          Drop here to add another top-level role
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import HierarchyTreeNode from './HierarchyTreeNode.vue'

// v-model is the flat [{parent_role, child_roles}] list the backend stores;
// the tree is derived from it, and every drag edits it through moveRole.
const rows = defineModel({ type: Array, required: true })
const props = defineProps({ roles: { type: Array, default: () => [] } })

const rootOver = ref(false)

const childSet = computed(() => new Set(rows.value.flatMap((r) => r.child_roles)))
const parents = computed(() => rows.value.map((r) => r.parent_role).filter(Boolean))

const tree = computed(() => {
  const byParent = new Map(rows.value.filter((r) => r.parent_role).map((r) => [r.parent_role, r.child_roles]))
  const build = (role, seen) => ({
    role,
    children: seen.has(role)
      ? []
      : (byParent.get(role) || []).map((c) => build(c, new Set([...seen, role]))),
  })
  return parents.value.filter((p) => !childSet.value.has(p)).map((p) => build(p, new Set()))
})

const available = computed(() => props.roles.filter((r) => !childSet.value.has(r) && !parents.value.includes(r)))

function isDescendant(role, ancestor) {
  const byParent = new Map(rows.value.map((r) => [r.parent_role, r.child_roles]))
  const stack = [...(byParent.get(ancestor) || [])]
  const seen = new Set()
  while (stack.length) {
    const cur = stack.pop()
    if (cur === role) return true
    if (seen.has(cur)) continue
    seen.add(cur)
    stack.push(...(byParent.get(cur) || []))
  }
  return false
}

function ensureRow(list, role) {
  if (!list.some((r) => r.parent_role === role)) list.push({ parent_role: role, child_roles: [] })
}

function moveRole(role, newParent) {
  if (role === newParent) return
  if (newParent && isDescendant(newParent, role)) return
  const next = rows.value.map((r) => ({ ...r, child_roles: r.child_roles.filter((c) => c !== role) }))
  ensureRow(next, role)
  if (newParent) {
    ensureRow(next, newParent)
    next.find((r) => r.parent_role === newParent).child_roles.push(role)
  }
  rows.value = next
}

function removeRole(role) {
  const own = rows.value.find((r) => r.parent_role === role)
  const next = rows.value
    .filter((r) => r.parent_role !== role)
    .map((r) => ({ ...r, child_roles: r.child_roles.filter((c) => c !== role) }))
  // Orphaned children become top-level roles instead of vanishing.
  for (const c of own?.child_roles || []) ensureRow(next, c)
  rows.value = next
}

function onRootDrop(e) {
  rootOver.value = false
  const role = e.dataTransfer.getData('text/plain')
  if (role) moveRole(role, null)
}
</script>
