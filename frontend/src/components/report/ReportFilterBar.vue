<template>
  <div class="rounded-xl border border-app-border bg-app-panel p-4 shadow-sm">
    <div class="grid grid-cols-1 items-start gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
      <div v-for="f in shown" :key="f.fieldname">
        <FieldControl
          :field="controlField(f)"
          :model-value="values[f.fieldname]"
          :link-query="linkQuery(f)"
          @update:model-value="(v) => emit('change', f.fieldname, v)"
        />
        <p v-if="f.description" class="mt-1 text-p-xs text-app-text-muted">{{ f.description }}</p>
      </div>
    </div>
    <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
      <button v-if="filters.length > LIMIT" type="button" class="text-p-sm font-medium text-app-primary hover:underline" @click="expanded = !expanded">
        {{ expanded ? 'Fewer filters' : `More filters (${filters.length - LIMIT})` }}
      </button>
      <span v-else />
      <div class="flex gap-2">
        <AppButton variant="ghost" size="sm" icon="rotate-ccw" @click="emit('reset')">Reset</AppButton>
        <AppButton size="sm" icon="play" :loading="loading" @click="emit('run')">Run</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
// The filter panel above a report. Which filters show, their link queries and
// their cascading behaviour come from the server's definitions (see
// utils/reports.py); this only draws them, reusing the same FieldControl every
// form uses — so a Link filter is the same searchable picker, a Date the same
// date input.
import { computed, ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import FieldControl from '@/components/detail/FieldControl.vue'

const LIMIT = 8
const props = defineProps({
  filters: { type: Array, required: true }, // visible filters, in order
  values: { type: Object, required: true },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['change', 'run', 'reset'])

const expanded = ref(false)
// Required filters and the first few always show; the rest fold away.
const shown = computed(() => (expanded.value || props.filters.length <= LIMIT ? props.filters : props.filters.slice(0, LIMIT)))

function controlField(f) {
  return {
    ...f,
    // A Link whose target is another filter's value (GL's Party follows Party Type).
    options: f.options_from ? props.values[f.options_from] || f.options : f.options,
    label: f.reqd ? `${f.label} *` : f.label,
    fieldtype: f.fieldtype,
  }
}

function linkQuery(f) {
  if (f.fieldtype !== 'Link') return null
  const filters = {}
  for (const [key, value] of Object.entries(f.link_filters || {})) {
    filters[key] = typeof value === 'string' && value.startsWith('$') ? props.values[value.slice(1)] : value
  }
  return { query: f.query || undefined, filters: Object.keys(filters).length ? filters : undefined }
}
</script>
