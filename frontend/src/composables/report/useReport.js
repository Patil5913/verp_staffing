import { computed, reactive, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import { useRoute, useRouter } from 'vue-router'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import { normalizeColumns } from '@/utils/report/formatReport'

// One report's whole lifecycle: load its filter definitions + smart defaults
// (utils/reports.py), hold the filter values (URL query wins over defaults, so
// a link like "View Ledger" opens pre-filtered), apply the desk's cascading
// behaviour as you edit (dependent visibility, "setting X clears Y", company ->
// fiscal year / currency, fiscal year -> dates), run the report, and keep the
// URL in step with the last run so a filtered view can be shared.
export function useReport(reportName) {
  const route = useRoute()
  const router = useRouter()

  const meta = useResource({
    url: 'verp_staffing.utils.reports.get_report_filters',
    makeParams: () => ({ report_name: reportName.value }),
    auto: true,
  })

  const filters = computed(() => meta.resource.data?.filters || [])
  const values = reactive({})
  const ready = ref(false)

  // `eval:` expressions come from utils/reports.py (this repo), never user input.
  function passes(filter) {
    const expr = filter.depends_on
    if (!expr) return true
    try {
      return Boolean(new Function('doc', `return (${expr.replace(/^eval:/, '')})`)(values))
    } catch {
      return true
    }
  }
  const visibleFilters = computed(() => filters.value.filter(passes))

  // Merge defaults with whatever the URL asked for.
  watch(
    () => meta.resource.data,
    (data) => {
      if (!data) return
      Object.keys(values).forEach((k) => delete values[k])
      Object.assign(values, data.defaults || {})
      for (const f of data.filters) {
        const fromUrl = route.query[f.fieldname]
        if (fromUrl !== undefined && fromUrl !== '') values[f.fieldname] = f.fieldtype === 'Check' || f.fieldtype === 'Int' ? Number(fromUrl) : fromUrl
      }
      ready.value = true
    },
    { immediate: true },
  )

  function reset() {
    const data = meta.resource.data
    if (!data) return
    Object.keys(values).forEach((k) => delete values[k])
    Object.assign(values, data.defaults || {})
  }

  const byName = (name) => filters.value.find((f) => f.fieldname === name)

  async function setValue(fieldname, value) {
    const f = byName(fieldname)
    if (!f) return
    if (f.max && Number(value) > f.max) {
      notify.warning(`Maximum allowed ${f.label.toLowerCase()} is ${f.max}.`)
      value = f.max
    }
    values[fieldname] = value

    // desk on_change: choosing this empties those.
    if (value !== '' && value !== null && value !== undefined) {
      for (const other of f.clears || []) values[other] = ''
    } else if (fieldname === 'party_type') {
      values.party = ''
    }

    if (fieldname === 'company' && value) await applyCompany(value)
    if (f.sets_dates && value) {
      try {
        const r = await call('verp_staffing.utils.reports.get_fiscal_year_dates', { fiscal_year: value })
        if (r?.from) {
          values.from_date = r.from
          values.to_date = r.to
        }
      } catch {
        // the report validates dates itself
      }
    }
  }

  // Changing company re-derives what hangs off it (desk's _apply_company_defaults).
  async function applyCompany(company) {
    const hasFiscal = byName('from_fiscal_year') || byName('fiscal_year')
    const hasCurrency = byName('currency')
    if (!hasFiscal && !hasCurrency) return
    try {
      const d = await call('verp_staffing.utils.reports.get_company_report_defaults', { company })
      if (hasCurrency && d.currency) values.currency = d.currency
      if (d.latest_fiscal_year) {
        if (byName('from_fiscal_year')) values.from_fiscal_year = values.to_fiscal_year = d.latest_fiscal_year
        if (byName('fiscal_year')) {
          values.fiscal_year = d.latest_fiscal_year
          values.from_date = d.fy_start
          values.to_date = d.fy_end
        }
      }
    } catch {
      // leave the filters as they were
    }
  }

  // ── run ──
  const run = useResource({ url: 'frappe.desk.query_report.run', notifyOnError: true })
  const hasRun = ref(false)

  const missing = computed(() => visibleFilters.value.filter((f) => f.reqd && (values[f.fieldname] === '' || values[f.fieldname] == null)))

  function execute() {
    if (missing.value.length) {
      notify.error(`Please set: ${missing.value.map((f) => f.label).join(', ')}`)
      return
    }
    const payload = {}
    for (const f of visibleFilters.value) {
      const v = values[f.fieldname]
      // An unticked check is simply absent - the reports read a missing key as false.
      if (v !== '' && v !== null && v !== undefined && v !== false && v !== 0) payload[f.fieldname] = v
    }
    hasRun.value = true
    router.replace({ query: Object.fromEntries(Object.entries(payload).map(([k, v]) => [k, String(v)])) })
    return run.resource.submit({ report_name: reportName.value, filters: payload, ignore_prepared_report: true })
  }

  // Open on data: run once the defaults are in (unless a required filter has
  // no default yet, e.g. a brand-new site with no company).
  watch(ready, (isReady) => {
    if (isReady && !missing.value.length) execute()
  })

  const result = computed(() => run.resource.data)
  const columns = computed(() => normalizeColumns(result.value?.columns))
  const rows = computed(() => result.value?.result || [])

  return { meta, filters, visibleFilters, values, setValue, reset, execute, run, hasRun, result, columns, rows, ready, missing }
}
