<template>
  <div class="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8">
    <h1 class="text-2xl font-semibold text-app-text">{{ reportName }}</h1>

    <StateBanner
      v-if="filterMeta.hasError"
      icon="alert-triangle"
      title="Couldn't load this report"
      :description="filterMeta.errorMessage"
    />

    <template v-else>
      <div v-if="filterFields.length" class="flex flex-wrap items-end gap-3 rounded-lg border border-app-border bg-app-panel p-4">
        <div v-for="field in filterFields" :key="field.fieldname" class="w-48">
          <FormControl
            :type="controlType(field)"
            :label="field.label"
            :model-value="filterValues[field.fieldname]"
            :options="selectOptions(field)"
            @update:model-value="(v) => (filterValues[field.fieldname] = v)"
          />
        </div>
        <Button variant="solid" :loading="run.loading" @click="onRun">Run</Button>
      </div>

      <StateBanner
        v-if="run.hasError"
        icon="alert-triangle"
        title="Couldn't run this report"
        :description="run.errorMessage"
      />
      <div v-else-if="run.isLoading" class="flex justify-center py-16">
        <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
      </div>

      <template v-else-if="result">
        <div v-if="summaryTiles.length" class="flex flex-wrap gap-3">
          <div
            v-for="tile in summaryTiles"
            :key="tile.label"
            class="min-w-[160px] flex-1 rounded-lg border border-app-border bg-app-panel px-4 py-3"
          >
            <div class="text-p-sm text-app-text-muted">{{ tile.label }}</div>
            <div class="mt-1 text-lg font-semibold" :class="tileColor(tile.indicator)">{{ tile.value }}</div>
          </div>
        </div>

        <div v-if="axisChartConfig" class="rounded-lg border border-app-border bg-app-panel p-4">
          <AxisChart v-bind="axisChartConfig" />
        </div>

        <StateBanner v-if="!rows.length" icon="inbox" title="No data" description="This report returned no rows for the selected filters." />
        <div v-else class="overflow-auto rounded-lg border border-app-border bg-app-panel">
          <table class="w-full text-left text-p-base">
            <thead class="border-b border-app-border text-p-sm text-app-text-muted">
              <tr>
                <th v-for="col in columns" :key="col.fieldname" class="whitespace-nowrap px-4 py-2 font-medium">
                  {{ col.label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in rows" :key="i" class="border-b border-app-border last:border-0">
                <td v-for="col in columns" :key="col.fieldname" class="whitespace-nowrap px-4 py-2">
                  {{ row[col.fieldname] }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { AxisChart, Button, FormControl, LoadingIndicator } from 'frappe-ui'
import { useResource } from '@/composables/useResource'
import StateBanner from '@/components/StateBanner.vue'

const route = useRoute()
const reportName = computed(() => route.params.reportName)

const filterMeta = useResource({
  url: 'verp_staffing.utils.reports.get_report_filters',
  makeParams: () => ({ report_name: reportName.value }),
  auto: true,
})

const filterFields = computed(() => filterMeta.resource.data?.filters || [])
const filterValues = reactive({})

watch(
  filterFields,
  (fields) => {
    Object.keys(filterValues).forEach((k) => delete filterValues[k])
    for (const f of fields) {
      filterValues[f.fieldname] = f.default ?? ''
    }
  },
  { immediate: true },
)

const TYPE_MAP = {
  Date: 'date',
  Datetime: 'datetime-local',
  Int: 'number',
  Float: 'number',
  Check: 'checkbox',
  Select: 'select',
  Link: 'text', // no dedicated link-picker in this pass; plain text entry of the linked name
  Data: 'text',
}
function controlType(field) {
  return TYPE_MAP[field.fieldtype] || 'text'
}
function selectOptions(field) {
  if (field.fieldtype !== 'Select') return undefined
  return (field.options || '').split('\n').map((v) => ({ label: v || '(any)', value: v }))
}

const run = useResource({
  url: 'frappe.desk.query_report.run',
  notifyOnError: true,
})

function onRun() {
  const filters = {}
  for (const [k, v] of Object.entries(filterValues)) {
    if (v !== '' && v !== null && v !== undefined) filters[k] = v
  }
  run.resource.submit({ report_name: reportName.value, filters })
}

// Auto-run once filters have loaded, so a report with no required filters
// shows data immediately instead of an empty page.
watch(
  () => filterMeta.resource.data,
  (data) => {
    if (data) onRun()
  },
)

const result = computed(() => run.resource.data)
const columns = computed(() => result.value?.columns || [])
const rows = computed(() => result.value?.result || [])

const summaryTiles = computed(() =>
  (result.value?.report_summary || []).map((s) => ({
    label: s.label,
    value: s.value,
    indicator: s.indicator,
  })),
)

function tileColor(indicator) {
  if (indicator === 'green' || indicator === 'Green') return 'text-green-600'
  if (indicator === 'red' || indicator === 'Red') return 'text-red-600'
  return 'text-app-text'
}

// frappe-charts-shaped {data:{labels,datasets}, type} -> frappe-ui's
// AxisChart config. Only bar/line/area map cleanly onto an axis chart;
// other chart types (pie, percentage) aren't rendered here.
const axisChartConfig = computed(() => {
  const chart = result.value?.chart
  const labels = chart?.data?.labels
  const datasets = chart?.data?.datasets
  const type = ['bar', 'line', 'area'].includes(chart?.type) ? chart.type : 'bar'
  if (!labels?.length || !datasets?.length) return null

  const data = labels.map((label, i) => {
    const row = { category: label }
    for (const ds of datasets) row[ds.name] = ds.values?.[i]
    return row
  })

  return {
    data,
    title: '',
    xAxis: { key: 'category', type: 'category' },
    yAxis: {},
    series: datasets.map((ds) => ({ name: ds.name, type })),
  }
})
</script>
