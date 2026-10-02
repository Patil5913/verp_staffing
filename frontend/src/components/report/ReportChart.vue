<template>
  <div class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="text-p-base font-semibold text-app-text">{{ title }}</h3>
        <p class="text-p-xs text-app-text-muted">{{ labels.length }} {{ labels.length === 1 ? 'period' : 'periods' }}<template v-if="series.length > 1"> · {{ series.length }} series</template></p>
      </div>
      <div class="flex items-center gap-1 rounded-lg bg-app-panel-2 p-0.5">
        <button
          v-for="t in TYPES"
          :key="t.value"
          type="button"
          class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-p-xs font-medium transition-colors"
          :class="kind === t.value ? 'bg-app-panel text-app-primary shadow-sm' : 'text-app-text-muted hover:text-app-text'"
          :title="t.label"
          @click="kind = t.value"
        >
          <span :class="`lucide-${t.icon} size-3.5`" />{{ t.label }}
        </button>
      </div>
    </div>

    <!-- legend: click a series to show or hide it -->
    <div v-if="series.length > 1" class="mb-3 flex flex-wrap gap-2">
      <button
        v-for="s in series"
        :key="s.name"
        type="button"
        class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-p-xs font-medium transition-all"
        :class="hidden.has(s.name) ? 'border-app-border text-app-text-muted opacity-50' : 'border-app-border bg-app-panel-2 text-app-text hover:border-app-primary'"
        @click="toggle(s.name)"
      >
        <span class="size-2.5 shrink-0 rounded-full" :style="{ background: s.color }" />{{ s.name }}
      </button>
    </div>

    <div v-if="legend?.length" class="mb-2 flex flex-wrap gap-4 text-p-xs text-app-text-muted">
      <span v-for="[color, label] in legend" :key="label" class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-full" :style="{ background: color }" />{{ label }}</span>
    </div>

    <div ref="host" class="relative w-full select-none" @mouseleave="hover = -1">
      <svg :width="width" :height="H" class="block overflow-visible" @mousemove="onMove">
        <defs>
          <linearGradient v-for="s in visible" :id="`${uid}-g${s.index}`" :key="s.name" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" :stop-color="s.color" stop-opacity="0.35" />
            <stop offset="100%" :stop-color="s.color" stop-opacity="0.02" />
          </linearGradient>
        </defs>

        <!-- gridlines + y labels -->
        <g v-for="t in ticks" :key="t">
          <line :x1="M.left" :x2="width - M.right" :y1="y(t)" :y2="y(t)" :stroke="t === 0 ? 'var(--app-text-muted)' : 'var(--app-border)'" :stroke-dasharray="t === 0 ? '' : '3 4'" :stroke-opacity="t === 0 ? 0.5 : 1" />
          <text :x="M.left - 8" :y="y(t)" dy="0.32em" text-anchor="end" class="fill-app-text-muted text-[11px] tabular-nums">{{ compactNum(t) }}</text>
        </g>

        <!-- hover band -->
        <rect v-if="hover >= 0" :x="bandX(hover)" :y="M.top" :width="band" :height="plotH" fill="var(--app-primary)" fill-opacity="0.06" rx="4" />

        <!-- bars -->
        <template v-if="kind === 'bar'">
          <g v-for="s in visible" :key="s.name">
            <rect
              v-for="(v, i) in s.values"
              :key="i"
              :x="barX(i, s.slot)"
              :y="Math.min(y(v), y(0))"
              :width="barW"
              :height="Math.max(Math.abs(y(v) - y(0)), v ? 2 : 0)"
              :fill="pointColors[i] || s.color"
              :fill-opacity="hover < 0 || hover === i ? 1 : 0.55"
              :rx="Math.min(4, barW / 2)"
              class="transition-[fill-opacity]"
            />
          </g>
        </template>

        <!-- line / area -->
        <template v-else>
          <g v-for="s in visible" :key="s.name">
            <path v-if="kind === 'area'" :d="areaPath(s)" :fill="`url(#${uid}-g${s.index})`" />
            <path :d="linePath(s)" fill="none" :stroke="s.color" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
            <circle v-for="(v, i) in s.values" :key="i" :cx="cx(i)" :cy="y(v)" :r="hover === i ? 5 : labels.length > 24 ? 0 : 3" :fill="hover === i ? s.color : 'var(--app-panel)'" :stroke="s.color" stroke-width="2" />
          </g>
        </template>

        <!-- x labels -->
        <text v-for="i in labelIdx" :key="i" :x="cx(i)" :y="H - 10" text-anchor="middle" class="text-[11px]" :class="hover === i ? 'fill-app-text font-medium' : 'fill-app-text-muted'">{{ shortLabel(labels[i]) }}</text>
      </svg>

      <!-- tooltip -->
      <div
        v-if="hover >= 0"
        class="pointer-events-none absolute z-10 min-w-[9rem] rounded-lg border border-app-border bg-app-panel px-3 py-2 text-p-xs shadow-lg"
        :style="tipStyle"
      >
        <p class="mb-1 font-semibold text-app-text">{{ labels[hover] }}</p>
        <p v-for="s in visible" :key="s.name" class="flex items-center justify-between gap-4">
          <span class="inline-flex items-center gap-1.5 text-app-text-muted"><span class="size-2 rounded-full" :style="{ background: s.color }" />{{ s.name }}</span>
          <span class="font-medium tabular-nums text-app-text">{{ full(s.values[hover]) }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
// The multi-series chart for period reports (Balance Sheet, Profit and Loss,
// interviews over time, call duration). Drawn as plain SVG so it can match the
// app's theme: dashed gridlines, compact axis numbers, a hover band with a
// tooltip listing every series, a legend whose chips show or hide a series, and a bars / line / area switch. Colours come from the
// report when it names them, else a fixed palette.
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue'

const PALETTE = ['#4c7dff', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899']
const TYPES = [
  { value: 'bar', label: 'Bars', icon: 'bar-chart-3' },
  { value: 'line', label: 'Line', icon: 'line-chart' },
  { value: 'area', label: 'Area', icon: 'area-chart' },
]

const props = defineProps({
  title: { type: String, default: '' },
  labels: { type: Array, required: true },
  datasets: { type: Array, required: true }, // [{ name, values }]
  colors: { type: Array, default: () => [] },
  type: { type: String, default: 'bar' },
  currency: { type: String, default: '' },
  pointColors: { type: Array, default: () => [] }, // single series: one colour per bar
  legend: { type: Array, default: null }, // [[colour, label]] shown under the chart
})

const uid = useId()
const H = 300
const M = { top: 12, right: 12, bottom: 34, left: 52 }
const plotH = H - M.top - M.bottom

const kind = ref(TYPES.some((t) => t.value === props.type) ? props.type : 'bar')
const hidden = ref(new Set())
const hover = ref(-1)
const host = ref(null)
const width = ref(600)
let ro

onMounted(() => {
  width.value = host.value?.clientWidth || 600
  ro = new ResizeObserver(([e]) => (width.value = Math.max(e.contentRect.width, 240)))
  ro.observe(host.value)
})
onBeforeUnmount(() => ro?.disconnect())

const series = computed(() =>
  props.datasets.map((ds, index) => {
    const values = props.labels.map((_, i) => Number(ds.values?.[i]) || 0)
    return { name: ds.name || `Series ${index + 1}`, index, values, total: values.reduce((a, b) => a + b, 0), color: props.colors[index] || PALETTE[index % PALETTE.length] }
  }),
)
const visible = computed(() => {
  const shown = series.value.filter((s) => !hidden.value.has(s.name))
  return shown.map((s, slot) => ({ ...s, slot }))
})
function toggle(name) {
  const next = new Set(hidden.value)
  if (next.has(name)) next.delete(name)
  else if (next.size < series.value.length - 1) next.add(name) // always keep one on screen
  hidden.value = next
}

// ── scale ──
function niceStep(range, count) {
  const raw = range / count
  const pow = 10 ** Math.floor(Math.log10(raw || 1))
  const f = raw / pow
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow
}
const extent = computed(() => {
  const all = visible.value.flatMap((s) => s.values)
  const min = Math.min(0, ...all)
  const max = Math.max(0, ...all)
  const step = niceStep((max - min) || 1, 5)
  return { lo: Math.floor(min / step) * step, hi: Math.ceil(max / step) * step || step, step }
})
const ticks = computed(() => {
  const { lo, hi, step } = extent.value
  const out = []
  for (let t = lo; t <= hi + step / 2; t += step) out.push(Math.abs(t) < step / 1e6 ? 0 : t)
  return out
})
const y = (v) => M.top + plotH - ((v - extent.value.lo) / (extent.value.hi - extent.value.lo || 1)) * plotH

const plotW = computed(() => width.value - M.left - M.right)
const band = computed(() => plotW.value / Math.max(props.labels.length, 1))
const cx = (i) => M.left + band.value * (i + 0.5)
const bandX = (i) => M.left + band.value * i
const group = computed(() => Math.min(band.value * 0.7, 56 * visible.value.length))
const barW = computed(() => Math.max(group.value / Math.max(visible.value.length, 1) - 3, 2))
const barX = (i, slot) => cx(i) - group.value / 2 + slot * (group.value / visible.value.length) + 1.5

function linePath(s) {
  return s.values.map((v, i) => `${i ? 'L' : 'M'}${cx(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
}
function areaPath(s) {
  const last = s.values.length - 1
  return `${linePath(s)} L${cx(last).toFixed(1)},${y(0).toFixed(1)} L${cx(0).toFixed(1)},${y(0).toFixed(1)} Z`
}

// Thin the x labels so they never overlap.
const labelIdx = computed(() => {
  const n = props.labels.length
  const longest = Math.max(...props.labels.map((l) => String(l).length), 1)
  const fit = Math.max(Math.floor(plotW.value / (Math.min(longest, 12) * 7 + 16)), 1)
  const every = Math.ceil(n / fit)
  return props.labels.map((_, i) => i).filter((i) => i % every === 0)
})
const shortLabel = (l) => {
  const s = String(l)
  return s.length > 14 ? `${s.slice(0, 13)}…` : s
}

function onMove(e) {
  const x = e.clientX - e.currentTarget.getBoundingClientRect().left - M.left
  hover.value = x < 0 || x > plotW.value ? -1 : Math.min(Math.floor(x / band.value), props.labels.length - 1)
}
const tipStyle = computed(() => {
  const x = cx(hover.value)
  const right = x > width.value / 2
  return { top: `${M.top}px`, ...(right ? { right: `${width.value - x + 12}px` } : { left: `${x + 12}px` }) }
})

const compactNum = (n) => Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(n)
const full = (n) => {
  const v = Number(n) || 0
  if (props.currency) {
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: props.currency, maximumFractionDigits: 2 }).format(v)
    } catch {
      // fall through to a plain number
    }
  }
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
}
</script>
