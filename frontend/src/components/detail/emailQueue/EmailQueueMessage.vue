<template>
  <SectionCard title="Message" subtitle="What will be - or was - sent.">
    <div v-if="loading" class="flex justify-center py-8"><LoadingIndicator class="h-5 w-5 text-app-text-muted" /></div>
    <p v-else-if="error" class="text-p-sm text-red-600">{{ error }}</p>
    <p v-else-if="data?.redacted" class="text-p-sm text-app-text-muted">This message has gone out, so its content was removed from the queue.</p>
    <div v-else-if="data" class="flex flex-col gap-3">
      <dl class="grid grid-cols-[4rem_1fr] gap-x-3 gap-y-1 text-p-sm">
        <dt class="text-app-text-muted">Subject</dt><dd class="break-words font-medium text-app-text">{{ data.subject || '-' }}</dd>
        <dt class="text-app-text-muted">From</dt><dd class="break-words text-app-text">{{ data.from || '-' }}</dd>
        <dt class="text-app-text-muted">To</dt><dd class="break-words text-app-text">{{ data.to || '-' }}</dd>
        <template v-if="data.cc"><dt class="text-app-text-muted">Cc</dt><dd class="break-words text-app-text">{{ data.cc }}</dd></template>
        <template v-if="data.attachments?.length"><dt class="text-app-text-muted">Files</dt><dd class="break-words text-app-text">{{ data.attachments.join(', ') }}</dd></template>
      </dl>
      <div class="rounded-lg border border-app-border bg-app-panel p-3">
        <MailBody v-if="data.html" :html="data.html" />
        <pre v-else class="whitespace-pre-wrap break-words text-p-sm text-app-text">{{ data.text || '(empty)' }}</pre>
      </div>
    </div>
  </SectionCard>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { call, LoadingIndicator } from 'frappe-ui'
import SectionCard from '@/components/common/SectionCard.vue'
import MailBody from '@/components/mail/MailBody.vue'
import { normalizeError } from '@/utils/common/errors'

const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, default: '' },
  name: { type: String, required: true },
  locked: { type: Boolean, default: false },
})

const loading = ref(true)
const error = ref('')
const data = ref(null)

onMounted(async () => {
  try {
    data.value = await call('verp_staffing.utils.email_queue.get_queue_message', { name: props.name })
  } catch (e) {
    error.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
})
</script>
