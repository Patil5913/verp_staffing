import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useResource } from '@/composables/list/useResource'
import { presetRange } from '@/utils/dashboard/format'

const PRESET_KEY = 'verp.dashboard.preset'
const readPreset = () => {
  try {
    return localStorage.getItem(PRESET_KEY) || 'last_30'
  } catch {
    return 'last_30'
  }
}

// One dashboard tab's whole lifecycle: which tabs the user may open, the
// selected range and company, and the board the server builds for them
// (utils/dashboard.py). The tab comes from the URL (/dashboard/:section), so a
// tab is linkable; range and company are remembered per browser.
export function useDashboard() {
  const route = useRoute()

  const meta = useResource({ url: 'verp_staffing.utils.dashboard.get_dashboard_meta', auto: true })
  const sections = computed(() => meta.resource.data?.sections || [])
  const companies = computed(() => meta.resource.data?.companies || [])

  const section = computed(() => route.params.section || 'overview')
  const preset = ref(readPreset())
  const custom = reactive({ from: '', to: '' })
  const company = ref('')
  const range = computed(() => presetRange(preset.value, custom))

  watch(
    () => meta.resource.data,
    (data) => {
      if (data && !company.value) company.value = data.company || ''
    },
    { immediate: true },
  )

  const board = useResource({ url: 'verp_staffing.utils.dashboard.get_dashboard', notifyOnError: false })

  // A slow answer for the tab you just left must not paint over the one you're
  // on: the board says which section/range it belongs to.
  const data = computed(() => {
    const d = board.resource.data
    return d && d.section === section.value && d.period?.from === range.value.from && d.period?.to === range.value.to ? d : null
  })

  const ready = computed(() => meta.resource.data && (company.value || !companies.value.length))
  function load(refresh = false) {
    if (!ready.value) return
    return board.resource.submit({ section: section.value, from_date: range.value.from, to_date: range.value.to, company: company.value, refresh: refresh ? 1 : 0 })
  }

  watch([section, () => range.value.from, () => range.value.to, company, ready], () => load(), { immediate: true })

  watch(preset, (v) => {
    if (v === 'custom' && !custom.from) Object.assign(custom, range.value)
    try {
      localStorage.setItem(PRESET_KEY, v)
    } catch {
      // remembering the range is a convenience only
    }
  })

  return { meta, sections, companies, section, preset, custom, company, range, board, data, load }
}
