<template>
  <div v-if="views.length" class="inline-flex shrink-0 items-center rounded-full border border-app-border bg-app-panel-2 p-0.5">
    <button
      v-for="view in ['list', ...views]"
      :key="view"
      type="button"
      class="inline-flex h-6 items-center gap-1 rounded-full px-2.5 text-p-xs font-medium capitalize transition-colors"
      :class="view === current ? 'bg-app-panel text-app-text shadow-sm' : 'text-app-text-muted hover:text-app-text'"
      @click="go(view)"
    >
      <span :class="`lucide-${ICONS[view]} size-3`" />{{ view }}
    </button>
  </div>
</template>

<script setup>
// List / Tree / Kanban / Calendar toggle for a doctype - which views exist comes from
// listOptions.js's EXTRA_VIEWS, so a page just drops this in.
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { EXTRA_VIEWS } from '@/configs/detail/listOptions'

const props = defineProps({
  doctype: { type: String, required: true },
  current: { type: String, default: 'list' },
})
const router = useRouter()
const ICONS = { list: 'list', tree: 'git-branch', kanban: 'columns-3', calendar: 'calendar' }
const views = computed(() => EXTRA_VIEWS[props.doctype] || [])

function go(view) {
  const base = `/${encodeURIComponent(props.doctype)}`
  router.push(view === 'list' ? base : `${base}/view/${view}`)
}
</script>
