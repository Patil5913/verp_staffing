<template>
  <Dropdown v-if="views.length" :options="options" placement="left">
    <template #default="{ open }">
      <button
        type="button"
        class="inline-flex h-7 shrink-0 items-center gap-2 rounded-lg border border-app-border bg-app-panel px-2.5 text-p-sm font-medium capitalize text-app-text transition-colors hover:bg-app-panel-2"
        :class="open ? 'bg-app-panel-2' : ''"
        title="Switch view"
      >
        <span :class="`lucide-${ICONS[current]} size-3.5 shrink-0 text-app-text-muted`" />
        <span>{{ current }}</span>
        <span class="lucide-chevron-down size-3.5 shrink-0 text-app-text-muted" />
      </button>
    </template>
  </Dropdown>
</template>

<script setup>
// List / Tree / Kanban / Calendar dropdown for a doctype - which views exist comes from
// listOptions.js's EXTRA_VIEWS, so a page just drops this in.
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Dropdown } from 'frappe-ui'
import { EXTRA_VIEWS } from '@/configs/detail/listOptions'

const props = defineProps({
  doctype: { type: String, required: true },
  current: { type: String, default: 'list' },
})
const router = useRouter()
const ICONS = { list: 'list', tree: 'git-branch', kanban: 'columns-3', calendar: 'calendar' }
const views = computed(() => EXTRA_VIEWS[props.doctype] || [])

const label = (v) => v.charAt(0).toUpperCase() + v.slice(1)
const options = computed(() => ['list', ...views.value].map((v) => ({ label: label(v), icon: v === props.current ? 'check' : undefined, onClick: () => go(v) })))

function go(view) {
  const base = `/${encodeURIComponent(props.doctype)}`
  router.push(view === 'list' ? base : `${base}/view/${view}`)
}
</script>
