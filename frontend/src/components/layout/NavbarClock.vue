<template>
  <div
    class="flex shrink-0 items-center gap-1.5 rounded-md border border-app-border bg-app-bg px-2.5 py-1.5 text-p-sm tabular-nums text-app-text"
    :title="`${zone}\n${dateText}`"
  >
    <span class="lucide-clock size-4 shrink-0 text-app-text-muted" />
    <span class="font-medium">{{ time }}</span>
    <span class="text-p-xs font-medium text-app-text-muted">{{ code }}</span>
  </div>
</template>

<script setup>
// The user's clock: the time in their own Time Zone (User > General) with the zone's short code -
// "09:41:07 PM IST". That zone starts as the company's (System Settings, edited under ERP
// Configuration > Website Settings), so until someone picks another everyone sees company time.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { displayTimeZone, siteTimeZone } from '@/utils/common/siteTime'

const zone = computed(() => displayTimeZone() || siteTimeZone())
const code = displayTimeZone() ? window.display_time_zone_label || '' : window.site_time_zone_label || ''
const now = ref(new Date())
let timer

const format = (options) => {
  try {
    return new Intl.DateTimeFormat(undefined, { timeZone: zone.value, ...options }).format(now.value)
  } catch {
    return new Intl.DateTimeFormat(undefined, options).format(now.value)
  }
}
const time = computed(() => format({ hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }))
const dateText = computed(() => format({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }))

onMounted(() => {
  timer = setInterval(() => (now.value = new Date()), 1000)
})
onUnmounted(() => clearInterval(timer))
</script>
