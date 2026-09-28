<template>
  <component
    :is="kpi.href ? 'router-link' : 'div'"
    :to="kpi.href || undefined"
    :title="kpi.calc"
    class="group flex min-w-0 flex-col gap-1.5 rounded-xl border border-app-border bg-app-panel px-4 py-3 shadow-sm transition-colors"
    :class="kpi.href ? 'hover:border-app-primary/50' : ''"
  >
    <div class="flex items-center justify-between gap-2">
      <p class="truncate text-p-xs font-medium uppercase tracking-wide text-app-text-muted" :title="kpi.label">{{ kpi.label }}</p>
      <span v-if="kpi.icon" class="flex size-7 shrink-0 items-center justify-center rounded-lg" :class="iconTone">
        <span :class="`lucide-${kpi.icon} size-3.5`" />
      </span>
    </div>
    <p class="truncate text-xl font-semibold tabular-nums" :class="valueTone" :title="kpi.calc ? `${full}\n${kpi.calc}` : full">{{ text }}</p>
    <div class="flex min-h-4 items-center gap-2 text-p-xs">
      <span v-if="kpi.delta !== null && kpi.delta !== undefined" class="inline-flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-0.5 font-medium" :class="deltaTone">
        <span :class="kpi.delta >= 0 ? 'lucide-arrow-up-right size-3' : 'lucide-arrow-down-right size-3'" />{{ Math.abs(kpi.delta).toLocaleString(undefined, { maximumFractionDigits: 1 }) }}%
      </span>
      <span v-if="kpi.hint || (kpi.delta !== null && kpi.delta !== undefined)" class="truncate text-app-text-muted" :title="kpi.hint">{{ kpi.hint || 'vs previous period' }}</span>
    </div>
  </component>
</template>

<script setup>
// One headline number: value, change against the previous period (green when
// better, red when worse - `invert` flips that for costs), and a hint.
import { computed } from 'vue'
import { formatMetric } from '@/utils/dashboard/format'

const props = defineProps({
  kpi: { type: Object, required: true },
  currency: { type: String, default: '' },
})

const text = computed(() => formatMetric(props.kpi.value, props.kpi.format, props.currency, { compact: props.kpi.format === 'currency' }))
const full = computed(() => formatMetric(props.kpi.value, props.kpi.format, props.currency))

const valueTone = computed(() => ({ good: 'text-green-600', bad: 'text-red-600', warn: 'text-amber-600' })[props.kpi.tone] || 'text-app-text')
const iconTone = computed(() => ({ good: 'bg-green-500/10 text-green-600', bad: 'bg-red-500/10 text-red-600', warn: 'bg-amber-500/10 text-amber-600' })[props.kpi.tone] || 'bg-app-primary-tint text-app-primary')
const deltaTone = computed(() => {
  const better = props.kpi.invert ? props.kpi.delta <= 0 : props.kpi.delta >= 0
  return better ? 'bg-green-500/10 text-green-600' : 'bg-red-500/10 text-red-600'
})
</script>
