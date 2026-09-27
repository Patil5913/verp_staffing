<template>
  <Teleport to="body">
  <div v-if="open && minimized" class="fixed bottom-0 right-6 z-50 flex w-72 items-center gap-2 rounded-t-xl border border-b-0 border-app-border bg-app-panel px-3 py-2 shadow-xl">
    <button type="button" class="min-w-0 flex-1 truncate text-left text-p-sm font-medium text-app-text" @click="minimized = false">{{ form.subject || title }}</button>
    <button type="button" class="flex size-7 items-center justify-center rounded-md text-app-text-muted hover:bg-app-panel-2" title="Expand" @click="minimized = false"><span class="lucide-maximize-2 size-4" /></button>
    <button type="button" class="flex size-7 items-center justify-center rounded-md text-app-text-muted hover:bg-app-panel-2" title="Save and close" @click="saveAndClose"><span class="lucide-x size-4" /></button>
  </div>
  <div v-show="open && !minimized" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
  <div class="flex h-[90vh] w-[90vw] flex-col overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-xl">
    <div class="flex h-12 shrink-0 items-center gap-2 border-b border-app-border px-4">
      <h2 class="flex-1 truncate text-p-lg font-semibold text-app-text">{{ title }}</h2>
      <span class="hidden items-center gap-1.5 text-p-xs text-app-text-muted sm:flex">Press <kbd class="rounded border border-app-border bg-app-panel-2 px-1.5 py-0.5 font-sans font-medium text-app-text">Esc</kbd> to exit</span>
      <button type="button" class="inline-flex h-8 items-center gap-1 rounded-md border border-app-border px-2.5 text-p-xs font-medium text-app-text hover:bg-app-panel-2" title="Exit (Esc)" @click="saveAndClose">Esc</button>
      <button type="button" class="flex size-8 items-center justify-center rounded-md text-app-text-muted hover:bg-app-panel-2 hover:text-app-text" title="Minimize" @click="minimized = true"><span class="lucide-minus size-4" /></button>
      <button type="button" class="flex size-8 items-center justify-center rounded-md text-app-text-muted hover:bg-app-panel-2 hover:text-app-text" title="Save draft and close" @click="saveAndClose"><span class="lucide-x size-4" /></button>
    </div>
    <div class="min-h-0 flex-1 overflow-y-auto">
      <div :key="formKey" class="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-5">
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

        <TextEditor class="mail-editor" :fixed-menu="MAIL_MENU" :content="form.content" editor-class="min-h-[45vh] text-p-sm" placeholder="Write your message…" @change="(html) => (form.content = html)" />

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
    </div>
    <div class="shrink-0 border-t border-app-border px-4 py-3">
      <div class="mx-auto flex w-full max-w-5xl items-center justify-between gap-2">
        <button type="button" class="inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-p-sm text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-red-600" @click="discard"><span class="lucide-trash-2 size-4" />Discard</button>
        <div class="flex items-center gap-2">
          <button type="button" class="inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-p-sm font-medium text-app-text transition-colors hover:bg-app-panel-2" @click="saveAndClose"><span class="lucide-save size-4" />Save draft</button>
          <AppButton icon="send" :loading="sending" @click="submit">Send</AppButton>
        </div>
      </div>
    </div>
  </div>
  </div>
  </Teleport>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
// New message / reply / reply all / forward. Closing with something written
// keeps it as a draft (on this device); Send goes through the mailbox API,
// which sends as one of the user's own accounts.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { FileUploader, TextEditor } from 'frappe-ui'
import { MAIL_MENU } from '@/utils/mail/editorMenu'
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
const minimized = ref(false)
const showCc = ref(false)
const showBcc = ref(false)
const problem = ref('')
let handled = false // sent, saved or discarded - nothing left to auto-save

const onKey = (e) => {
  if (e.key === 'Escape' && open.value && !minimized.value) saveAndClose()
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

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
    minimized.value = false
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
