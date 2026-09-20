<template>
  <div class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <h3 class="mb-2 text-p-base font-medium text-app-text">Resume</h3>
    <p v-if="!customer" class="text-p-sm text-app-text-muted">No customer selected.</p>
    <div v-else-if="resume.isLoading && !resume.resource.data" class="text-p-sm text-app-text-muted">Loading…</div>
    <a
      v-else-if="resume.resource.data?.document"
      :href="resume.resource.data.document"
      target="_blank"
      rel="noopener"
      class="inline-flex items-center gap-1.5 text-p-sm font-medium text-app-primary hover:underline"
    >
      <span class="lucide-file-text size-4" />
      View Resume
    </a>
    <p v-else class="text-p-sm text-app-text-muted">No resume on file for this customer yet.</p>
  </div>
</template>

<script setup>
// The latest resume document on file for a customer — shared across every
// service record page (Training, Interview Support, Technical Other
// Services, ...) since they all surface the same "resume" panel in the
// desk form (see fetch_and_render_resume in public/js/reusable.js).
import { computed, watch } from 'vue'
import { useResource } from '@/composables/list/useResource'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  customer: { type: String, default: '' },
  // ConfigDetailPage hands section components the whole `detail` instead.
  detail: { type: Object, default: null },
})
const customer = computed(() => props.customer || props.detail?.values.customer || '')

const resume = useResource({
  url: 'verp_staffing.technical.doctype.resume.resume.get_latest_resume_document',
  makeParams: () => ({ customer: customer.value }),
  notifyOnError: false,
})

watch(
  customer,
  (customer) => {
    if (customer) resume.resource.submit({ customer })
  },
  { immediate: true },
)
</script>
