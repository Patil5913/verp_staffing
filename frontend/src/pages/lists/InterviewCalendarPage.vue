<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar :title="doctype">
      <template #left><ViewSwitcher :doctype="doctype" current="calendar" /></template>
      <div class="inline-flex items-center rounded-full border border-app-border bg-app-panel-2 p-0.5">
        <button
          v-for="m in MODES"
          :key="m.key"
          type="button"
          class="inline-flex h-6 items-center gap-1 rounded-full px-2.5 text-p-xs font-medium transition-colors"
          :class="mode === m.key ? 'bg-app-panel text-app-text shadow-sm' : 'text-app-text-muted hover:text-app-text'"
          @click="mode = m.key"
        >
          <span :class="`lucide-${m.icon} size-3`" />{{ m.label }}
        </button>
      </div>
      <template #right>
        <AppButton variant="outline" size="sm" icon="users" @click="showCustomerDialog = true">Select Customer</AppButton>
        <AppButton variant="ghost" icon="chevron-left" tooltip="Previous month" @click="shift(-1)" />
        <span class="min-w-[8.5rem] text-center text-p-sm font-medium text-app-text">{{ monthLabel }}</span>
        <AppButton variant="ghost" icon="chevron-right" tooltip="Next month" @click="shift(1)" />
        <AppButton variant="ghost" label="Today" @click="goToday" />
        <AppButton variant="ghost" icon="refresh-cw" tooltip="Refresh" :loading="events.isLoading" @click="load" />
      </template>
    </SubNavbar>

    <div class="min-h-0 flex-1 overflow-auto px-3 md:px-6 py-3">
      <StateBanner v-if="events.hasError" icon="alert-triangle" title="Couldn't load the schedule" :description="events.errorMessage" />
      <div v-else-if="events.isLoading && !events.resource.data" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

      <!-- Month: every round on the day it happens -->
      <div v-else-if="mode === 'month'" class="min-w-[56rem] overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-sm">
        <div class="grid grid-cols-7 border-b border-app-border bg-app-panel-2 text-p-xs font-medium uppercase tracking-wide text-app-text-muted">
          <div v-for="d in WEEKDAYS" :key="d" class="px-2 py-1.5">{{ d }}</div>
        </div>
        <div v-for="(week, wi) in weeks" :key="wi" class="grid grid-cols-7 border-b border-app-border last:border-b-0">
          <div
            v-for="day in week"
            :key="day.iso"
            class="min-h-[7rem] border-r border-app-border p-1.5 last:border-r-0"
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
              <span class="font-medium">{{ ev.allDay ? '' : hhmm(ev.from_time) + ' ' }}</span>{{ ev.company }} · R{{ ev.round }}
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

      <!-- Timeline: each interview as a row, its rounds as bars across the month -->
      <div v-else class="overflow-x-auto rounded-xl border border-app-border bg-app-panel shadow-sm">
        <div class="min-w-max">
          <div class="sticky top-0 z-10 flex border-b border-app-border bg-app-panel-2">
            <div class="sticky left-0 z-10 w-64 shrink-0 border-r border-app-border bg-app-panel-2 px-3 py-1.5 text-p-xs font-medium uppercase tracking-wide text-app-text-muted">Interview</div>
            <div v-for="day in monthDays" :key="day.iso" class="w-9 shrink-0 border-r border-app-border py-1 text-center text-p-xs" :class="day.iso === todayIso ? 'bg-app-primary-tint font-semibold text-app-primary' : 'text-app-text-muted'">{{ day.n }}</div>
          </div>
          <p v-if="!timelineRows.length" class="px-4 py-10 text-center text-p-sm text-app-text-muted">No interviews scheduled this month.</p>
          <div v-for="row in timelineRows" :key="row.interview" class="flex border-b border-app-border last:border-b-0">
            <button type="button" class="sticky left-0 z-[5] w-64 shrink-0 truncate border-r border-app-border bg-app-panel px-3 py-2 text-left text-p-sm text-app-text hover:text-app-primary" :title="row.label" @click="router.push(`/Interview/${encodeURIComponent(row.interview)}`)">
              {{ row.label }}
              <span v-if="row.customer" class="block truncate text-p-xs text-app-text-muted">{{ row.customer }}</span>
            </button>
            <div class="relative flex">
              <div v-for="day in monthDays" :key="day.iso" class="h-12 w-9 shrink-0 border-r border-app-border" :class="day.iso === todayIso ? 'bg-app-primary-tint/50' : ''" />
              <button
                v-for="ev in row.rounds"
                :key="ev.key"
                type="button"
                class="absolute top-2 h-8 w-8 rounded-md border-l-2 text-center text-p-xs font-semibold leading-8 transition-opacity hover:opacity-80"
                :class="tone(ev.status).chip"
                :style="{ left: `${(ev.dayIndex) * 36 + 2}px` }"
                :title="`${ev.subject}\n${timeText(ev)}`"
                @click="open(ev)"
              >R{{ ev.round }}</button>
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
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { LoadingIndicator } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import ViewSwitcher from '@/components/common/ViewSwitcher.vue'
import SelectCustomerDialog from '@/components/list/SelectCustomerDialog.vue'
import { useResource } from '@/composables/list/useResource'
import { useMarketingCustomerFilter } from '@/composables/list/useMarketingCustomerFilter'

const router = useRouter()
const showCustomerDialog = ref(false)
const { selectedCustomers, ensureDefaultCustomers } = useMarketingCustomerFilter()
const doctype = 'Interview'
const MODES = [
  { key: 'month', label: 'Month', icon: 'calendar' },
  { key: 'timeline', label: 'Timeline', icon: 'chart-gantt' },
]
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const LIMIT = 3

const mode = ref('month')
const monthStartOfSiteToday = () => {
  const t = siteTodayDate()
  return new Date(t.getFullYear(), t.getMonth(), 1)
}
const anchor = ref(monthStartOfSiteToday())
const expanded = ref('')

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const todayIso = siteTodayIso()
const monthLabel = computed(() => anchor.value.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }))

const monthDays = computed(() => {
  const y = anchor.value.getFullYear()
  const m = anchor.value.getMonth()
  const count = new Date(y, m + 1, 0).getDate()
  return Array.from({ length: count }, (_, i) => ({ n: i + 1, iso: iso(new Date(y, m, i + 1)), inMonth: true }))
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
  return [...rows.values()]
})

// Status colour: green done, red/amber called off, blue upcoming, grey otherwise.
function tone(status) {
  const s = String(status || '').toLowerCase()
  if (/complete|offer|select/.test(s)) return { chip: 'border-green-600 bg-green-500/10 text-green-700' }
  if (/cancel|reject/.test(s)) return { chip: 'border-red-600 bg-red-500/10 text-red-700' }
  if (/resched|hold|pending/.test(s)) return { chip: 'border-amber-600 bg-amber-500/10 text-amber-700' }
  return { chip: 'border-blue-600 bg-blue-500/10 text-blue-700' }
}
// The server sends times as "9:00:00"; show "09:00".
const hhmm = (t) => {
  const [h = '', m = ''] = String(t ?? '').split(':')
  return h ? `${h.padStart(2, '0')}:${m.padStart(2, '0')}` : ''
}
const timeText = (e) => (e.allDay ? 'All day' : `${hhmm(e.from_time)} – ${hhmm(e.to_time)}${e.edt_est ? ` ${e.edt_est}` : ''}`)

const open = (e) => router.push(`/Interview/${encodeURIComponent(e.name)}`)
const shift = (n) => (anchor.value = new Date(anchor.value.getFullYear(), anchor.value.getMonth() + n, 1))
const goToday = () => (anchor.value = monthStartOfSiteToday())
</script>
