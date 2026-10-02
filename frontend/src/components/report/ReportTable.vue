<template>
  <div class="flex flex-col overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-sm">
    <!-- toolbar -->
    <div class="flex flex-wrap items-center gap-3 border-b border-app-border bg-app-panel px-4 py-2.5">
      <AppSearchInput v-if="searchable" v-model="search" class="w-full sm:w-72" placeholder="Search this report" />
      <span class="text-p-xs text-app-text-muted">
        <template v-if="searchable">{{ filtered.length.toLocaleString() }} of {{ dataRows.length.toLocaleString() }} rows</template>
        <template v-else>{{ dataRows.length.toLocaleString() }} rows · {{ columns.length }} columns</template>
      </span>
      <div class="ml-auto flex items-center gap-1 rounded-lg bg-app-panel-2 p-0.5">
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-p-xs font-medium transition-colors"
          :class="compact ? 'bg-app-primary text-white shadow-sm' : 'text-app-text-muted hover:text-app-text'"
          title="Fit more rows on screen"
          @click="compact = !compact"
        >
          <span class="lucide-rows-3 size-3.5" />Compact
        </button>
      </div>
    </div>

    <div class="max-h-[70vh] min-h-0 overflow-auto">
      <table class="w-full border-separate border-spacing-0 text-p-sm">
        <thead class="sticky top-0 z-20">
          <tr>
            <th v-if="!tree" class="sticky left-0 z-30 h-10 w-12 min-w-12 border-b border-r border-app-border bg-app-panel-2 px-2 text-center text-p-xs font-medium text-app-text-muted">#</th>
            <th
              v-for="(col, ci) in columns"
              :key="col.fieldname"
              class="group/h h-10 whitespace-nowrap border-b border-r border-app-border bg-app-panel-2 px-3 text-p-xs font-semibold uppercase tracking-wide text-app-text-muted last:border-r-0"
              :class="[
                isNumeric(col) ? 'text-right' : 'text-left',
                ci === 0 && tree ? 'sticky left-0 z-30 min-w-[18rem]' : '',
                !tree ? 'cursor-pointer select-none hover:bg-app-primary-tint hover:text-app-text' : '',
                sortKey === col.fieldname ? 'text-app-primary' : '',
              ]"
              @click="!tree && sortBy(col)"
            >
              <span class="inline-flex items-center gap-1" :class="isNumeric(col) ? 'flex-row-reverse' : ''">
                {{ col.label }}
                <span v-if="sortKey === col.fieldname" :class="sortDir === 'asc' ? 'lucide-arrow-up' : 'lucide-arrow-down'" class="size-3" />
                <span v-else-if="!tree" class="lucide-arrow-up-down size-3 opacity-0 transition-opacity group-hover/h:opacity-50" />
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(row, ri) in visibleRows" :key="ri">
            <tr v-if="!Object.keys(row).length"><td :colspan="columns.length + 1" class="h-3" /></tr>
            <tr
              v-else
              class="group transition-colors"
              :class="[TINTS[tone(row)] || (!tree && ri % 2 ? 'bg-[color-mix(in_srgb,var(--app-panel-2)_55%,transparent)]' : ''), linkFor(row) ? 'cursor-pointer' : '', 'hover:bg-app-primary-tint']"
              @click="linkFor(row) && router.push(linkFor(row))"
            >
              <td v-if="!tree" class="sticky left-0 z-10 border-b border-r border-app-border bg-app-panel-2 px-2 text-center text-p-xs tabular-nums text-app-text-muted" :class="cellPad">{{ ri + 1 }}</td>
              <td
                v-for="(col, ci) in columns"
                :key="col.fieldname"
                class="border-b border-r border-app-border px-3 last:border-r-0"
                :class="[
                  cellPad,
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
        <tfoot v-if="totals" class="sticky bottom-0 z-20">
          <tr>
            <td class="sticky left-0 border-r border-t-2 border-app-border bg-app-panel-2 px-2 text-center text-p-xs font-semibold text-app-text-muted" :class="cellPad">Σ</td>
            <td
              v-for="(col, ci) in columns"
              :key="col.fieldname"
              class="whitespace-nowrap border-r border-t-2 border-app-border bg-app-panel-2 px-3 font-semibold tabular-nums text-app-text last:border-r-0"
              :class="[cellPad, isNumeric(col) ? 'text-right' : 'text-left']"
            >
              <template v-if="ci === 0 && !(col.fieldname in totals)">Total</template>
              <template v-else-if="col.fieldname in totals">{{ totals[col.fieldname] }}</template>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>

    <div v-if="hiddenCount" class="flex justify-center border-t border-app-border py-2">
      <AppButton variant="outline" size="sm" @click="limit += PAGE">Show {{ Math.min(PAGE, hiddenCount) }} more ({{ hiddenCount }} left)</AppButton>
    </div>
  </div>
</template>

<script setup>
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
// The result grid, laid out like a spreadsheet: row numbers, cell gridlines,
// banded rows, a pinned header and a pinned totals row. Flat reports get
// sortable columns, search and "show more";
// statements ('tree' layout) keep the server's row order, indent by level, bold
// their totals and pin the account column while you scroll across periods.
// Cells are formatted by fieldtype (currency with the row's own currency, dates,
// links that open the linked record), and a report config can tint rows.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import { formatCurrency, formatReportValue, isNumeric, linkTarget } from '@/utils/report/formatReport'

const PAGE = 200
const TINTS = {
  danger: 'bg-red-50/70 dark:bg-red-950/20',
  success: 'bg-green-50/70 dark:bg-green-950/20',
  muted: 'text-app-text-muted',
  strong: 'bg-app-panel-2',
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
const compact = ref(false)
// Comfortable is a roomy 44px row; compact is a tight 26px one with smaller type.
const cellPad = computed(() => (compact.value ? 'py-0 h-[26px] text-p-xs leading-none' : 'py-2.5 h-11'))

const dataRows = computed(() => props.rows.filter((r) => r && Object.keys(r).length))
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

const SUMMABLE = new Set(['Currency', 'Int'])
const numericColumns = computed(() => props.columns.filter((c) => SUMMABLE.has(c.fieldtype)))

// Pinned totals for the summable columns of the rows currently matching the
// search. Off for statements and for reports whose numbers don't add up (a
// ledger's running balance) via `totals: false` in the report config.
const totals = computed(() => {
  if (tree.value || props.config.totals === false || !numericColumns.value.length) return null
  const rows = filtered.value.filter((r) => r && Object.keys(r).length && !r.is_total_row && !r.is_opening_row && !r.is_closing_row)
  if (rows.length < 2) return null
  const out = {}
  for (const col of numericColumns.value) {
    const currencies = new Set(rows.map((r) => r.currency || props.defaultCurrency))
    if (col.fieldtype === 'Currency' && currencies.size > 1) continue // never add across currencies
    const sum = rows.reduce((s, r) => s + (Number(r[col.fieldname]) || 0), 0)
    out[col.fieldname] = col.fieldtype === 'Currency' ? formatCurrency(sum, rows[0].currency || props.defaultCurrency) : sum.toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  return Object.keys(out).length ? out : null
})

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
