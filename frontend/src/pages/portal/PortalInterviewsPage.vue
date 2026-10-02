<template>
  <div class="mx-auto flex max-w-5xl flex-col gap-4 px-3 py-5 md:px-6">
    <div class="flex flex-wrap items-center gap-2">
      <AppSearchInput v-model="query" placeholder="Search company, role or status" class="min-w-[14rem] flex-1" />
      <AppDatePicker v-model="from" placeholder="From" compact class="w-40" />
      <AppDatePicker v-model="to" placeholder="To" compact class="w-40" />
      <AppButton v-if="query || from || to" variant="ghost" @click="clear">Clear</AppButton>
    </div>

    <AppSkeleton v-if="!interviewsLoaded" variant="block" height="10rem" />
    <StateBanner v-else-if="!rows.length" icon="calendar-days" title="No interviews found" :description="interviews.length ? 'Try a different search or date range.' : 'Your interviews will appear here once they are scheduled.'" />

    <SectionCard v-for="rec in rows" v-else :key="rec.name" :title="rec.company || '-'" :subtitle="rec.role || ''">
      <div class="mb-3"><AppBadge :label="rec.status || '-'" :theme="interviewTheme(rec.status)" size="md" /></div>
      <div class="overflow-x-auto rounded-lg border border-app-border">
        <table class="w-full text-p-sm">
          <thead class="bg-app-panel-2 text-left text-2xs uppercase text-app-text-muted">
            <tr><th class="px-3 py-2">Round</th><th class="px-3 py-2">Type</th><th class="px-3 py-2">Added</th><th class="px-3 py-2">Interview date</th><th class="px-3 py-2">Time</th><th class="px-3 py-2">Status</th><th class="px-3 py-2">Feedback</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r, n) in rec.interview_rounds_table || []" :key="n" class="border-t border-app-border">
              <td class="px-3 py-2">{{ r.round || '-' }}<AppBadge v-if="r.support" label="Support" theme="blue" class="ml-1.5" /></td>
              <td class="px-3 py-2">{{ r.type_of_interview || '-' }}</td>
              <td class="px-3 py-2">{{ r.date || '-' }}</td>
              <td class="px-3 py-2">{{ r.date_of_interview || '-' }}</td>
              <td class="whitespace-nowrap px-3 py-2">{{ r.from_time && r.to_time ? `${r.from_time} – ${r.to_time} ${zoneAbbr(r.time_zone)}` : '-' }}</td>
              <td class="px-3 py-2"><AppBadge :label="r.status || '-'" :theme="interviewTheme(r.status)" /></td>
              <td class="max-w-[16rem] px-3 py-2">
                <template v-if="(r.feedback || '').trim()">
                  <span class="line-clamp-2">{{ r.feedback.trim() }}</span>
                  <button v-if="r.feedback.trim().length > 60" type="button" class="text-p-xs font-medium text-app-primary hover:underline" @click="full = r.feedback.trim()">View</button>
                </template>
                <span v-else class="text-app-text-muted">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>

    <Dialog v-model="showFull" :options="{ title: 'Full feedback', size: 'lg' }">
      <template #body-content><p class="whitespace-pre-wrap break-words text-p-base leading-relaxed text-app-text">{{ full }}</p></template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Dialog } from 'frappe-ui'
import { zoneAbbr } from '@/utils/common/siteTime'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppDatePicker from '@/components/ui/AppDatePicker.vue'
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { usePortal } from '@/composables/portal/usePortal'
import { interviewTheme } from '@/utils/portal/status'

const { interviews, interviewsLoaded, loadInterviews, load } = usePortal()
onMounted(() => {
  load()
  loadInterviews()
})

const query = ref('')
const from = ref('')
const to = ref('')
const full = ref('')
const showFull = computed({ get: () => Boolean(full.value), set: (v) => !v && (full.value = '') })

const rows = computed(() => {
  const q = query.value.trim().toLowerCase()
  return interviews.value.filter((rec) => {
    if (q && [rec.company, rec.role, rec.status].join(' ').toLowerCase().indexOf(q) === -1) return false
    if (!from.value && !to.value) return true
    return (rec.interview_rounds_table || []).some((r) => {
      const d = r.date_of_interview || r.date || ''
      return (!from.value || d >= from.value) && (!to.value || d <= to.value)
    })
  })
})

const clear = () => {
  query.value = ''
  from.value = ''
  to.value = ''
}
</script>
