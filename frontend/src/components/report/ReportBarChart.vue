<template>
  <div class="rounded-xl border border-app-border bg-app-panel p-4 shadow-sm">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h3 class="text-p-base font-medium text-app-text">{{ title }}</h3>
      <div v-if="legend?.length" class="flex gap-3 text-p-xs text-app-text-muted">
        <span v-for="[tone, label] in legend" :key="tone" class="inline-flex items-center gap-1.5">
          <span class="size-2.5 rounded-sm" :class="TONES[tone]" />{{ label }}
        </span>
      </div>
    </div>

    <ol class="flex max-h-[26rem] flex-col gap-2 overflow-y-auto pr-1">
      <li v-for="(bar, i) in bars" :key="i" class="grid grid-cols-[minmax(8rem,16rem)_1fr_auto] items-center gap-3 text-p-sm" :title="bar.label">
        <span class="truncate text-app-text">{{ bar.label }}</span>
        <div class="h-5 overflow-hidden rounded-md bg-app-panel-2">
          <div
            class="flex h-full items-center justify-end rounded-md pr-1.5 text-p-xs font-medium text-white transition-all"
            :class="bar.tone ? TONES[bar.tone] : 'bg-app-primary'"
            :style="{ width: `${bar.pct}%`, minWidth: bar.value ? '4px' : '0' }"
          />
        </div>
        <span class="min-w-[6rem] text-right tabular-nums text-app-text">
          {{ bar.text }}<span v-if="ratio && i > 0 && bars[0].value" class="ml-1.5 text-p-xs text-app-text-muted">({{ Math.round((bar.value / bars[0].value) * 100) }}%)</span>
        </span>
      </li>
    </ol>
  </div>
</template>

<script setup>
// A horizontal bar chart for single-series reports (interviews per customer,
// the lead funnel, revenue vs target). Unlike a stock axis chart it can colour
// each bar by a rule from the report's config, label bars with long names in
// full, and - in funnel mode - show every stage as a share of the first.
import { computed } from 'vue'

const TONES = { danger: 'bg-red-500', success: 'bg-green-500', warning: 'bg-amber-500' }

const props = defineProps({
  title: { type: String, default: '' },
  labels: { type: Array, required: true },
  values: { type: Array, required: true },
  tones: { type: Array, default: () => [] }, // per-bar 'danger' | 'success' | ...
  legend: { type: Array, default: null },
  ratio: { type: Boolean, default: false }, // funnel: % of first bar
})

const bars = computed(() => {
  const max = Math.max(...props.values.map((v) => Number(v) || 0), 1)
  return props.labels.map((label, i) => {
    const value = Number(props.values[i]) || 0
    return { label, value, text: value.toLocaleString(undefined, { maximumFractionDigits: 2 }), pct: (value / max) * 100, tone: props.tones[i] || '' }
  })
})
</script>
