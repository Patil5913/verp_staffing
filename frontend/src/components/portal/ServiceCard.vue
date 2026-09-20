<template>
  <SectionCard :title="service.title">
    <div class="flex flex-wrap items-center gap-2">
      <AppBadge :label="service.rec.status || 'Pending'" :theme="serviceTheme(service.rec.status)" size="md" />
    </div>

    <!-- the interview round a JDC / Interview Support record belongs to -->
    <div v-if="linked.has(service.dept) && service.rec.interview_round_detail" class="mt-4 rounded-lg border border-app-border bg-app-panel-2 p-3">
      <p class="mb-2 text-2xs font-semibold uppercase tracking-wide text-app-text-muted">Interview round</p>
      <dl class="grid grid-cols-2 gap-x-6 gap-y-2 text-p-sm sm:grid-cols-3">
        <div v-for="[label, value] in roundFacts" :key="label"><dt class="text-2xs text-app-text-muted">{{ label }}</dt><dd class="font-medium text-app-text">{{ value || '-' }}</dd></div>
        <div><dt class="text-2xs text-app-text-muted">Status</dt><dd><AppBadge :label="service.rec.interview_round_detail.status || '-'" :theme="interviewTheme(service.rec.interview_round_detail.status)" /></dd></div>
      </dl>
    </div>

    <div v-if="service.rec.session_details?.length" class="mt-4">
      <p class="mb-2 text-2xs font-semibold uppercase tracking-wide text-app-text-muted">Sessions</p>
      <div class="overflow-x-auto rounded-lg border border-app-border">
        <table class="w-full text-p-sm">
          <thead class="bg-app-panel-2 text-left text-2xs uppercase text-app-text-muted"><tr><th class="px-3 py-2">#</th><th class="px-3 py-2">Duration</th><th class="px-3 py-2">Date</th><th class="px-3 py-2">Projects</th><th class="px-3 py-2">Quality</th></tr></thead>
          <tbody>
            <tr v-for="(x, n) in service.rec.session_details" :key="n" class="border-t border-app-border"><td class="px-3 py-2">{{ n + 1 }}</td><td class="px-3 py-2">{{ x.session_duration_in_hour || '-' }}</td><td class="px-3 py-2">{{ x.date || '-' }}</td><td class="px-3 py-2">{{ x.projects || '-' }}</td><td class="px-3 py-2">{{ x.quality || '-' }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="service.rec.job_application_count?.length" class="mt-4">
      <p class="mb-2 text-2xs font-semibold uppercase tracking-wide text-app-text-muted">Job applications</p>
      <div class="overflow-x-auto rounded-lg border border-app-border">
        <table class="w-full text-p-sm">
          <thead class="bg-app-panel-2 text-left text-2xs uppercase text-app-text-muted"><tr><th class="px-3 py-2">#</th><th class="px-3 py-2">Small</th><th class="px-3 py-2">Large</th><th class="px-3 py-2">Total</th><th class="px-3 py-2">Date</th></tr></thead>
          <tbody>
            <tr v-for="(m, n) in service.rec.job_application_count" :key="n" class="border-t border-app-border"><td class="px-3 py-2">{{ n + 1 }}</td><td class="px-3 py-2">{{ m.small_application || '-' }}</td><td class="px-3 py-2">{{ m.large_application || '-' }}</td><td class="px-3 py-2">{{ m.total_application || '-' }}</td><td class="px-3 py-2">{{ m.date || '-' }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="downloadable.has(service.dept)" class="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-app-border bg-app-panel-2 p-3">
      <template v-if="service.rec.latest_document_reference">
        <span class="min-w-0"><span class="block truncate text-p-sm font-medium text-app-text">{{ service.rec.latest_document_reference.document_title || 'Document' }}</span><span v-if="service.rec.latest_document_reference.date" class="text-2xs text-app-text-muted">{{ service.rec.latest_document_reference.date }}</span></span>
        <AppButton icon="download" size="sm" @click="download">Download</AppButton>
      </template>
      <span v-else class="text-p-sm text-app-text-muted">No document available yet.</span>
    </div>

    <div v-if="service.rec.forward_events_display?.length" class="mt-4">
      <p class="mb-2 text-2xs font-semibold uppercase tracking-wide text-app-text-muted">Progress</p>
      <ol class="flex flex-col gap-1.5 border-l border-app-border pl-4 text-p-sm">
        <li v-for="(f, n) in service.rec.forward_events_display" :key="n" class="text-app-text">Moved to <strong class="font-medium">{{ f.department }}</strong> <span class="text-app-text-muted">· {{ f.when }}</span></li>
      </ol>
    </div>
  </SectionCard>
</template>

<script setup>
import { computed } from 'vue'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppButton from '@/components/ui/AppButton.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { usePortal } from '@/composables/portal/usePortal'
import { interviewTheme, serviceTheme } from '@/utils/portal/status'

const props = defineProps({ service: { type: Object, required: true } })
const { data } = usePortal()

const linked = computed(() => new Set(data.value?.interview_linked_doctypes || []))
const downloadable = computed(() => new Set(data.value?.download_allowed_doctypes || []))

const roundFacts = computed(() => {
  const rec = props.service.rec
  const r = rec.interview_round_detail
  return [
    ['Company', rec.interview?.company],
    ['Role', rec.interview?.role],
    ['Round', r.round],
    ['Type', r.type_of_interview],
    ['Interview date', r.date_of_interview],
    ['Time', r.from_time && r.to_time ? `${r.from_time} – ${r.to_time}` : ''],
  ]
})

// a plain navigation: the server streams the file and checks it is this customer's
const download = () => {
  window.location.href = `/verp/portal/services/${encodeURIComponent(props.service.dept)}/${encodeURIComponent(props.service.rec.docname)}/download`
}
</script>
