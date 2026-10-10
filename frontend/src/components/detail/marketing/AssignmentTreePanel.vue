<template>
  <SectionCard title="Hierarchy" subtitle="Reporting chain of the assignee, up to the top of the department.">
    <p v-if="!assignTo" class="py-4 text-center text-p-sm text-app-text-muted">Not assigned to anyone yet.</p>
    <div v-else-if="tree.isLoading && !tree.resource.data" class="flex justify-center py-6">
      <LoadingIndicator class="h-5 w-5 text-app-text-muted" />
    </div>
    <p v-else-if="!edges.length && !labels[assignTo]" class="py-4 text-center text-p-sm text-app-text-muted">No hierarchy found.</p>
    <HierarchyDiagram v-else :data="edges" :labels="labels" :highlight="assignTo" />
  </SectionCard>

  <SectionCard
    v-if="history.length > 1"
    title="Team history"
    subtitle="Every team that held this record, with the work done while they had it."
    class="mt-4"
  >
    <ol class="flex flex-col gap-3">
      <li
        v-for="(h, i) in history"
        :key="i"
        class="rounded-lg border p-4"
        :class="h.is_current ? 'border-app-primary' : 'border-app-border'"
      >
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-p-sm font-medium text-app-text">{{ h.employee_name }}</span>
          <span v-if="h.role" class="text-p-xs text-app-text-muted">{{ h.role }}</span>
          <span v-if="h.is_current" class="rounded-full bg-app-panel-2 px-2 py-0.5 text-p-xs font-medium text-app-primary">Current</span>
          <span class="ml-auto text-p-xs text-app-text-muted">{{ day(h.start) }} - {{ h.end ? day(h.end) : 'now' }}</span>
        </div>

        <p class="mt-2 text-p-xs text-app-text-muted">
          Team:
          <template v-for="(t, j) in h.team" :key="t.employee">
            <span v-if="j" class="px-1">&rarr;</span>
            <span :class="t.employee === h.employee ? 'font-medium text-app-text' : ''">{{ t.employee_name }}<template v-if="t.role"> ({{ t.role }})</template></span>
          </template>
        </p>

        <dl class="mt-3 grid grid-cols-3 gap-2 text-center">
          <div class="rounded-md bg-app-panel-2 py-2">
            <dt class="text-p-xs text-app-text-muted">Small applications</dt>
            <dd class="text-p-base font-semibold text-app-text">{{ h.applications.small }}</dd>
          </div>
          <div class="rounded-md bg-app-panel-2 py-2">
            <dt class="text-p-xs text-app-text-muted">Large applications</dt>
            <dd class="text-p-base font-semibold text-app-text">{{ h.applications.large }}</dd>
          </div>
          <div class="rounded-md bg-app-panel-2 py-2">
            <dt class="text-p-xs text-app-text-muted">Total applications</dt>
            <dd class="text-p-base font-semibold text-app-text">{{ h.applications.total }}</dd>
          </div>
        </dl>

        <div class="mt-3">
          <p class="text-p-xs font-medium text-app-text-muted">Interviews ({{ h.interviews.length }})</p>
          <p v-if="!h.interviews.length" class="text-p-xs text-app-text-muted">None during this period.</p>
          <ul v-else class="mt-1 flex flex-col gap-1">
            <li v-for="iv in h.interviews" :key="iv.name" class="flex flex-wrap items-center gap-2 text-p-sm">
              <RouterLink :to="`/Interview/${encodeURIComponent(iv.name)}`" class="text-app-primary hover:underline">{{ iv.company || iv.name }}</RouterLink>
              <span class="text-app-text-muted">{{ iv.role }}</span>
              <span v-if="iv.status" class="ml-auto text-p-xs text-app-text-muted">{{ iv.status }}</span>
            </li>
          </ul>
        </div>
      </li>
    </ol>
  </SectionCard>
</template>

<script setup>
// "Hierarchy" tab on a service record: the assignee and their superiors in
// the service's department (Employee Assignment Detail), drawn with the same
// diagram as the Hierarchy page.
import { computed, watch } from 'vue'
import { LoadingIndicator } from 'frappe-ui'
import SectionCard from '@/components/common/SectionCard.vue'
import HierarchyDiagram from '@/components/detail/hierarchy/HierarchyDiagram.vue'
import { useResource } from '@/composables/list/useResource'

const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, required: true },
  name: { type: String, default: '' },
  department: { type: String, default: 'Marketing' },
})

const assignTo = computed(() => props.detail.values.assign_to)

const tree = useResource({ url: 'verp_staffing.crm.api.helpers.get_assignment_tree', notifyOnError: false })

watch(
  assignTo,
  (value) => {
    if (value) tree.resource.submit({ doctype: props.doctype, name: props.name, department: props.department })
  },
  { immediate: true },
)

// Newest first, so the current team leads.
const history = computed(() => [...(tree.resource.data?.history || [])].reverse())
const day = (ts) => (ts ? String(ts).slice(0, 10) : '')

const nodes = computed(() => tree.resource.data?.nodes || [])
const labels = computed(() =>
  Object.fromEntries(nodes.value.map((n) => [n.employee, { title: n.employee_name, subtitle: n.role || '' }])),
)
// Chain as role-style rows ({ parent_role, child_roles }) so the shared
// diagram layout can draw it; a lone assignee has no edge, so add a bare row.
const edges = computed(() => {
  const rows = nodes.value.filter((n) => n.parent).map((n) => ({ parent_role: n.parent, child_roles: [n.employee] }))
  if (!rows.length && nodes.value.length) return nodes.value.map((n) => ({ parent_role: n.employee, child_roles: [] }))
  return rows
})
</script>
