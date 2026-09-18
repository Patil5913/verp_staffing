<template>
  <AppButton icon="send" :loading="sending" @click="askOpen = true">Send For Signature</AppButton>

  <Dialog v-model="askOpen" :options="{ title: 'Send for signature?', size: 'md' }">
    <template #body-content>
      <p class="text-p-base text-app-text-muted">
        This emails every recipient a link to sign, and locks the document so its fields can't be edited afterwards.
      </p>
    </template>
    <template #actions>
      <AppButton icon="send" :loading="sending" @click="send">Send to {{ recipients.length }} {{ recipients.length === 1 ? 'recipient' : 'recipients' }}</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// e_sign.js's send_for_signature: checks every field is assigned and labelled,
// saves pending edits, then send_all_signers emails the signing links.
import { computed, ref } from 'vue'
import { call, Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, required: true },
})

const askOpen = ref(false)
const sending = ref(false)

const fields = computed(() => props.detail.values.signature_fields ?? props.detail.hiddenTables.signature_fields ?? [])
const recipients = computed(() => [...new Set(fields.value.map((f) => f.signer_email).filter(Boolean))])

function problem() {
  if (!fields.value.length) return 'Add at least one field first.'
  if (!recipients.value.length) return 'Add at least one recipient field.'
  const unlabeled = fields.value.find((f) => f.field_type !== 'checkbox' && !f.field_label)
  if (unlabeled) return `A ${unlabeled.field_type} field is missing its label.`
  return ''
}

async function send() {
  const issue = problem()
  if (issue) {
    notify.error(issue)
    return
  }
  sending.value = true
  try {
    if (props.detail.isDirty.value && !(await props.detail.submit())) return
    await call('verp_staffing.esign.doctype.e_sign.e_sign.send_all_signers', { agreement: props.name })
    notify.success('Emails sent successfully.')
    askOpen.value = false
    props.detail.refresh()
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    sending.value = false
  }
}
</script>
