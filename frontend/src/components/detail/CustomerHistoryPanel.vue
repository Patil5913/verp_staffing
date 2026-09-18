<template>
  <div class="flex flex-col gap-4">
    <p v-if="!customer" class="rounded-xl border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      No customer selected.
    </p>
    <div v-else-if="history.isLoading && !history.resource.data" class="flex justify-center py-10">
      <LoadingIndicator class="h-5 w-5 text-app-text-muted" />
    </div>
    <p v-else-if="!groups.length" class="rounded-xl border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      This customer hasn't been forwarded to any department yet.
    </p>

    <SectionCard
      v-for="group in groups"
      :key="group.department"
      :title="group.department"
      :subtitle="`${group.entries.length} ${group.entries.length === 1 ? 'record' : 'records'}`"
    >
      <div class="flex flex-col gap-3">
        <div
          v-for="entry in group.entries"
          :key="entry.id"
          class="flex flex-col gap-2 rounded-lg border border-app-border bg-app-panel-2/40 p-4"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <router-link
              :to="`/${encodeURIComponent(group.department)}/${encodeURIComponent(entry.id)}`"
              class="text-p-sm font-medium text-app-primary hover:underline"
            >
              {{ entry.id }}
            </router-link>
            <DocStatusBadge :status="entry.status" />
          </div>

          <p class="text-p-sm text-app-text-muted">
            <span v-if="entry.service_name">{{ entry.service_name }} · </span>
            <span v-if="entry.interview">{{ entry.interview.company }} · {{ entry.interview.role }} · </span>
            Assigned to {{ entry.assign_to || '—' }}
          </p>

          <dl v-if="entry.interview_round_detail" class="grid grid-cols-2 gap-x-4 gap-y-1 text-p-sm sm:grid-cols-4">
            <div v-for="row in roundRows(entry.interview_round_detail)" :key="row.label">
              <dt class="text-p-xs text-app-text-muted">{{ row.label }}</dt>
              <dd class="text-app-text">{{ row.value || '—' }}</dd>
            </div>
          </dl>

          <div v-if="entry.job_application_count?.length" class="overflow-x-auto">
            <table class="w-full text-left text-p-sm">
              <thead class="text-p-xs text-app-text-muted">
                <tr><th class="py-1 pr-4 font-medium">Date</th><th class="py-1 pr-4 font-medium">Small</th><th class="py-1 pr-4 font-medium">Large</th><th class="py-1 font-medium">Total</th></tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in entry.job_application_count" :key="i" class="border-t border-app-border">
                  <td class="py-1 pr-4">{{ formatDate(row.date) }}</td>
                  <td class="py-1 pr-4">{{ row.small_application ?? 0 }}</td>
                  <td class="py-1 pr-4">{{ row.large_application ?? 0 }}</td>
                  <td class="py-1 font-medium">{{ row.total_application ?? 0 }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="entry.session_details?.length" class="flex flex-col gap-1 text-p-sm">
            <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Sessions</p>
            <p v-for="(s, i) in entry.session_details" :key="i" class="text-app-text">
              {{ formatDate(s.date) }} · {{ s.session_duration_in_hour }}h
              <span v-if="s.feedback_due" class="text-orange-600">· feedback due</span>
            </p>
          </div>

          <div v-if="entry.document_references?.length" class="flex flex-wrap gap-2">
            <a
              v-for="(ref, i) in entry.document_references"
              :key="i"
              :href="ref.document"
              target="_blank"
              rel="noopener"
              class="inline-flex items-center gap-1 rounded-full border border-app-border px-2.5 py-1 text-p-xs text-app-primary hover:border-app-primary/50"
            >
              <span class="lucide-paperclip size-3" />{{ ref.document_title || 'Document' }}
            </a>
          </div>

          <div v-if="entry.feedback_entries?.length" class="flex flex-col gap-1 text-p-sm">
            <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">Customer feedback</p>
            <p v-for="(f, i) in entry.feedback_entries" :key="i" class="text-app-text">
              <span class="text-app-text-muted">{{ formatDate(f.date) }} —</span> {{ f.feedback }}
            </p>
          </div>
        </div>
      </div>
    </SectionCard>

    <div v-if="hasMoreInterviews" class="flex justify-center">
      <AppButton variant="outline" size="sm" :loading="history.isLoading" @click="loadMoreInterviews">Load more interviews</AppButton>
    </div>
  </div>
</template>

<script setup>
// The customer's full trail across departments (Marketing, Resume, RUC,
// Interview Support, ...) — the desk "History" tab, backed by the same
// get_customer_history the customer portal uses.
import { computed, ref, watch } from 'vue'
import { LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { useResource } from '@/composables/list/useResource'
import { formatDate } from '@/utils/list/formatValue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  customer: { type: String, default: '' },
  detail: { type: Object, default: null },
  // When set, shows only this department (doctype) — e.g. Marketing's
  // History tab only cares about its own trail plus interviews.
  departments: { type: Array, default: null },
})

const customer = computed(() => props.customer || props.detail?.values.customer || '')

const PAGE = 5
const interviewLimit = ref(PAGE)

const history = useResource({
  url: 'verp_staffing.www.customer.get_customer_history',
  makeParams: () => ({ customer: customer.value, interview_limit: interviewLimit.value, interview_offset: 0 }),
  notifyOnError: false,
})

watch(
  customer,
  (value) => {
    interviewLimit.value = PAGE
    if (value) history.resource.submit({ customer: value, interview_limit: PAGE, interview_offset: 0 })
  },
  { immediate: true },
)

const groups = computed(() => {
  const departments = history.resource.data?.departments || {}
  return Object.entries(departments)
    .filter(([name, entries]) => entries?.length && (!props.departments || props.departments.includes(name)))
    .map(([department, entries]) => ({ department, entries }))
})

const hasMoreInterviews = computed(() => {
  const list = history.resource.data?.departments?.Interview || []
  return list.length >= interviewLimit.value
})

function loadMoreInterviews() {
  interviewLimit.value += PAGE
  history.resource.submit({ customer: customer.value, interview_limit: interviewLimit.value, interview_offset: 0 })
}

function roundRows(r) {
  return [
    { label: 'Round', value: r.round },
    { label: 'Type', value: r.type_of_interview },
    { label: 'Interview date', value: formatDate(r.date_of_interview) },
    { label: 'Time', value: r.from_time && r.to_time ? `${r.from_time} – ${r.to_time}` : '' },
  ]
}
</script>
