<template>
  <template v-if="!detail.isNew.value">
    <AppButton v-if="canSend" variant="outline" icon="send" :loading="working === 'send'" :disabled="!!working" @click="run('send')">Send now</AppButton>
    <AppButton v-if="canRetry" variant="outline" icon="rotate-cw" :loading="working === 'retry'" :disabled="!!working" @click="run('retry')">Retry sending</AppButton>
  </template>
</template>

<script setup>
// Push one queued email along, the way the desk form's buttons do: Send now
// (anything not yet sent) and Retry sending (put a failed / expired one back in
// the queue for the scheduler).
import { computed, ref } from 'vue'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const props = defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, default: '' },
  name: { type: String, required: true },
  locked: { type: Boolean, default: false },
  save: { type: Function, default: null },
})

const status = computed(() => props.detail.values.status)
const canSend = computed(() => ['Not Sent', 'Partially Sent', 'Error', 'Expired'].includes(status.value))
const canRetry = computed(() => ['Error', 'Expired'].includes(status.value))
const working = ref('')

const METHODS = { send: 'send_now_bulk', retry: 'retry_bulk' }
async function run(kind) {
  working.value = kind
  try {
    const res = await call(`verp_staffing.utils.email_queue.${METHODS[kind]}`, { names: props.name })
    if (res.failed?.length) notify.error(res.message)
    else notify.success(res.message)
    props.detail.refresh()
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    working.value = ''
  }
}
</script>
