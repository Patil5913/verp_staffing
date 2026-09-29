<template>
  <!-- Funnel: every stage as a centred bar, narrowing with the drop-off -->
  <div v-if="ratio" class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <h3 class="text-p-base font-semibold text-app-text">{{ title }}</h3>
    <p class="mb-4 text-p-xs text-app-text-muted">Each stage as a share of the first</p>
    <ol class="mx-auto flex max-w-3xl flex-col gap-1.5">
      <li v-for="(bar, i) in bars" :key="i" class="flex items-center gap-4" :title="`${bar.label}: ${bar.text}`">
        <span class="w-36 shrink-0 truncate text-right text-p-sm text-app-text sm:w-48">{{ bar.label }}</span>
        <div class="flex min-w-0 flex-1 justify-center">
          <div
            class="flex h-9 items-center justify-center rounded-lg px-3 text-p-sm font-semibold tabular-nums text-white shadow-sm transition-all duration-500"
            :style="{ width: `${Math.max(bar.pct, 12)}%`, background: shade(i) }"
          >
            {{ bar.text }}
          </div>
        </div>
        <span class="w-24 shrink-0 text-p-xs tabular-nums text-app-text-muted">
          {{ bars[0].value ? Math.round((bar.value / bars[0].value) * 100) : 0 }}%
          <span v-if="i > 0 && bars[i - 1].value" class="text-red-500">↓{{ Math.round((1 - bar.value / bars[i - 1].value) * 100) }}%</span>
        </span>
      </li>
    </ol>
  </div>

  <!-- Share: donut of the top items + a ranked list with each one's share -->
  <div v-else class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <div class="mb-4">
      <h3 class="text-p-base font-semibold text-app-text">{{ title }}</h3>
      <p class="text-p-xs text-app-text-muted">{{ bars.length }} {{ bars.length === 1 ? 'item' : 'items' }} · ranked by share of total</p>
    </div>
    <div class="grid items-center gap-6 md:grid-cols-[14rem_1fr]">
      <div class="relative mx-auto size-56">
        <svg viewBox="0 0 120 120" class="size-full -rotate-90">
          <circle cx="60" cy="60" :r="R" fill="none" stroke="var(--app-panel-2)" stroke-width="16" />
          <circle
            v-for="seg in segments"
            :key="seg.index"
            cx="60"
            cy="60"
            :r="R"
            fill="none"
            :stroke="seg.color"
            :stroke-width="active === seg.index ? 20 : 16"
            :stroke-dasharray="`${seg.len} ${C - seg.len}`"
            :stroke-dashoffset="-seg.offset"
            class="cursor-pointer transition-all duration-200"
            :opacity="active === -1 || active === seg.index ? 1 : 0.35"
            @mouseenter="active = seg.index"
            @mouseleave="active = -1"
          />
        </svg>
        <div class="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-8 text-center">
          <span class="max-w-full truncate text-p-xs text-app-text-muted">{{ active >= 0 ? bars[active].label : 'Total' }}</span>
          <span class="text-2xl font-semibold tabular-nums text-app-text">{{ active >= 0 ? bars[active].text : total }}</span>
          <span v-if="active >= 0" class="text-p-xs tabular-nums text-app-text-muted">{{ bars[active].share }}%</span>
        </div>
      </div>

      <ol class="flex max-h-72 flex-col gap-0.5 overflow-y-auto pr-1">
        <li
          v-for="(bar, i) in bars"
          :key="i"
          class="grid cursor-default grid-cols-[1.25rem_minmax(6rem,1fr)_minmax(3rem,8rem)_auto] items-center gap-3 rounded-lg px-2 py-1.5 text-p-sm transition-colors hover:bg-app-panel-2"
          :class="active === i ? 'bg-app-panel-2' : ''"
          :title="`${bar.label}: ${bar.text}`"
          @mouseenter="active = i"
          @mouseleave="active = -1"
        >
          <span class="size-2.5 rounded-full" :style="{ background: colorOf(i) }" />
          <span class="truncate text-app-text">{{ bar.label }}</span>
          <div class="h-1.5 overflow-hidden rounded-full bg-app-panel-2">
            <div class="h-full rounded-full transition-all duration-500" :style="{ width: `${bar.pct}%`, background: colorOf(i) }" />
          </div>
          <span class="min-w-[5.5rem] text-right tabular-nums text-app-text">
            <span class="font-medium">{{ bar.text }}</span>
            <span class="ml-1.5 text-p-xs text-app-text-muted">{{ bar.share }}%</span>
          </span>
        </li>
      </ol>
    </div>
  </div>
</template>

<script setup>
// Single-series reports that are really "who has how much" (interviews per
// customer, leads per employee, profiles per recruiter) read best as a share of
// the total: a donut for the top items and a ranked list with every item's
// percentage. The lead funnel gets its own centred funnel layout instead
// (`ratio`). Reports that colour bars by target use ReportChart's columns.
import { computed, ref } from 'vue'

const PALETTE = ['#4c7dff', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#ef4444']
const OTHER = '#94a3b8'
const R = 46
const C = 2 * Math.PI * R

const props = defineProps({
  title: { type: String, default: '' },
  labels: { type: Array, required: true },
  values: { type: Array, required: true },
  ratio: { type: Boolean, default: false }, // funnel: % of first bar
  tones: { type: Array, default: () => [] }, // used by ReportChart, accepted so they don't fall through as attributes
  legend: { type: Array, default: null },
})

const fmt = (n) => n.toLocaleString(undefined, { maximumFractionDigits: 2 })
const active = ref(-1)

const sum = computed(() => props.values.reduce((s, v) => s + (Number(v) || 0), 0))
const total = computed(() => fmt(sum.value))

const bars = computed(() => {
  const max = Math.max(...props.values.map((v) => Number(v) || 0), 1)
  const rows = props.labels.map((label, i) => ({ label, value: Number(props.values[i]) || 0 }))
  if (!props.ratio) rows.sort((a, b) => b.value - a.value)
  return rows.map((r) => ({ ...r, text: fmt(r.value), pct: (r.value / max) * 100, share: sum.value ? Math.round((r.value / sum.value) * 1000) / 10 : 0 }))
})

// Beyond the palette the rest share one neutral colour.
const colorOf = (i) => (i < PALETTE.length ? PALETTE[i] : OTHER)

const segments = computed(() => {
  let offset = 0
  const gap = bars.value.length > 1 ? 1.2 : 0
  return bars.value
    .map((b, index) => ({ index, color: colorOf(index), len: sum.value ? (b.value / sum.value) * C : 0 }))
    .filter((s) => s.len > 0)
    .map((s) => {
      const seg = { ...s, len: Math.max(s.len - gap, 0.5), offset }
      offset += s.len
      return seg
    })
})

// Funnel stages fade from strong to light down the funnel.
const shade = (i) => `color-mix(in srgb, var(--app-primary) ${Math.max(100 - i * (60 / Math.max(bars.value.length - 1, 1)), 40)}%, #8fb4ff)`
</script>
