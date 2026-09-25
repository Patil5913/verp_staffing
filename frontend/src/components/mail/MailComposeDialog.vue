<template>
  <Dialog v-model="open" :options="{ title: title, size: '3xl' }">
    <template #body-content>
      <div :key="formKey" class="flex flex-col gap-3">
        <div class="grid grid-cols-[3.5rem_1fr] items-center gap-x-3 gap-y-2.5">
          <template v-if="accounts.length > 1">
            <label class="text-p-sm text-app-text-muted">From</label>
            <AppCombobox v-model="form.account" :options="accountOptions" compact />
          </template>
          <template v-else-if="accounts.length">
            <label class="text-p-sm text-app-text-muted">From</label>
            <p class="truncate text-p-sm text-app-text">{{ accounts[0].email_id }}</p>
          </template>

          <label class="text-p-sm text-app-text-muted">To</label>
          <div class="flex items-start gap-2">
            <RecipientInput v-model="form.to" placeholder="Add recipients" class="flex-1" />
            <div class="flex shrink-0 gap-1 pt-1.5 text-p-xs font-medium text-app-primary">
              <button v-if="!showCc" type="button" class="hover:underline" @click="showCc = true">Cc</button>
              <button v-if="!showBcc" type="button" class="hover:underline" @click="showBcc = true">Bcc</button>
            </div>
          </div>

          <template v-if="showCc">
            <label class="text-p-sm text-app-text-muted">Cc</label>
            <RecipientInput v-model="form.cc" />
          </template>
          <template v-if="showBcc">
            <label class="text-p-sm text-app-text-muted">Bcc</label>
            <RecipientInput v-model="form.bcc" />
          </template>

          <label class="text-p-sm text-app-text-muted">Subject</label>
          <AppInput v-model="form.subject" placeholder="Subject" />
        </div>

        <TextEditor :content="form.content" editor-class="min-h-[220px] max-h-[45vh] overflow-y-auto rounded-lg border border-app-border px-3 py-2 text-p-sm" placeholder="Write your message…" @change="(html) => (form.content = html)" />

        <div class="flex flex-wrap items-center gap-2">
          <FileUploader :upload-args="{ private: true }" @success="(f) => form.attachments.push(f)" @failure="() => notify.error('Upload failed')">
            <template #default="{ uploading, progress, openFileSelector }">
              <button type="button" class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-app-border px-3 text-p-sm font-medium text-app-text transition-colors hover:bg-app-panel-2" @click="openFileSelector">
                <span class="lucide-paperclip size-4" />{{ uploading ? `Uploading ${progress}%` : 'Attach files' }}
              </button>
            </template>
          </FileUploader>
          <span v-for="(f, i) in form.attachments" :key="f.name" class="inline-flex max-w-xs items-center gap-1.5 rounded-full bg-app-panel-2 py-1 pl-3 pr-1.5 text-p-xs text-app-text">
            <span class="truncate">{{ f.file_name }}</span><span class="text-app-text-muted">{{ fileSize(f.file_size) }}</span>
            <button type="button" class="flex size-4 items-center justify-center rounded-full hover:bg-black/10" :aria-label="`Remove ${f.file_name}`" @click="form.attachments.splice(i, 1)"><span class="lucide-x size-3" /></button>
          </span>
        </div>

        <p v-if="problem" class="text-p-sm text-red-600">{{ problem }}</p>
      </div>
    </template>
    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <button type="button" class="inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-p-sm text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-red-600" @click="discard"><span class="lucide-trash-2 size-4" />Discard</button>
        <div class="flex items-center gap-2">
          <button type="button" class="inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-p-sm font-medium text-app-text transition-colors hover:bg-app-panel-2" @click="saveAndClose"><span class="lucide-save size-4" />Save draft</button>
          <AppButton icon="send" :loading="sending" @click="submit">Send</AppButton>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// New message / reply / reply all / forward. Closing with something written
// keeps it as a draft (on this device); Send goes through the mailbox API,
// which sends as one of the user's own accounts.
import { computed, reactive, ref, watch } from 'vue'
import { Dialog, FileUploader, TextEditor } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import RecipientInput from './RecipientInput.vue'
import { useSendMail } from '@/composables/mail/useSendMail'
import { EMAIL_RE, fileSize } from '@/utils/mail/format'
import { notify } from '@/utils/common/notify'

const open = defineModel({ type: Boolean, default: false })
const props = defineProps({
  // { to, cc, bcc, subject, content, inReplyTo, draftId }
  initial: { type: Object, default: () => ({}) },
  accounts: { type: Array, default: () => [] },
  defaultAccount: { type: String, default: '' },
})
const emit = defineEmits(['sent', 'save-draft', 'discard-draft'])

const { send, sending } = useSendMail()
const blank = () => ({ to: [], cc: [], bcc: [], subject: '', content: '', attachments: [], account: '', inReplyTo: '', draftId: '' })
const form = reactive(blank())
const formKey = ref(0)
const showCc = ref(false)
const showBcc = ref(false)
const problem = ref('')
let handled = false // sent, saved or discarded - nothing left to auto-save

const title = computed(() => (form.inReplyTo ? 'Reply' : form.subject.startsWith('Fwd:') ? 'Forward' : 'New message'))
const outgoing = computed(() => props.accounts.filter((a) => a.enable_outgoing))
const accountOptions = computed(() => outgoing.value.map((a) => ({ label: a.email_id || a.account, value: a.account })))

watch(open, (isOpen) => {
  if (isOpen) {
    Object.assign(form, blank(), { ...props.initial, account: props.initial.account || props.defaultAccount || outgoing.value[0]?.account || '' })
    form.to = [...(props.initial.to || [])]
    form.cc = [...(props.initial.cc || [])]
    form.bcc = [...(props.initial.bcc || [])]
    form.attachments = []
    showCc.value = form.cc.length > 0
    showBcc.value = form.bcc.length > 0
    problem.value = ''
    handled = false
    formKey.value++
  } else if (!handled && hasContent()) {
    keepDraft()
    notify.success('Saved to Drafts')
  }
})

const hasContent = () => form.to.length || form.subject.trim() || form.content.replace(/<[^>]*>/g, '').trim()
const keepDraft = () => emit('save-draft', { id: form.draftId, to: form.to, cc: form.cc, bcc: form.bcc, subject: form.subject, content: form.content, inReplyTo: form.inReplyTo, account: form.account })

function saveAndClose() {
  if (hasContent()) {
    keepDraft()
    notify.success('Saved to Drafts')
  }
  handled = true
  open.value = false
}
function discard() {
  if (form.draftId) emit('discard-draft', form.draftId)
  handled = true
  open.value = false
}

async function submit() {
  problem.value = ''
  const bad = [...form.to, ...form.cc, ...form.bcc].find((e) => !EMAIL_RE.test(e))
  if (!form.to.length) problem.value = 'Add at least one recipient.'
  else if (bad) problem.value = `“${bad}” isn't a valid email address.`
  else if (!form.subject.trim() && !form.content.replace(/<[^>]*>/g, '').trim()) problem.value = 'Write a subject or a message first.'
  if (problem.value) return

  const res = await send({
    to: form.to,
    cc: form.cc,
    bcc: form.bcc,
    subject: form.subject.trim(),
    content: form.content,
    inReplyTo: form.inReplyTo,
    attachments: form.attachments.map((f) => f.name),
    account: form.account,
  })
  if (!res) return
  if (form.draftId) emit('discard-draft', form.draftId)
  handled = true
  open.value = false
  emit('sent')
}
</script>
