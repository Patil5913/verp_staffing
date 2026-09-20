<template>
  <section class="flex h-full min-h-0 w-full flex-col bg-app-panel">
    <div v-if="!message" class="flex h-full flex-col items-center justify-center gap-2 px-3 md:px-6 text-center">
      <span class="lucide-mail-open size-12 text-app-text-muted/60" />
      <p class="text-p-lg font-medium text-app-text">Select a message to read</p>
      <p class="text-p-sm text-app-text-muted">{{ hint }}</p>
    </div>

    <template v-else>
      <!-- Actions -->
      <div class="flex h-11 shrink-0 items-center gap-1 border-b border-app-border px-3">
        <button type="button" class="flex size-8 items-center justify-center rounded-md text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-app-text lg:hidden" title="Back" @click="$emit('close')"><span class="lucide-arrow-left size-4" /></button>

        <template v-if="message.queue">
          <button type="button" class="tool" @click="$emit('outbox', message.name, 'send_now')"><span class="lucide-send size-4" />Send now</button>
          <button type="button" class="tool text-red-600" @click="$emit('outbox', message.name, 'cancel')"><span class="lucide-x size-4" />Cancel sending</button>
        </template>
        <template v-else>
          <button v-if="canReply" type="button" class="tool" @click="$emit('reply', message)"><span class="lucide-reply size-4" />Reply</button>
          <button v-if="canReply && hasOthers" type="button" class="tool" @click="$emit('reply-all', message)"><span class="lucide-reply-all size-4" />Reply all</button>
          <button v-if="canReply" type="button" class="tool" @click="$emit('forward', message)"><span class="lucide-forward size-4" />Forward</button>
          <span class="flex-1" />
          <button type="button" class="icon-tool" :class="message.starred ? 'text-amber-500' : ''" :title="message.starred ? 'Remove star' : 'Star'" @click="$emit('action', message.starred ? 'unstar' : 'star')"><span class="lucide-star size-4" :class="message.starred ? 'fill-current' : ''" /></button>
          <button type="button" class="icon-tool" :title="message.seen ? 'Mark unread' : 'Mark read'" @click="$emit('action', message.seen ? 'unread' : 'read')"><span :class="message.seen ? 'lucide-mail' : 'lucide-mail-open'" class="size-4" /></button>
          <template v-if="folder === 'trash'">
            <button type="button" class="tool" @click="$emit('action', 'restore')"><span class="lucide-undo-2 size-4" />Restore</button>
            <button type="button" class="tool text-red-600" @click="$emit('action', 'delete')"><span class="lucide-trash-2 size-4" />Delete forever</button>
          </template>
          <template v-else>
            <button v-if="folder === 'spam'" type="button" class="tool" @click="$emit('action', 'not_spam')"><span class="lucide-shield-check size-4" />Not spam</button>
            <button v-else-if="message.sent_or_received === 'Received'" type="button" class="icon-tool" title="Report spam" @click="$emit('action', 'spam')"><span class="lucide-shield-alert size-4" /></button>
            <button type="button" class="icon-tool hover:!text-red-600" title="Move to Trash" @click="$emit('action', 'trash')"><span class="lucide-trash-2 size-4" /></button>
          </template>
        </template>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto">
        <div class="mx-auto flex max-w-3xl flex-col gap-4 px-3 md:px-6 py-5">
          <div class="flex items-start justify-between gap-3">
            <h2 class="text-xl font-semibold leading-snug text-app-text">{{ message.subject || '(no subject)' }}</h2>
            <span v-if="folder === 'spam'" class="shrink-0 rounded-full bg-red-500/15 px-2 py-0.5 text-p-xs font-medium text-red-700">Spam</span>
          </div>

          <div v-if="message.error" class="flex items-start gap-2 rounded-lg border border-red-300 bg-red-500/10 px-3 py-2 text-p-sm text-red-700">
            <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0" /><span class="min-w-0 break-words">{{ message.error }}</span>
          </div>
          <div v-if="folder === 'spam'" class="rounded-lg border border-amber-300 bg-amber-500/10 px-3 py-2 text-p-sm text-amber-800">
            This sender was reported as spam. Pictures and links are shown as sent — only open things you trust.
          </div>

          <!-- Earlier messages in the conversation -->
          <div v-if="message.thread?.length" class="rounded-xl border border-app-border">
            <button type="button" class="flex w-full items-center gap-2 px-4 py-2 text-left text-p-sm font-medium text-app-text-muted hover:text-app-text" @click="showThread = !showThread">
              <span class="size-4" :class="showThread ? 'lucide-chevron-down' : 'lucide-chevron-right'" />
              {{ message.thread.length }} other {{ message.thread.length === 1 ? 'message' : 'messages' }} in this conversation
            </button>
            <div v-if="showThread" class="divide-y divide-app-border border-t border-app-border">
              <div v-for="t in message.thread" :key="t.name" class="px-4 py-3">
                <button type="button" class="flex w-full items-center gap-2 text-left" @click="toggleThread(t.name)">
                  <div class="flex size-7 shrink-0 items-center justify-center rounded-full text-p-xs font-semibold" :class="avatarTone(t.sender)">{{ initials(senderName(t)) }}</div>
                  <span class="min-w-0 flex-1 truncate text-p-sm"><span class="font-medium text-app-text">{{ senderName(t) }}</span> <span class="text-app-text-muted">— {{ t.snippet }}</span></span>
                  <span class="shrink-0 text-p-xs text-app-text-muted">{{ mailDate(t.communication_date) }}</span>
                </button>
                <MailBody v-if="openThread.has(t.name)" :html="t.content" class="mt-2" />
              </div>
            </div>
          </div>

          <!-- Header -->
          <div class="flex items-start gap-3">
            <div class="flex size-10 shrink-0 items-center justify-center rounded-full text-p-sm font-semibold" :class="avatarTone(message.sender)">{{ initials(senderName(message)) }}</div>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-baseline justify-between gap-x-3">
                <p class="truncate text-p-base font-medium text-app-text">{{ senderName(message) }} <span class="text-p-sm font-normal text-app-text-muted">&lt;{{ message.sender }}&gt;</span></p>
                <p class="shrink-0 text-p-xs text-app-text-muted">{{ mailDate(message.communication_date, { long: true }) }}</p>
              </div>
              <button type="button" class="flex items-center gap-1 text-p-xs text-app-text-muted hover:text-app-text" @click="showRecipients = !showRecipients">
                to {{ shortRecipients }}<span class="size-3" :class="showRecipients ? 'lucide-chevron-up' : 'lucide-chevron-down'" />
              </button>
              <dl v-if="showRecipients" class="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-p-xs text-app-text-muted">
                <dt>To</dt><dd class="break-words text-app-text">{{ message.recipients || '—' }}</dd>
                <template v-if="message.cc"><dt>Cc</dt><dd class="break-words text-app-text">{{ message.cc }}</dd></template>
                <template v-if="message.bcc"><dt>Bcc</dt><dd class="break-words text-app-text">{{ message.bcc }}</dd></template>
              </dl>
              <router-link v-if="message.reference_name" :to="`/${encodeURIComponent(message.reference_doctype)}/${encodeURIComponent(message.reference_name)}`" class="mt-1.5 inline-flex items-center gap-1 rounded-full bg-app-primary-tint px-2 py-0.5 text-p-xs font-medium text-app-primary hover:underline">
                <span class="lucide-link size-3" />{{ message.reference_doctype }}: {{ message.reference_title || message.reference_name }}
              </router-link>
            </div>
          </div>

          <div v-if="messageLoading" class="flex justify-center py-8"><LoadingIndicator class="h-5 w-5 text-app-text-muted" /></div>
          <MailBody v-else-if="!message.queue || message.content" :html="message.content" />
          <p v-else class="text-p-sm text-app-text-muted">{{ message.snippet }}</p>

          <div v-if="message.attachments?.length" class="flex flex-wrap gap-2 border-t border-app-border pt-3">
            <a v-for="f in message.attachments" :key="f.name" :href="f.file_url" target="_blank" rel="noopener" class="flex max-w-xs items-center gap-2 rounded-lg border border-app-border bg-app-bg px-3 py-1.5 text-p-sm text-app-text transition-colors hover:border-app-primary/50">
              <span class="lucide-paperclip size-4 shrink-0 text-app-text-muted" />
              <span class="min-w-0 truncate">{{ f.file_name }}</span>
              <span class="shrink-0 text-p-xs text-app-text-muted">{{ fileSize(f.file_size) }}</span>
            </a>
          </div>

          <!-- Quick reply -->
          <div v-if="canReply && !messageLoading" class="rounded-xl border border-app-border bg-app-bg">
            <button v-if="!replying" type="button" class="flex w-full items-center gap-2 px-4 py-3 text-left text-p-sm text-app-text-muted hover:text-app-text" @click="replying = true">
              <span class="lucide-reply size-4" />Reply to {{ senderName(message) }}…
            </button>
            <div v-else class="flex flex-col gap-2 p-3">
              <p class="text-p-xs text-app-text-muted">To: {{ message.sender }}</p>
              <TextEditor :content="replyHtml" editor-class="min-h-[110px] rounded-lg border border-app-border bg-app-panel px-3 py-2 text-p-sm" placeholder="Write your reply…" @change="(html) => (replyHtml = html)" />
              <div class="flex items-center justify-end gap-2">
                <button type="button" class="rounded-lg px-3 py-1.5 text-p-sm text-app-text-muted hover:bg-app-panel-2" @click="discardReply">Discard</button>
                <button type="button" class="rounded-lg px-3 py-1.5 text-p-sm text-app-text-muted hover:bg-app-panel-2" title="Open in the full editor" @click="expandReply">Pop out</button>
                <AppButton icon="send" :loading="sending" :disabled="!hasReplyText" @click="sendQuick">Send</AppButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { LoadingIndicator, TextEditor } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import MailBody from './MailBody.vue'
import { useSendMail } from '@/composables/mail/useSendMail'
import { avatarTone, fileSize, initials, mailDate, quoteMessage, senderName, withPrefix } from '@/utils/mail/format'

const props = defineProps({
  message: { type: Object, default: null },
  messageLoading: Boolean,
  folder: { type: String, default: 'inbox' },
  account: { type: String, default: '' },
})
const emit = defineEmits(['close', 'action', 'reply', 'reply-all', 'forward', 'outbox', 'sent', 'expand'])

const showThread = ref(false)
const showRecipients = ref(false)
const openThread = reactive(new Set())
const toggleThread = (n) => (openThread.has(n) ? openThread.delete(n) : openThread.add(n))

const canReply = computed(() => props.message && !props.message.queue && props.message.sent_or_received === 'Received' && props.folder !== 'trash')
const hasOthers = computed(() => (props.message?.recipients || '').split(',').filter(Boolean).length > 1 || !!props.message?.cc)
const shortRecipients = computed(() => {
  const list = String(props.message?.recipients || '').split(',').map((s) => s.trim()).filter(Boolean)
  return list.length ? (list.length > 2 ? `${list[0]} and ${list.length - 1} others` : list.join(', ')) : 'me'
})
const hint = computed(() => ({ drafts: 'Pick a draft to keep writing.', outbox: 'Pick a message to retry or cancel it.' })[props.folder] || 'Your messages open here.')

// Quick inline reply
const { send, sending } = useSendMail()
const replying = ref(false)
const replyHtml = ref('')
const hasReplyText = computed(() => replyHtml.value.replace(/<[^>]*>/g, '').trim().length > 0)
watch(() => props.message?.name, () => {
  replying.value = false
  replyHtml.value = ''
  showRecipients.value = false
  showThread.value = false
  openThread.clear()
})
function discardReply() {
  replying.value = false
  replyHtml.value = ''
}
async function sendQuick() {
  const m = props.message
  const res = await send({
    to: [m.sender],
    subject: withPrefix(m.subject, 'Re'),
    content: `${replyHtml.value}<br>${quoteMessage(m)}`,
    inReplyTo: m.name,
    account: m.email_account || props.account,
  })
  if (res) {
    discardReply()
    emit('sent')
  }
}
function expandReply() {
  emit('reply', props.message, replyHtml.value)
  discardReply()
}
</script>

<style scoped>
.tool {
  display: inline-flex;
  height: 1.75rem;
  align-items: center;
  gap: 0.375rem;
  border-radius: 0.375rem;
  padding: 0 0.5rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--app-text);
  transition: background-color 0.15s;
}
.tool:hover {
  background-color: var(--app-panel-2);
}
.icon-tool {
  display: inline-flex;
  width: 2rem;
  height: 2rem;
  align-items: center;
  justify-content: center;
  border-radius: 0.375rem;
  color: var(--app-text-muted);
  transition: background-color 0.15s, color 0.15s;
}
.icon-tool:hover {
  background-color: var(--app-panel-2);
  color: var(--app-text);
}
</style>
