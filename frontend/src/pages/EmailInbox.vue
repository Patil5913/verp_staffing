<template>
  <div class="mx-auto flex h-[calc(100vh-4rem)] max-w-6xl gap-4 px-6 py-8">
    <!-- Message list -->
    <div class="flex w-80 shrink-0 flex-col overflow-hidden rounded-lg border border-app-border bg-app-panel">
      <div class="flex items-center justify-between border-b border-app-border px-3 py-2">
        <h1 class="text-p-base font-semibold text-app-text">Inbox</h1>
        <Button variant="ghost" icon="refresh-cw" @click="list.resource.reload()" />
      </div>

      <StateBanner
        v-if="list.hasError"
        icon="alert-triangle"
        title="Couldn't load inbox"
        :description="list.errorMessage"
      />
      <div v-else-if="list.isLoading && !list.resource.data" class="flex justify-center py-10">
        <LoadingIndicator class="h-5 w-5 text-app-text-muted" />
      </div>
      <StateBanner v-else-if="!list.resource.data?.length" icon="inbox" title="No messages" />

      <div v-else class="flex-1 overflow-y-auto">
        <button
          v-for="msg in list.resource.data"
          :key="msg.name"
          type="button"
          class="flex w-full flex-col gap-0.5 border-b border-app-border px-3 py-2.5 text-left hover:bg-app-panel-2"
          :class="[selected?.name === msg.name ? 'bg-app-panel-2' : '', !msg.seen ? 'font-semibold' : '']"
          @click="select(msg)"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="truncate text-p-base text-app-text">{{ msg.sender_full_name || msg.sender }}</span>
            <span class="shrink-0 text-2xs text-app-text-muted">{{ formatRelativeTime(msg.communication_date) }}</span>
          </div>
          <span class="truncate text-p-sm text-app-text-muted">{{ msg.subject || '(no subject)' }}</span>
        </button>
      </div>
    </div>

    <!-- Detail / reply -->
    <div class="flex flex-1 flex-col overflow-hidden rounded-lg border border-app-border bg-app-panel">
      <StateBanner v-if="!selected" icon="mail" title="Select a message" class="m-auto" />

      <template v-else>
        <div class="border-b border-app-border px-5 py-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="truncate text-lg font-semibold text-app-text">{{ selected.subject || '(no subject)' }}</div>
              <div class="mt-1 text-p-sm text-app-text-muted">
                {{ selected.sender_full_name || selected.sender }} &lt;{{ selected.sender }}&gt;
              </div>
            </div>
            <div class="flex shrink-0 gap-1">
              <Button variant="ghost" :icon="selected.seen ? 'mail' : 'mail-open'" @click="toggleRead" />
              <Button variant="ghost" icon="alert-octagon" @click="onSpam" />
              <Button variant="ghost" icon="trash-2" @click="onTrash" />
            </div>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto px-5 py-4 text-p-base text-app-text" v-html="selected.content" />

        <div class="border-t border-app-border p-4">
          <TextEditor
            :content="replyContent"
            editor-class="min-h-[100px] rounded-b-lg border border-t-0 border-app-border px-3 py-2"
            @change="(html) => (replyContent = html)"
          />
          <div class="mt-2 flex justify-end">
            <Button variant="solid" :loading="reply.loading" :disabled="!replyContent" @click="onReply">
              Send Reply
            </Button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, LoadingIndicator, TextEditor } from 'frappe-ui'
import { useResource } from '@/composables/useResource'
import { formatRelativeTime } from '@/utils/formatValue'
import { notify } from '@/utils/notify'
import StateBanner from '@/components/StateBanner.vue'

// Scoped to a unified inbox (list/read/reply/flag/trash/spam) — per-account
// folder switching isn't wired up because frappe.email.inbox.get_email_accounts
// (the method that would list them) isn't whitelisted, only its 4 action
// methods are.
const list = useResource({
  url: 'frappe.client.get_list',
  params: {
    doctype: 'Communication',
    filters: [
      ['communication_type', '=', 'Communication'],
      ['communication_medium', '=', 'Email'],
      ['email_status', 'not in', ['Trash', 'Spam']],
    ],
    fields: [
      'name', 'subject', 'sender', 'sender_full_name', 'content',
      'communication_date', 'seen', 'email_status', 'reference_doctype', 'reference_name',
    ],
    order_by: 'communication_date desc',
    limit_page_length: 50,
  },
  auto: true,
})

const selected = ref(null)
const replyContent = ref('')

function select(msg) {
  selected.value = msg
  replyContent.value = ''
  if (!msg.seen) markSeen(msg, 'Read')
}

const flag = useResource({ url: 'frappe.email.inbox.create_email_flag_queue' })

function markSeen(msg, action) {
  flag.resource.submit({ names: JSON.stringify([msg.name]), action }).then(() => {
    msg.seen = action === 'Read' ? 1 : 0
  })
}

function toggleRead() {
  markSeen(selected.value, selected.value.seen ? 'Unread' : 'Read')
}

const trash = useResource({
  url: 'frappe.email.inbox.mark_as_trash',
  onSuccess() {
    notify.success('Moved to trash.')
    list.resource.reload()
    selected.value = null
  },
})
function onTrash() {
  trash.resource.submit({ communication: selected.value.name })
}

const spam = useResource({
  url: 'frappe.email.inbox.mark_as_spam',
  onSuccess() {
    notify.success('Marked as spam.')
    list.resource.reload()
    selected.value = null
  },
})
function onSpam() {
  spam.resource.submit({ communication: selected.value.name, sender: selected.value.sender })
}

const reply = useResource({
  url: 'frappe.core.doctype.communication.email.make',
  onSuccess() {
    notify.success('Reply sent.')
    replyContent.value = ''
    list.resource.reload()
  },
})
function onReply() {
  const msg = selected.value
  reply.resource.submit({
    doctype: msg.reference_doctype || undefined,
    name: msg.reference_name || undefined,
    content: replyContent.value,
    subject: msg.subject?.startsWith('Re:') ? msg.subject : `Re: ${msg.subject || ''}`,
    recipients: msg.sender,
    communication_medium: 'Email',
    sent_or_received: 'Sent',
    send_email: 1,
    in_reply_to: msg.name,
  })
}
</script>
