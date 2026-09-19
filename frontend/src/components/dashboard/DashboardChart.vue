<template>
  <section class="flex min-w-0 flex-col rounded-xl border border-app-border bg-app-panel p-4 shadow-sm" :class="chart.span === 2 ? 'lg:col-span-2' : ''">
    <header class="mb-2">
      <h3 class="flex items-center gap-2 text-p-base font-medium text-app-text"><span :class="`lucide-${chartIcon(chart)} size-4 shrink-0 text-app-primary`" />{{ chart.title }}</h3>
      <p v-if="chart.subtitle" class="text-p-xs text-app-text-muted">{{ chart.subtitle }}</p>
    </header>

    <div v-if="!hasData" class="flex min-h-[220px] flex-1 flex-col items-center justify-center gap-1 text-p-sm text-app-text-muted">
      <span class="lucide-chart-no-axes-column size-6" />No data for this period
    </div>

    <ol v-else-if="chart.type === 'hbar'" class="flex max-h-[320px] flex-col gap-2 overflow-y-auto pr-1">
      <li v-for="bar in bars" :key="bar.label" class="grid grid-cols-[minmax(6rem,11rem)_1fr_auto] items-center gap-3 text-p-sm" :title="bar.label">
        <span class="truncate text-app-text">{{ bar.label }}</span>
        <div class="h-4 overflow-hidden rounded-md bg-app-panel-2">
          <div class="h-full rounded-md transition-all" :class="bar.tone" :style="{ width: `${bar.pct}%`, minWidth: bar.value ? '3px' : '0', backgroundColor: bar.tone ? undefined : PALETTE[0] }" />
        </div>
        <span class="min-w-[4.5rem] text-right tabular-nums text-app-text">{{ bar.text }}</span>
      </li>
    </ol>

    <DonutChart v-else-if="chart.type === 'donut'" :config="donutConfig" />
    <FunnelChart v-else-if="chart.type === 'funnel'" :config="funnelConfig" />
    <AxisChart v-else :config="axisConfig" />
  </section>
</template>

<script setup>
// One chart card. The server names a chart's type and hands over ready rows
// (utils/dashboard.py); this maps that onto frappe-ui's charts — or, for the
// ranked horizontal bars, draws them itself so long names show in full and
// each bar can carry a tone.
import { computed } from 'vue'
import { AxisChart, DonutChart, FunnelChart } from 'frappe-ui'
import { PALETTE, formatMetric } from '@/utils/dashboard/format'
import { chartIcon } from '@/utils/dashboard/icons'

const props = defineProps({
  chart: { type: Object, required: true },
  currency: { type: String, default: '' },
})

const TONES = { success: 'bg-green-500', danger: 'bg-red-500', warning: 'bg-amber-500', info: 'bg-blue-500' }

const seriesNames = computed(() => props.chart.series.map((s) => s.name))
const hasData = computed(() => {
  const rows = props.chart.data || []
  if (!rows.length) return false
  const keys = ['donut', 'funnel', 'hbar'].includes(props.chart.type) ? ['value'] : seriesNames.value
  return rows.some((r) => keys.some((k) => Number(r[k]) !== 0 && r[k] != null))
})

const bars = computed(() => {
  const rows = props.chart.data || []
  const max = Math.max(...rows.map((r) => Math.abs(Number(r.value) || 0)), 1)
  return rows.map((r) => ({
    label: r.label,
    value: Number(r.value) || 0,
    pct: (Math.abs(Number(r.value) || 0) / max) * 100,
    text: formatMetric(r.value, props.chart.format, props.currency, { compact: props.chart.format === 'currency' }),
    tone: TONES[r.tone] || '',
  }))
})

// frappe-ui's donut and funnel sort their data in place — hand them copies.
const rowsCopy = computed(() => (props.chart.data || []).map((r) => ({ ...r })))
const donutConfig = computed(() => ({ data: rowsCopy.value, title: '', categoryColumn: 'label', valueColumn: 'value', colors: PALETTE, maxSliceCount: 8 }))
const funnelConfig = computed(() => ({ data: rowsCopy.value, title: '', categoryColumn: 'label', valueColumn: 'value', colors: PALETTE, showPercentages: true }))

const axisConfig = computed(() => {
  const stacked = props.chart.type === 'stacked'
  return {
    data: props.chart.data || [],
    title: '',
    xAxis: { key: 'label', type: 'category' },
    yAxis: {},
    stacked,
    series: props.chart.series.map((s, i) => ({ ...s, color: s.color || PALETTE[i % PALETTE.length] })),
  }
})
</script>
