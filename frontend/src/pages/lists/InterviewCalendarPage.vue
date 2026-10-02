<template>
  <div class="flex h-full min-w-0 max-w-full flex-col overflow-hidden bg-app-bg">
    <SubNavbar :title="doctype">
      <template #left>
        <ViewSwitcher :doctype="doctype" current="calendar" />
        <Dropdown :options="modeOptions" placement="left">
          <template #default="{ open }">
            <button
              type="button"
              class="inline-flex h-7 shrink-0 items-center gap-2 rounded-lg border border-app-border bg-app-panel px-2.5 text-p-sm font-medium text-app-text transition-colors hover:bg-app-panel-2"
              :class="open ? 'bg-app-panel-2' : ''"
              title="Switch layout"
            >
              <span :class="`lucide-${currentMode.icon} size-3.5 shrink-0 text-app-text-muted`" />
              <span>{{ currentMode.label }}</span>
              <span class="lucide-chevron-down size-3.5 shrink-0 text-app-text-muted" />
            </button>
          </template>
        </Dropdown>
      </template>
      <template #right>
        <AppButton variant="outline" size="sm" icon="users" tooltip="Select Customer" :label="wide ? 'Select Customer' : ''" @click="showCustomerDialog = true" />
        <AppButton variant="ghost" icon="chevron-left" tooltip="Previous month" @click="shift(-1)" />
        <span class="min-w-[4.5rem] whitespace-nowrap text-center text-p-sm font-medium text-app-text">{{ monthLabel }}</span>
        <AppButton variant="ghost" icon="chevron-right" tooltip="Next month" @click="shift(1)" />
        <AppButton variant="ghost" size="sm" label="Today" @click="goToday" />
        <AppButton variant="ghost" icon="refresh-cw" tooltip="Refresh" :loading="events.isLoading" @click="load" />
      </template>
    </SubNavbar>

    <div class="min-h-0 min-w-0 flex-1 overflow-auto px-2 py-2">
      <StateBanner v-if="events.hasError" icon="alert-triangle" title="Couldn't load the schedule" :description="events.errorMessage" />
      <div v-else-if="events.isLoading && !events.resource.data" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

      <!-- Month: every round on the day it happens -->
      <div v-else-if="mode === 'month'" class="min-w-[48rem] overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-sm">
        <div class="grid grid-cols-7 border-b border-app-border bg-app-panel-2 text-p-xs font-medium uppercase tracking-wide text-app-text-muted">
          <div v-for="d in WEEKDAYS" :key="d" class="px-2 py-1.5">{{ d }}</div>
        </div>
        <div v-for="(week, wi) in weeks" :key="wi" class="grid grid-cols-7 border-b border-app-border last:border-b-0">
          <div
            v-for="day in week"
            :key="day.iso"
            class="min-h-[8rem] border-r border-app-border p-1.5 last:border-r-0"
            :class="day.inMonth ? '' : 'bg-app-panel-2/50'"
          >
            <p
              class="mb-1 inline-flex size-6 items-center justify-center rounded-full text-p-xs"
              :class="day.iso === todayIso ? 'bg-app-primary font-semibold text-white' : day.inMonth ? 'text-app-text' : 'text-app-text-muted'"
            >{{ day.n }}</p>
            <button
              v-for="ev in shown(day)"
              :key="ev.key"
              type="button"
              class="mb-1 block w-full truncate rounded-md border-l-2 px-1.5 py-0.5 text-left text-p-xs transition-opacity hover:opacity-80"
              :class="tone(ev.status).chip"
              :title="`${ev.subject}\n${timeText(ev)}${ev.customer ? '\n' + ev.customer : ''}`"
              @click="open(ev)"
            >
              <span class="font-medium">{{ ev.allDay ? '' : hhmm(ev.from_time) + ' ' }}</span>{{ ev.company }} · R{{ roundNo(ev) }}
            </button>
            <button
              v-if="(byDay[day.iso] || []).length > LIMIT"
              type="button"
              class="text-p-xs font-medium text-app-primary hover:underline"
              @click="expanded = expanded === day.iso ? '' : day.iso"
            >{{ expanded === day.iso ? 'Show less' : `+${byDay[day.iso].length - LIMIT} more` }}</button>
          </div>
        </div>
      </div>

      <!-- Timeline: each interview as a row, its rounds as bars across the month. This box is the
           one scroller (both ways), so the date header and the Interview column stay put while
           scrolling down through the rows or across the days. -->
      <div v-else ref="timelineEl" class="max-h-full overflow-auto rounded-xl border border-app-border bg-app-panel shadow-sm">
        <div class="min-w-max">
          <div class="sticky top-0 z-20 flex border-b border-app-border bg-app-panel-2 shadow-sm">
            <div class="sticky left-0 z-30 flex w-40 xl:w-48 shrink-0 items-end border-r border-app-border bg-app-panel-2 px-3 py-2 text-p-xs font-medium uppercase tracking-wide text-app-text-muted">Interview · {{ monthLabel }}</div>
            <div
              v-for="day in monthDays"
              :key="day.iso"
              class="shrink-0 border-r border-app-border py-1 text-center"
              :style="{ width: `${CELL}px` }"
              :class="day.iso === todayIso ? 'bg-app-primary-tint text-app-primary' : day.weekend ? 'bg-app-panel-2 text-app-text-muted/70' : 'text-app-text-muted'"
            >
              <p class="text-2xs uppercase leading-4">{{ CELL < 40 ? day.weekday.slice(0, 1) : day.weekday }}</p>
              <p class="text-p-sm leading-5" :class="day.iso === todayIso ? 'font-semibold' : 'font-medium'">{{ day.n }}</p>
            </div>
          </div>
          <p v-if="!timelineRows.length" class="sticky left-0 px-4 py-10 text-center text-p-sm text-app-text-muted">No interviews scheduled this month.</p>
          <div v-for="row in timelineRows" :key="row.interview" class="group flex border-b border-app-border last:border-b-0">
            <button type="button" class="sticky left-0 z-10 w-40 xl:w-48 shrink-0 truncate border-r border-app-border bg-app-panel px-3 py-2 text-left text-p-sm text-app-text group-hover:bg-app-panel-2 hover:text-app-primary" :title="row.label" @click="router.push(`/Interview/${encodeURIComponent(row.interview)}`)">
              {{ row.label }}
              <span v-if="row.customer" class="block truncate text-p-xs text-app-text-muted">{{ row.customer }}</span>
            </button>
            <div class="relative flex group-hover:bg-app-panel-2/40">
              <div
                v-for="day in monthDays"
                :key="day.iso"
                class="h-14 shrink-0 border-r border-app-border"
                :style="{ width: `${CELL}px` }"
                :class="day.iso === todayIso ? 'bg-app-primary-tint/60' : day.weekend ? 'bg-app-panel-2/60' : ''"
              />
              <!-- Each round: a horizontal bar across its day's column (several rounds on one day
                   share the row's height), the time shown inside and in the tooltip -->
              <button
                v-for="ev in row.rounds"
                :key="ev.key"
                type="button"
                class="absolute z-[4] flex cursor-pointer items-center overflow-hidden rounded-sm px-1.5 text-left text-white text-p-xs font-semibold leading-4 transition-opacity hover:opacity-80"
                :class="tone(ev.status).line"
                :style="barStyle(ev)"
                :title="`R${roundNo(ev)} · ${ev.subject}\n${timeText(ev)}`"
                @click="open(ev)"
              >
                <span class="truncate">R{{ roundNo(ev) }}<template v-if="showLabels && !ev.allDay"> · {{ hhmm(ev.from_time) }}</template></span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="events.resource.data?.length === 0 && !events.isLoading" class="mt-4 text-center text-p-sm text-app-text-muted">No interview rounds scheduled in {{ monthLabel }}.</div>
    </div>

    <SelectCustomerDialog v-model="showCustomerDialog" @applied="load" />
  </div>
</template>

<script setup>
import { siteTodayDate, siteTodayIso } from '@/utils/common/siteTime'
import AppButton from '@/components/ui/AppButton.vue'
// Calendar and timeline views of the Interview rounds - the desk's
// interview_calendar.js / interview_list.js Gantt on top of the same server
// methods (get_interview_round_events), which already scope rows to what the
// user may see. A round is one event; clicking it opens its Interview.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dropdown, LoadingIndicator } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import ViewSwitcher from '@/components/common/ViewSwitcher.vue'
import SelectCustomerDialog from '@/components/list/SelectCustomerDialog.vue'
import { useResource } from '@/composables/list/useResource'
import { useMarketingCustomerFilter } from '@/composables/list/useMarketingCustomerFilter'

const router = useRouter()
// Room for full button labels in the bar; on smaller screens they collapse to icons.
const wideQuery = window.matchMedia('(min-width: 1536px)')
const wide = ref(wideQuery.matches)
const onWide = (e) => (wide.value = e.matches)
wideQuery.addEventListener('change', onWide)
onBeforeUnmount(() => wideQuery.removeEventListener('change', onWide))
const showCustomerDialog = ref(false)
const { selectedCustomers, ensureDefaultCustomers } = useMarketingCustomerFilter()
const doctype = 'Interview'
const MODES = [
  { key: 'month', label: 'Month', icon: 'calendar' },
  { key: 'timeline', label: 'Timeline', icon: 'chart-gantt' },
]
const currentMode = computed(() => MODES.find((m) => m.key === mode.value))
const modeOptions = computed(() => MODES.map((m) => ({ label: m.label, icon: m.key === mode.value ? 'check' : undefined, onClick: () => (mode.value = m.key) })))
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const LIMIT = 3
// px of the Interview column: w-48 from the xl breakpoint up, w-40 below (keep in step with the classes)
const labelCol = () => (window.innerWidth >= 1280 ? 192 : 160)
// The timeline fits the screen: a day's column is as wide as the room allows (a day is 24h wide, so a
// round's line sits at its time), never narrower than MIN_CELL - only then does the box scroll.
const MIN_CELL = 18
const MAX_CELL = 72
const timelineEl = ref(null)
const timelineWidth = ref(0)
let resizeObserver
watch(timelineEl, (el) => {
  resizeObserver?.disconnect()
  if (!el) return
  timelineWidth.value = el.clientWidth
  resizeObserver = new ResizeObserver(() => (timelineWidth.value = el.clientWidth))
  resizeObserver.observe(el)
})
onBeforeUnmount(() => resizeObserver?.disconnect())
const CELL = computed(() => {
  const fit = Math.floor((timelineWidth.value - labelCol() - 2) / monthDays.value.length)
  return Math.max(MIN_CELL, Math.min(MAX_CELL, fit || MAX_CELL))
})
const showLabels = computed(() => CELL.value >= 56)
const roundNo = (ev) => String(ev.round ?? '').replace(/\D/g, '') || ev.round

const mode = ref('month')
const monthStartOfSiteToday = () => {
  const t = siteTodayDate()
  return new Date(t.getFullYear(), t.getMonth(), 1)
}
const anchor = ref(monthStartOfSiteToday())
const expanded = ref('')

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const todayIso = siteTodayIso()
const monthLabel = computed(() => anchor.value.toLocaleDateString(undefined, { month: 'short', year: 'numeric' }))

const monthDays = computed(() => {
  const y = anchor.value.getFullYear()
  const m = anchor.value.getMonth()
  const count = new Date(y, m + 1, 0).getDate()
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(y, m, i + 1)
    return { n: i + 1, iso: iso(d), inMonth: true, weekday: d.toLocaleDateString(undefined, { weekday: 'short' }), weekend: [0, 6].includes(d.getDay()) }
  })
})

// Monday-first grid covering the month, padded with the neighbouring days.
const weeks = computed(() => {
  const y = anchor.value.getFullYear()
  const m = anchor.value.getMonth()
  const lead = (new Date(y, m, 1).getDay() + 6) % 7
  const total = Math.ceil((lead + new Date(y, m + 1, 0).getDate()) / 7) * 7
  const days = Array.from({ length: total }, (_, i) => {
    const d = new Date(y, m, 1 - lead + i)
    return { n: d.getDate(), iso: iso(d), inMonth: d.getMonth() === m }
  })
  return Array.from({ length: total / 7 }, (_, w) => days.slice(w * 7, w * 7 + 7))
})

const events = useResource({
  url: 'verp_staffing.marketing.doctype.interview.interview.get_interview_round_events',
  makeParams: () => ({
    start: weeks.value[0][0].iso,
    end: weeks.value.at(-1).at(-1).iso,
    marketing_link: selectedCustomers.value.length ? selectedCustomers.value : undefined,
  }),
  notifyOnError: false,
})
async function load() {
  await ensureDefaultCustomers()
  events.resource.submit()
}
load()
watch(anchor, load)

const list = computed(() =>
  (events.resource.data || []).map((e, i) => ({ ...e, key: `${e.name}-${e.round}-${i}`, day: String(e.start).slice(0, 10) })),
)
const byDay = computed(() => {
  const map = {}
  for (const e of list.value) (map[e.day] ||= []).push(e)
  return map
})
const shown = (day) => {
  const all = byDay.value[day.iso] || []
  return expanded.value === day.iso ? all : all.slice(0, LIMIT)
}

const timelineRows = computed(() => {
  const rows = new Map()
  for (const e of list.value) {
    if (!e.day.startsWith(iso(anchor.value).slice(0, 7))) continue
    if (!rows.has(e.name)) rows.set(e.name, { interview: e.name, label: `${e.company} - ${e.role}`, customer: e.customer, rounds: [] })
    rows.get(e.name).rounds.push({ ...e, dayIndex: Number(e.day.slice(8, 10)) - 1 })
  }
  // Rounds on the same day stack, earliest on top.
  for (const row of rows.values()) {
    const perDay = {}
    row.rounds.sort((a, b) => String(a.from_time).localeCompare(String(b.from_time), undefined, { numeric: true }))
    for (const r of row.rounds) (perDay[r.dayIndex] ||= []).push(r)
    for (const group of Object.values(perDay)) group.forEach((r, i) => ((r.slot = i), (r.slots = group.length)))
  }
  return [...rows.values()]
})

// Status colour: green done, red/amber called off, blue upcoming, grey otherwise.
function tone(status) {
  const s = String(status || '').toLowerCase()
  if (/complete|offer|select/.test(s)) return { chip: 'border-green-600 bg-green-500/10 text-green-700', line: 'bg-green-600' }
  if (/cancel|reject/.test(s)) return { chip: 'border-red-600 bg-red-500/10 text-red-700', line: 'bg-red-600' }
  if (/resched|hold|pending/.test(s)) return { chip: 'border-amber-600 bg-amber-500/10 text-amber-700', line: 'bg-amber-600' }
  return { chip: 'border-blue-600 bg-blue-500/10 text-blue-700', line: 'bg-blue-600' }
}

// Timeline x-position of a time on a given day: the day's column, plus how far into the 24h it is.
const dayFraction = (t) => {
  const [h = 0, m = 0] = String(t ?? '').split(':').map(Number)
  return (h * 60 + m) / 1440
}
const ROW_H = 56 // px, the h-14 of a timeline row
const BAR_H = 22 // px, a slim bar the width of the day
const barStyle = (ev) => {
  const group = ev.slots * BAR_H + (ev.slots - 1) * 3
  return { left: `${ev.dayIndex * CELL.value}px`, width: `${CELL.value}px`, top: `${(ROW_H - group) / 2 + ev.slot * (BAR_H + 3)}px`, height: `${BAR_H}px` }
}
// The server sends times as "9:00:00"; show "09:00".
const hhmm = (t) => {
  const [h = '', m = ''] = String(t ?? '').split(':')
  return h ? `${h.padStart(2, '0')}:${m.padStart(2, '0')}` : ''
}
// The server has already moved each round from the Eastern time it was typed in to this user's zone.
const timeText = (e) => (e.allDay ? 'All day' : `${hhmm(e.from_time)} – ${hhmm(e.to_time)} ${e.tz_label || e.edt_est || ''}`.trim() + (e.tz_label && e.entered && e.tz_label !== e.edt_est ? ` (entered ${e.entered})` : ''))

const open = (e) => router.push(`/Interview/${encodeURIComponent(e.name)}`)
const shift = (n) => (anchor.value = new Date(anchor.value.getFullYear(), anchor.value.getMonth() + n, 1))
const goToday = () => (anchor.value = monthStartOfSiteToday())
</script>
