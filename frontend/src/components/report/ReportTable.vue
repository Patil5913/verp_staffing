<template>
  <div class="flex min-h-0 flex-col rounded-xl border border-app-border bg-app-panel shadow-sm">
    <div v-if="searchable" class="flex items-center gap-3 border-b border-app-border px-4 py-2">
      <AppSearchInput v-model="search" class="w-full sm:w-72" placeholder="Search this report">
      </AppSearchInput>
      <span class="text-p-xs text-app-text-muted">{{ filtered.length }} of {{ dataRows.length }} rows</span>
    </div>

    <div class="min-h-0 flex-1 overflow-auto">
      <table class="w-full border-separate border-spacing-0 text-p-sm">
        <thead class="sticky top-0 z-20">
          <tr>
            <th
              v-for="(col, ci) in columns"
              :key="col.fieldname"
              class="h-10 whitespace-nowrap border-b border-app-border bg-app-panel-2 px-3 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted"
              :class="[isNumeric(col) ? 'text-right' : 'text-left', ci === 0 && tree ? 'sticky left-0 z-30 min-w-[18rem]' : '', !tree ? 'cursor-pointer select-none hover:text-app-text' : '']"
              @click="!tree && sortBy(col)"
            >
              <span class="inline-flex items-center gap-1">
                {{ col.label }}
                <FeatherIcon v-if="sortKey === col.fieldname" :name="sortDir === 'asc' ? 'arrow-up' : 'arrow-down'" class="h-3 w-3" />
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(row, ri) in visibleRows" :key="ri">
            <tr v-if="!Object.keys(row).length"><td :colspan="columns.length" class="h-3" /></tr>
            <tr
              v-else
              class="group transition-colors"
              :class="[TINTS[tone(row)] || '', linkFor(row) ? 'cursor-pointer' : '', 'hover:bg-app-panel-2']"
              @click="linkFor(row) && router.push(linkFor(row))"
            >
              <td
                v-for="(col, ci) in columns"
                :key="col.fieldname"
                class="border-b border-app-border/60 px-3 py-2"
                :class="[
                  isNumeric(col) ? 'whitespace-nowrap text-right tabular-nums' : 'max-w-[26rem] truncate',
                  ci === 0 && tree ? ['sticky left-0 z-10', TINTS[tone(row)] || 'bg-app-panel'] : '',
                  emphasised(row) ? 'font-semibold text-app-text' : 'text-app-text',
                ]"
                :style="ci === 0 && tree ? { paddingLeft: `${12 + (Number(row.indent) || 0) * 18}px` } : null"
                :title="!isNumeric(col) ? String(row[col.fieldname] ?? '') : undefined"
              >
                <router-link
                  v-if="targetFor(col, row)"
                  :to="targetFor(col, row)"
                  class="text-app-primary hover:underline"
                  @click.stop
                >
                  {{ display(col, row) }}
                </router-link>
                <span v-else :class="numberTone(col, row)">{{ display(col, row) }}</span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="hiddenCount" class="flex justify-center border-t border-app-border py-2">
      <AppButton variant="outline" size="sm" @click="limit += PAGE">Show {{ Math.min(PAGE, hiddenCount) }} more ({{ hiddenCount }} left)</AppButton>
    </div>
  </div>
</template>

<script setup>
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
// The result grid. Flat reports get sortable columns, search and "show more";
// statements ('tree' layout) keep the server's row order, indent by level, bold
// their totals and pin the account column while you scroll across periods.
// Cells are formatted by fieldtype (currency with the row's own currency, dates,
// links that open the linked record), and a report config can tint rows.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { formatReportValue, isNumeric, linkTarget } from '@/utils/report/formatReport'

const PAGE = 200
const TINTS = {
  danger: 'bg-red-50/70 dark:bg-red-950/20',
  success: 'bg-green-50/70 dark:bg-green-950/20',
  muted: 'text-app-text-muted',
  strong: 'bg-app-panel-2/70',
  total: 'bg-app-panel-2',
}

const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
  config: { type: Object, default: () => ({}) },
  defaultCurrency: { type: String, default: '' },
})

const router = useRouter()
const tree = computed(() => props.config.layout === 'tree')
const searchable = computed(() => Boolean(props.config.searchable) && !tree.value)

const search = ref('')
const sortKey = ref('')
const sortDir = ref('asc')
const limit = ref(PAGE)

const dataRows = computed(() => props.rows.filter((r) => r))
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  const base = q ? dataRows.value.filter((r) => Object.values(r).some((v) => String(v ?? '').toLowerCase().includes(q))) : props.rows.filter((r) => r !== null)
  if (!sortKey.value) return base
  const col = props.columns.find((c) => c.fieldname === sortKey.value)
  const dir = sortDir.value === 'asc' ? 1 : -1
  // Summary rows (opening / total / closing) stay pinned where the report put them.
  return [...base].sort((a, b) => {
    const x = a[sortKey.value]
    const y = b[sortKey.value]
    if (x === y) return 0
    if (x === '' || x == null) return 1
    if (y === '' || y == null) return -1
    return (isNumeric(col) ? Number(x) - Number(y) : String(x).localeCompare(String(y), undefined, { numeric: true })) * dir
  })
})
const visibleRows = computed(() => filtered.value.slice(0, limit.value))
const hiddenCount = computed(() => Math.max(filtered.value.length - limit.value, 0))

function sortBy(col) {
  if (sortKey.value === col.fieldname) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else {
    sortKey.value = col.fieldname
    sortDir.value = isNumeric(col) ? 'desc' : 'asc'
  }
}

const tone = (row) => props.config.rowClass?.(row) || ''
const emphasised = (row) => Boolean(row.bold) || ['strong', 'total'].includes(tone(row))
const linkFor = (row) => props.config.linkRow?.(row) || null
const targetFor = (col, row) => linkTarget(col, row[col.fieldname])
const display = (col, row) => formatReportValue(row[col.fieldname], col, row, props.defaultCurrency)
// Negative amounts read red - a credit balance, a loss, a shortfall.
const numberTone = (col, row) => (isNumeric(col) && Number(row[col.fieldname]) < 0 ? 'text-red-600' : '')
</script>
