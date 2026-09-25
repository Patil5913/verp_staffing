<template>
  <Dialog v-model="open" :options="{ title, size: '3xl' }">
    <template #body-content>
      <div v-if="loading" class="flex h-40 items-center justify-center text-app-text-muted">
        <span class="lucide-loader-circle size-6 animate-spin" />
      </div>
      <p v-else-if="blocked" class="py-6 text-p-sm text-app-text-muted">{{ blocked }}</p>
      <div v-else class="flex flex-col gap-3">
        <div class="grid grid-cols-[3.5rem_1fr] items-center gap-x-3 gap-y-2.5">
          <label class="text-p-sm text-app-text-muted">To</label>
          <p class="truncate text-p-sm text-app-text">{{ draft.to }}</p>

          <label class="text-p-sm text-app-text-muted">Subject</label>
          <AppInput v-model="form.subject" placeholder="Subject" />
        </div>

        <TextEditor
          :content="form.message"
          editor-class="min-h-[160px] max-h-[40vh] overflow-y-auto rounded-lg border border-app-border px-3 py-2 text-p-sm"
          placeholder="Write your message…"
          @change="(html) => (form.message = html)"
        />

        <!-- What the mail adds by itself: the customer never sees this until it is sent -->
        <div class="rounded-lg border border-app-border bg-app-panel-2 px-3 py-2.5 text-p-sm">
          <p class="mb-1.5 flex items-center gap-1.5 font-medium text-app-text">
            <span class="lucide-key-round size-4 text-app-primary" />Sign-in details added to this email
          </p>
          <dl class="grid grid-cols-[5rem_1fr] gap-x-3 gap-y-1 text-app-text-muted">
            <dt>Portal</dt>
            <dd class="truncate text-app-text">{{ draft.login_url }}</dd>
            <dt>Email</dt>
            <dd class="truncate text-app-text">{{ draft.to }}</dd>
            <dt>Password</dt>
            <dd class="text-app-text">Generated when you send</dd>
          </dl>
          <p v-if="draft.already_sent" class="mt-2 text-p-xs text-red-600">
            This customer already has access. Sending again replaces their current password.
          </p>
          <p v-else class="mt-2 text-p-xs text-app-text-muted">
            Their portal and chat login is created only when you press Send.
          </p>
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex w-full items-center justify-end gap-2">
        <AppButton variant="ghost" @click="open = false">Cancel</AppButton>
        <AppButton v-if="!loading && !blocked" icon="send" :loading="sending" @click="submit">
          {{ draft.already_sent ? 'Resend' : 'Send' }}
        </AppButton>
      </div>
    </template>
  </Dialog>
  <MissingEmailDialog v-model="showMissing" :customer="customer" @saved="open = true" />
</template>

<script setup>
// "Portal & Chat Access": opens the email for review (same layout as the
// mailbox's compose window), and sending it is what creates the customer's
// website user and mails the sign-in details. Nothing exists before that.
import { computed, reactive, ref, watch } from 'vue'
import { Dialog, TextEditor, call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import MissingEmailDialog from '@/components/common/MissingEmailDialog.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { notify } from '@/utils/common/notify'

const open = defineModel({ type: Boolean, default: false })
const props = defineProps({ customer: { type: String, required: true } })
const emit = defineEmits(['sent'])

const showMissing = ref(false)
const loading = ref(false)
const sending = ref(false)
const draft = ref({})
const form = reactive({ subject: '', message: '' })

const blocked = computed(() => {
  const d = draft.value
  if (!d.chat_installed) return 'The Verp Chat app is not installed on this site.'
  if (d.ended) return "This customer's service has ended, so access can't be issued."
  if (!d.to) return "Add an email address to this customer's Lead Details first."
  return ''
})
const title = computed(() => (draft.value.already_sent ? 'Resend portal & chat access' : 'Send portal & chat access'))

const errorText = (e) => e?.messages?.[0] || e?.message || 'Something went wrong'

watch(open, async (isOpen) => {
  if (!isOpen) return
  loading.value = true
  draft.value = {}
  try {
    draft.value = await call('verp_staffing.crm.api.customer_chat.get_portal_access_draft', { customer: props.customer })
    form.subject = draft.value.subject
    form.message = draft.value.message
    // No email on the customer's Lead Details: collect one, then come back here.
    if (!draft.value.to && draft.value.chat_installed && !draft.value.ended) {
      open.value = false
      showMissing.value = true
    }
  } catch (e) {
    notify.error(errorText(e))
    open.value = false
  } finally {
    loading.value = false
  }
})

async function submit() {
  if (!form.subject.trim()) return notify.error('Add a subject.')
  sending.value = true
  try {
    await call('verp_staffing.crm.api.customer_chat.send_portal_access', {
      customer: props.customer,
      subject: form.subject,
      message: form.message,
    })
    notify.success('Portal & chat access sent.')
    open.value = false
    emit('sent')
  } catch (e) {
    notify.error(errorText(e))
  } finally {
    sending.value = false
  }
}
</script>
