<template>
  <div class="mx-auto flex max-w-6xl flex-col gap-5 px-3 py-5 md:px-6">
    <template v-if="loading && !data">
      <AppSkeleton variant="block" height="9rem" />
      <div class="grid grid-cols-2 gap-4 lg:grid-cols-4"><AppSkeleton v-for="n in 4" :key="n" variant="block" height="6rem" /></div>
      <AppSkeleton variant="block" height="16rem" />
    </template>

    <StateBanner v-else-if="error" icon="triangle-alert" title="Your portal isn't available" :description="error" />

    <template v-else-if="data">
      <!-- welcome -->
      <div class="relative overflow-hidden rounded-2xl border border-app-border bg-app-panel p-4 md:p-5" :style="{ backgroundImage: 'radial-gradient(60rem 18rem at 100% -20%, var(--app-primary-tint), transparent)' }">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="text-p-sm text-app-text-muted">{{ today }}</p>
            <h2 class="mt-0.5 text-xl font-bold tracking-tight text-app-text md:text-2xl">Welcome back, {{ firstName }}</h2>
            <p class="mt-1 max-w-xl text-p-sm text-app-text-muted">
              Here's where things stand for <strong class="font-semibold text-app-text">{{ data.customer_title }}</strong>. Follow your services and prepare for interviews.
            </p>
          </div>
          <AppButton v-if="data.chat_enabled" icon="message-square" class="shrink-0" @click="router.push('/portal/messages')">Message your team</AppButton>
        </div>
      </div>

      <!-- key numbers -->
      <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <button v-for="k in kpis" :key="k.label" type="button" class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-4 text-left transition-colors hover:border-app-primary/50" @click="router.push(k.to)">
          <span class="flex size-9 items-center justify-center rounded-lg" :class="k.tone"><span :class="[k.icon, 'size-5']" /></span>
          <span>
            <span class="block text-2xl font-bold leading-none text-app-text">{{ k.value }}</span>
            <span class="mt-1 block text-p-sm text-app-text-muted">{{ k.label }}</span>
          </span>
        </button>
      </div>

      <div class="grid gap-4 lg:grid-cols-3">
        <!-- service progress -->
        <SectionCard title="Service progress" subtitle="Where each of your services stands" class="lg:col-span-2">
          <div v-if="!services.length" class="py-6 text-center text-p-sm text-app-text-muted">Your services will appear here once your team starts working on them.</div>
          <div v-else class="flex flex-col gap-6 sm:flex-row sm:items-center">
            <div class="relative mx-auto size-40 shrink-0">
              <svg viewBox="0 0 100 100" class="size-full -rotate-90">
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--app-panel-2)" stroke-width="10" />
                <circle cx="50" cy="50" r="42" fill="none" stroke="#16a34a" stroke-width="10" stroke-linecap="round" :stroke-dasharray="`${(pct * 263.9) / 100} 263.9`" class="transition-all duration-700" />
              </svg>
              <div class="absolute inset-0 flex flex-col items-center justify-center">
                <span class="text-3xl font-bold text-app-text">{{ pct }}%</span>
                <span class="text-2xs uppercase tracking-wide text-app-text-muted">complete</span>
              </div>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex h-2.5 overflow-hidden rounded-full bg-app-panel-2">
                <div v-for="seg in segments" :key="seg.key" :style="{ width: seg.width, background: seg.color }" class="transition-all duration-700" />
              </div>
              <ul class="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-p-sm">
                <li v-for="seg in segments" :key="seg.key" class="flex items-center gap-2 text-app-text-muted">
                  <span class="size-2.5 rounded-full" :style="{ background: seg.color }" />{{ seg.label }}
                  <span class="ml-auto font-semibold text-app-text">{{ counts[seg.key] }}</span>
                </li>
              </ul>
            </div>
          </div>
          <ul v-if="services.length" class="mt-5 divide-y divide-app-border border-t border-app-border">
            <li v-for="(s, i) in services.slice(0, 6)" :key="i" class="flex items-center justify-between gap-3 py-2.5">
              <span class="min-w-0"><span class="block truncate text-p-sm font-medium text-app-text">{{ s.title }}</span></span>
              <AppBadge :label="s.rec.status || 'Pending'" :theme="serviceTheme(s.rec.status)" />
            </li>
          </ul>
          <div v-if="services.length > 6" class="pt-2"><AppButton variant="ghost" size="sm" @click="router.push('/portal/services')">See all {{ services.length }} services</AppButton></div>
        </SectionCard>

        <!-- upcoming interviews -->
        <SectionCard title="Upcoming interviews" subtitle="What's next on your calendar">
          <div v-if="!interviewsLoaded" class="py-4"><AppSkeleton :lines="3" /></div>
          <div v-else-if="!upcoming.length" class="py-6 text-center text-p-sm text-app-text-muted">No interviews scheduled right now.</div>
          <ul v-else class="flex flex-col gap-3">
            <li v-for="u in upcoming" :key="u.key" class="flex gap-3">
              <span class="flex w-12 shrink-0 flex-col items-center rounded-lg bg-app-primary-tint py-1 text-app-primary">
                <span class="text-2xs font-semibold uppercase">{{ u.month }}</span><span class="text-lg font-bold leading-tight">{{ u.day }}</span>
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-p-sm font-medium text-app-text">{{ u.company }}</span>
                <span class="block truncate text-2xs text-app-text-muted">{{ u.role }} · {{ u.round }}</span>
                <span class="block text-2xs text-app-text-muted">{{ u.time }}</span>
              </span>
            </li>
          </ul>
          <div v-if="upcoming.length" class="pt-3"><AppButton variant="ghost" size="sm" @click="router.push('/portal/interviews')">All interviews</AppButton></div>
        </SectionCard>

        <!-- messages -->
        <SectionCard v-if="data.chat_enabled" title="Messages" subtitle="Your account manager is one message away">
          <div class="flex items-center gap-4">
            <span class="flex size-12 items-center justify-center rounded-xl bg-app-primary-tint text-app-primary"><span class="lucide-message-square size-6" /></span>
            <span>
              <span class="block text-2xl font-bold leading-none text-app-text">{{ unread }}</span>
              <span class="text-p-sm text-app-text-muted">unread {{ unread === 1 ? 'message' : 'messages' }}</span>
            </span>
          </div>
          <div class="pt-4"><AppButton variant="outline" icon="arrow-right" @click="router.push('/portal/messages')">Open messages</AppButton></div>
        </SectionCard>

        <!-- accounts -->
        <SectionCard title="Invoices" subtitle="What's paid and what's due">
          <div v-if="!accounts" class="py-3"><AppSkeleton :lines="2" /></div>
          <template v-else>
            <div class="flex items-baseline justify-between"><span class="text-p-sm text-app-text-muted">Outstanding</span><span class="text-xl font-bold" :class="accounts.totals.outstanding > 0 ? 'text-amber-600' : 'text-app-text'">{{ money(accounts.totals.outstanding, currency) }}</span></div>
            <div class="mt-2 flex flex-wrap gap-2">
              <AppBadge v-if="accounts.totals.overdue" :label="`${accounts.totals.overdue} overdue`" theme="red" />
              <AppBadge v-if="accounts.totals.pending" :label="`${accounts.totals.pending} pending`" theme="orange" />
              <AppBadge v-if="!accounts.totals.overdue && !accounts.totals.pending" :label="accounts.invoices.length ? 'All paid' : 'No invoices yet'" theme="green" />
            </div>
          </template>
          <div class="pt-3"><AppButton variant="outline" size="sm" @click="router.push('/portal/accounts')">View accounts</AppButton></div>
        </SectionCard>
      </div>

      <!-- documents: lower priority than the day-to-day sections above, so it sits last -->
      <SectionCard
        title="Your documents"
        :subtitle="missingDocs.length ? `${missingDocs.length} still needed. Please upload them so we can keep things moving.` : 'Everything is uploaded. Keep them up to date.'"
        :class="missingDocs.length ? '!border-amber-400/70' : ''"
      >
        <template v-if="data.lead_documents.length">
          <div class="mb-3 flex items-center gap-3">
            <div class="h-2 flex-1 overflow-hidden rounded-full bg-app-panel-2"><div class="h-full rounded-full transition-all duration-700" :class="missingDocs.length ? 'bg-amber-500' : 'bg-green-600'" :style="{ width: docPct + '%' }" /></div>
            <span class="shrink-0 text-p-sm font-semibold text-app-text">{{ uploadedDocs }} of {{ data.lead_documents.length }} uploaded</span>
          </div>
          <PortalDocumentList />
        </template>
        <p v-else class="text-p-sm text-app-text-muted">There are no documents to upload right now.</p>
      </SectionCard>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import PortalDocumentList from '@/components/portal/PortalDocumentList.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { usePortal } from '@/composables/portal/usePortal'
import { money, serviceTheme } from '@/utils/portal/status'
import { siteTimeZone, siteTodayIso, zoneAbbr } from '@/utils/common/siteTime'

const router = useRouter()
const { data, loading, error, services, counts, unread, interviews, interviewsLoaded, loadInterviews, accounts, loadAccounts, docNames } = usePortal()
onMounted(() => {
  loadInterviews()
  loadAccounts()
})
const currency = computed(() => accounts.value?.invoices?.[0]?.currency || accounts.value?.orders?.[0]?.currency)

const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: siteTimeZone() })
const firstName = computed(() => (data.value?.user_name || '').split(' ')[0] || 'there')

const pct = computed(() => (services.value.length ? Math.round((counts.value.completed / services.value.length) * 100) : 0))
const segments = computed(() => {
  const total = services.value.length || 1
  return [
    { key: 'completed', label: 'Completed', color: '#16a34a' },
    { key: 'progress', label: 'In progress', color: '#0057e5' },
    { key: 'pending', label: 'Pending', color: '#f59e0b' },
    { key: 'rework', label: 'Needs update', color: '#dc2626' },
  ].map((s) => ({ ...s, width: `${(counts.value[s.key] / total) * 100}%` }))
})

// rounds still ahead of us, soonest first
const upcoming = computed(() => {
  const now = siteTodayIso()
  const rows = []
  for (const rec of interviews.value) {
    for (const r of rec.interview_rounds_table || []) {
      const d = r.date_of_interview
      if (!d || d < now || /cancel|reject/i.test(r.status || '')) continue
      const date = new Date(`${d}T00:00:00`)
      rows.push({
        key: `${rec.name}-${r.round}-${d}`,
        d,
        company: rec.company || '-',
        role: rec.role || '-',
        round: r.round || '-',
        month: date.toLocaleDateString(undefined, { month: 'short' }),
        day: date.getDate(),
        time: r.from_time && r.to_time ? `${r.from_time} – ${r.to_time} ${zoneAbbr(r.time_zone)}` : '',
      })
    }
  }
  return rows.sort((a, b) => a.d.localeCompare(b.d)).slice(0, 4)
})

const isUploaded = (d) => Boolean(d.file_name || docNames[d.field])
const uploadedDocs = computed(() => (data.value?.lead_documents || []).filter(isUploaded).length)
const missingDocs = computed(() => (data.value?.lead_documents || []).filter((d) => !isUploaded(d)))
const docPct = computed(() => (data.value?.lead_documents?.length ? (uploadedDocs.value / data.value.lead_documents.length) * 100 : 0))

// icon classes written out for Tailwind: lucide-briefcase lucide-circle-check lucide-calendar-days lucide-receipt
const kpis = computed(() => [
  { label: 'Services', value: services.value.length, icon: 'lucide-briefcase', tone: 'bg-app-primary-tint text-app-primary', to: '/portal/services' },
  { label: 'Completed', value: counts.value.completed, icon: 'lucide-circle-check', tone: 'bg-green-500/10 text-green-600', to: '/portal/services' },
  { label: 'Interviews', value: interviews.value.length, icon: 'lucide-calendar-days', tone: 'bg-blue-500/10 text-blue-600', to: '/portal/interviews' },
  { label: 'Outstanding', value: accounts.value ? money(accounts.value.totals.outstanding, currency.value) : '–', icon: 'lucide-receipt', tone: 'bg-amber-500/10 text-amber-600', to: '/portal/accounts' },
])
</script>
