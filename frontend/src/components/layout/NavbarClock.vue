<template>
  <div
    class="flex shrink-0 items-center gap-1.5 rounded-md border border-app-border bg-app-bg px-2.5 py-1.5 text-p-sm tabular-nums text-app-text"
    :title="tooltip"
  >
    <span class="lucide-clock size-4 shrink-0 text-app-text-muted" />
    <span class="font-medium">{{ time }}</span>
    <span class="text-p-xs font-medium text-app-text-muted">{{ code }}</span>
  </div>
</template>

<script setup>
// The user's clock: the time in their own Time Zone (User > General) with the zone's short code -
// "09:41:07 PM EDT". That zone starts as the company's (System Settings, edited under ERP
// Configuration > Website Settings).
//
// The time and the code come from the SERVER (utils/timezone.py get_clock), which reads the zone and
// works out the wall time itself; this only ticks forward from that reading. So it is right whatever
// zone the browser or the server host is in, and it re-reads every few minutes so a changed Time
// Zone or a daylight-saving switch shows without a reload. Until the first answer (or if it fails) it
// falls back to the boot values and the browser's own zone database.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { call } from 'frappe-ui'
import { displayTimeZone, siteTimeZone } from '@/utils/common/siteTime'

const RESYNC_MS = 5 * 60 * 1000
const reading = ref(null) // { zone, company_zone, label, offset }
const now = ref(Date.now())
let tick
let resync

const fallbackZone = () => displayTimeZone() || siteTimeZone()
const zone = computed(() => reading.value?.zone || fallbackZone())
const code = computed(() => reading.value?.label || (displayTimeZone() ? window.display_time_zone_label : window.site_time_zone_label) || '')

// The server's wall time is read as if it were UTC, so formatting in UTC prints it unchanged.
const shown = computed(() => new Date(now.value + (reading.value?.offset ?? 0)))
const format = (options) => {
  try {
    return new Intl.DateTimeFormat(undefined, { timeZone: reading.value ? 'UTC' : fallbackZone(), ...options }).format(shown.value)
  } catch {
    return new Intl.DateTimeFormat(undefined, options).format(shown.value)
  }
}
const time = computed(() => format({ hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }))
const dateText = computed(() => format({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }))
const tooltip = computed(() => {
  const company = reading.value?.company_zone
  const zones = company && company !== zone.value ? `${zone.value} (company: ${company})` : zone.value
  return `${zones}\n${dateText.value}`
})

async function sync() {
  try {
    const r = await call('verp_staffing.utils.timezone.get_clock')
    if (r?.wall) reading.value = { ...r, offset: Date.parse(`${r.wall}Z`) - Date.now() }
  } catch {
    // keep the last reading, or the fallback
  }
}

onMounted(() => {
  tick = setInterval(() => (now.value = Date.now()), 1000)
  sync()
  resync = setInterval(sync, RESYNC_MS)
})
onUnmounted(() => {
  clearInterval(tick)
  clearInterval(resync)
})
</script>
