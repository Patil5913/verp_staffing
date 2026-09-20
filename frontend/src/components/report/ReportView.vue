<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar :title="reportName">
      <template #left>
        <router-link to="/reports" class="inline-flex items-center gap-1 text-p-sm text-app-text-muted hover:text-app-primary">
          <span class="lucide-chevron-left size-4" />All reports
        </router-link>
      </template>
      <p v-if="description" class="truncate text-p-sm text-app-text-muted">{{ description }}</p>
      <template #right>
        <AppButton variant="outline" size="sm" icon="download" :disabled="!rows.length" @click="exportCsv">Export CSV</AppButton>
        <AppButton variant="ghost" icon="refresh-cw" tooltip="Run again" :loading="run.isLoading" @click="execute" />
      </template>
    </SubNavbar>

    <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-3 md:px-6 py-4">
      <StateBanner v-if="meta.hasError" icon="alert-triangle" title="Couldn't open this report" :description="meta.errorMessage" />

      <template v-else-if="ready">
        <ReportFilterBar v-if="visibleFilters.length" :filters="visibleFilters" :values="values" :loading="run.isLoading" @change="setValue" @run="execute" @reset="reset" />

        <StateBanner v-if="run.hasError" icon="alert-triangle" title="Couldn't run this report" :description="run.errorMessage" />
        <div v-else-if="run.isLoading && !result" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

        <template v-else-if="result">
          <div v-if="message" class="rounded-xl border border-sky-300 bg-sky-50 px-4 py-3 text-p-sm text-sky-800" v-html="message" />

          <div v-if="tiles.length" class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <div v-for="t in tiles" :key="t.label" class="rounded-xl border border-app-border bg-app-panel px-4 py-3 shadow-sm">
              <p class="text-p-xs font-medium uppercase tracking-wide text-app-text-muted">{{ t.label }}</p>
              <p class="mt-0.5 truncate text-lg font-semibold tabular-nums" :class="t.tone">{{ t.text }}</p>
            </div>
          </div>

          <ReportBarChart v-if="barChart" v-bind="barChart" />
          <div v-else-if="axisConfig" class="rounded-xl border border-app-border bg-app-panel p-4 shadow-sm"><AxisChart :config="axisConfig" /></div>

          <StateBanner
            v-if="!dataRows.length"
            icon="inbox"
            title="No data"
            :description="config.empty || 'This report returned no rows for the selected filters.'"
          />
          <ReportTable v-else :columns="shownColumns" :rows="rows" :config="config" :default-currency="currency" />
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
// One report on screen: filters (server-defined), then summary tiles, a chart,
// and the table — each optional, driven by what the report returned plus its
// presentation config (reportConfigs.js). Financial statements, ledgers,
// funnels and target tracking all go through here; only the config differs.
import { computed } from 'vue'
import { AxisChart, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import ReportBarChart from '@/components/report/ReportBarChart.vue'
import ReportFilterBar from '@/components/report/ReportFilterBar.vue'
import ReportTable from '@/components/report/ReportTable.vue'
import { REPORT_CONFIGS } from '@/configs/reports'
import { useReport } from '@/composables/report/useReport'
import { downloadCsv, formatCurrency, toCsv } from '@/utils/report/formatReport'

const props = defineProps({ reportName: { type: String, required: true } })

const { meta, visibleFilters, values, setValue, reset, execute, run, result, columns, rows, ready } = useReport(computed(() => props.reportName))

const config = computed(() => REPORT_CONFIGS[props.reportName] || {})
const description = computed(() => meta.resource.data?.description || '')
const dataRows = computed(() => rows.value.filter((r) => r && Object.keys(r).length))
const shownColumns = computed(() => columns.value.filter((c) => !(config.value.hidden || []).includes(c.fieldname)))

// Unmarked amounts (a row with no currency of its own) use the report's
// currency filter, else the first row's currency.
const currency = computed(() => {
  const fromFilter = config.value.currencyFromFilter && values[config.value.currencyFromFilter]
  return fromFilter || dataRows.value.find((r) => r.currency)?.currency || result.value?.summary_currency || ''
})

const message = computed(() => {
  const m = result.value?.message
  return Array.isArray(m) ? m.join('<br>') : m || ''
})

const TONES = { green: 'text-green-600', red: 'text-red-600', orange: 'text-orange-600', blue: 'text-app-text' }
const tiles = computed(() =>
  (result.value?.report_summary || []).map((s) => ({
    label: s.label,
    text: s.datatype === 'Currency' ? formatCurrency(s.value, s.currency || currency.value) : typeof s.value === 'number' ? s.value.toLocaleString() : String(s.value ?? ''),
    tone: TONES[String(s.indicator || '').toLowerCase()] || 'text-app-text',
  })),
)

// ── chart: frappe-charts shape {data:{labels,datasets}, type} ─────────────
const chart = computed(() => result.value?.chart)
const single = computed(() => chart.value?.data?.datasets?.length === 1)

const barChart = computed(() => {
  const c = chart.value
  const mode = config.value.chart?.mode
  if (!c?.data?.labels?.length || !c.data.datasets?.length) return null
  if (mode === 'axis' || !(mode === 'bars' || mode === 'funnel' || (!mode && single.value && c.type === 'bar'))) return null
  const ds = c.data.datasets[0]
  const colorBy = config.value.chart?.colorBy
  return {
    title: c.title || props.reportName,
    labels: c.data.labels,
    values: ds.values,
    // Report rows line up with chart bars by position (as on desk).
    tones: colorBy ? dataRows.value.map((r) => colorBy(r)) : [],
    legend: config.value.chart?.legend || null,
    ratio: mode === 'funnel',
  }
})

const axisConfig = computed(() => {
  const c = chart.value
  if (barChart.value || !c?.data?.labels?.length || !c.data.datasets?.length) return null
  const type = ['bar', 'line', 'area'].includes(c.type) ? c.type : 'bar'
  const data = c.data.labels.map((label, i) => {
    const row = { category: label }
    for (const ds of c.data.datasets) row[ds.name] = ds.values?.[i]
    return row
  })
  return {
    data,
    title: c.title || '',
    xAxis: { key: 'category', type: 'category' },
    yAxis: {},
    series: c.data.datasets.map((ds, i) => ({ name: ds.name, type, ...(c.colors?.[i] ? { color: c.colors[i] } : {}) })),
  }
})

function exportCsv() {
  downloadCsv(`${props.reportName.replace(/\s+/g, '_')}.csv`, toCsv(shownColumns.value, rows.value, currency.value))
}
</script>
