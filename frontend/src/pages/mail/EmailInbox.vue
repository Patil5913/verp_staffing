<template>
  <div class="flex h-full min-h-0 bg-app-bg">
    <StateBanner
      v-if="loadedOnce && !hasAccount && !error"
      icon="mail-x"
      title="No mailbox is linked to your account"
      description="Ask an administrator to add an email account under your user's Email Accounts, then reload."
      class="m-auto max-w-md"
    />

    <template v-else>
      <!-- Folders -->
      <div class="hidden w-56 shrink-0 md:block">
        <MailSidebar
          :folder="folder"
          :counts="counts"
          :draft-count="drafts.length"
          :accounts="accounts"
          :account="account"
          :can-compose="canSend"
          @update:folder="folder = $event"
          @update:account="account = $event"
          @compose="compose()"
        />
      </div>

      <!-- Message list (a phone-sized screen shows either this or the reader) -->
      <div class="min-w-0 border-r border-app-border" :class="[readerOpen ? 'hidden lg:block' : 'block flex-1', 'lg:w-[26rem] lg:flex-none']">
        <!-- Folder picker for narrow screens, where the sidebar is hidden -->
        <div class="flex items-center gap-2 border-b border-app-border bg-app-panel px-3 py-2 md:hidden">
          <AppCombobox v-model="folder" :options="FOLDER_OPTIONS" compact class="flex-1" />
          <button type="button" class="flex h-7 items-center gap-1 rounded-lg bg-app-primary px-3 text-p-xs font-medium text-white disabled:opacity-50" :disabled="!canSend" @click="compose()"><span class="lucide-pen-line size-3.5 text-white" />New</button>
        </div>

        <MailList
          v-if="!isDrafts"
          :folder="folder"
          :items="items"
          :total="total"
          :loading="loading || syncing"
          :loading-more="loadingMore"
          :has-more="hasMore"
          :error="error"
          :active-name="openName"
          :checked="checked"
          :all-checked="allChecked"
          v-model:search="search"
          v-model:filter="filter"
          @open="open"
          @toggle="toggleChecked"
          @toggle-all="toggleAll"
          @clear="checked.clear()"
          @star="(m) => act([m.name], m.starred ? 'unstar' : 'star')"
          @bulk="onBulk"
          @more="load({ more: true })"
          @refresh="sync()"
          @empty="confirmEmpty"
        />

        <!-- Drafts live on this device -->
        <section v-else class="flex h-full flex-col bg-app-bg">
          <div class="flex h-10 items-center border-b border-app-border bg-app-panel px-4 text-p-xs text-app-text-muted">{{ drafts.length }} draft{{ drafts.length === 1 ? '' : 's' }} · saved on this device</div>
          <div v-if="!drafts.length" class="flex flex-col items-center gap-2 px-3 md:px-6 py-16 text-center">
            <span class="lucide-file-pen-line size-9 text-app-text-muted" />
            <p class="text-p-base font-medium text-app-text">No drafts</p>
            <p class="max-w-xs text-p-sm text-app-text-muted">Close a message you haven't sent and it's kept here.</p>
          </div>
          <div v-for="d in drafts" :key="d.id" role="button" tabindex="0" class="group flex cursor-pointer items-start gap-3 border-b border-app-border bg-app-panel px-4 py-3 transition-colors hover:bg-app-panel-2" @click="compose(d)" @keydown.enter="compose(d)">
            <span class="lucide-file-pen-line mt-0.5 size-4 shrink-0 text-app-text-muted" />
            <div class="min-w-0 flex-1">
              <div class="flex items-baseline justify-between gap-2">
                <span class="truncate text-p-sm font-medium text-app-text">{{ d.to?.length ? `To: ${d.to.join(', ')}` : 'No recipient' }}</span>
                <span class="shrink-0 text-p-xs text-app-text-muted">{{ mailDate(d.updated) }}</span>
              </div>
              <p class="truncate text-p-sm text-app-text">{{ d.subject || '(no subject)' }}</p>
              <p class="truncate text-p-xs text-app-text-muted">{{ plain(d.content) }}</p>
            </div>
            <button type="button" class="rounded p-1 text-app-text-muted opacity-0 transition-colors hover:bg-app-panel-2 hover:text-red-600 group-hover:opacity-100" title="Delete draft" @click.stop="removeDraft(d.id)"><span class="lucide-trash-2 size-4" /></button>
          </div>
        </section>
      </div>

      <!-- Reader -->
      <div class="min-w-0 flex-1" :class="readerOpen ? 'block' : 'hidden lg:block'">
        <MailReader
          :message="message"
          :message-loading="messageLoading"
          :folder="folder"
          :account="account"
          @close="close"
          @action="(a) => act([message.name], a)"
          @reply="(m, html) => reply(m, false, html)"
          @reply-all="(m) => reply(m, true)"
          @forward="forward"
          @outbox="outbox"
          @sent="onSent"
        />
      </div>
    </template>

    <MailComposeDialog v-model="composing" :initial="composeInitial" :accounts="accounts" :default-account="account" @sent="onSent" @save-draft="saveDraft" @discard-draft="removeDraft" />
  </div>
</template>

<script setup>
// Email Inbox: folders (Inbox, Starred, Sent, Drafts, Outbox, Spam, Trash, All
// mail) on the left, the message list with search / filters / bulk actions in
// the middle, and the reading pane with reply, reply all, forward and a quick
// reply on the right. New message opens the composer. Everything talks to
// verp_staffing.utils.mailbox, which shows only the user's own accounts.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import MailComposeDialog from '@/components/mail/MailComposeDialog.vue'
import MailList from '@/components/mail/MailList.vue'
import MailReader from '@/components/mail/MailReader.vue'
import MailSidebar from '@/components/mail/MailSidebar.vue'
import { useMailbox } from '@/composables/mail/useMailbox'
import { confirmLeave } from '@/utils/common/confirmDialog'
import { mailDate, quoteMessage, withPrefix, parseAddresses } from '@/utils/mail/format'
import { getSocket } from '@/utils/common/realtime'
import { notify } from '@/utils/common/notify'

const {
  folder, filter, search, account,
  items, total, counts, accounts, loading, loadingMore, error, loadedOnce, hasMore, hasAccount,
  checked, allChecked, toggleAll, toggleChecked,
  openName, message, messageLoading, open, close,
  drafts, saveDraft, removeDraft, isDrafts,
  load, sync, syncing, act, emptyFolder, outbox,
} = useMailbox()

const FOLDER_OPTIONS = [
  { label: 'Inbox', value: 'inbox' },
  { label: 'Starred', value: 'starred' },
  { label: 'Sent', value: 'sent' },
  { label: 'Drafts', value: 'drafts' },
  { label: 'Outbox', value: 'outbox' },
  { label: 'Spam', value: 'spam' },
  { label: 'Trash', value: 'trash' },
  { label: 'All mail', value: 'all' },
]

const readerOpen = computed(() => !!message.value)
const canSend = computed(() => accounts.value.some((a) => a.enable_outgoing))
const plain = (html) => String(html || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120)

function onBulk(action) {
  act([...checked], action)
}

async function confirmEmpty() {
  const label = folder.value === 'spam' ? 'Spam' : 'Trash'
  const ok = await confirmLeave({ title: `Empty ${label}?`, message: `Every message in ${label} is deleted permanently. This can't be undone.`, leaveLabel: 'Empty', cancelLabel: 'Cancel' })
  if (ok) emptyFolder()
}

// ── composing ────────────────────────────────────────────────────────────
const composing = ref(false)
const composeInitial = ref({})

function compose(draft) {
  composeInitial.value = draft ? { ...draft, draftId: draft.id } : {}
  composing.value = true
}
const others = (m, mine) => parseAddresses([m.recipients, m.cc].filter(Boolean).join(',')).map((a) => a.email).filter((e) => e && !mine.includes(e.toLowerCase()) && e.toLowerCase() !== m.sender.toLowerCase())

function reply(m, all, html = '') {
  const mine = accounts.value.map((a) => (a.email_id || '').toLowerCase())
  composeInitial.value = {
    to: [m.sender],
    cc: all ? others(m, mine) : [],
    subject: withPrefix(m.subject, 'Re'),
    content: `${html}${quoteMessage(m)}`,
    inReplyTo: m.name,
    account: m.email_account || '',
  }
  composing.value = true
}
function forward(m) {
  composeInitial.value = { subject: withPrefix(m.subject, 'Fwd'), content: quoteMessage(m, { forward: true }), account: m.email_account || '' }
  composing.value = true
}
function onSent() {
  // A sent message lands in Sent (or Outbox until it goes out) - refresh what's showing.
  load({ quiet: true })
}

// Keep the list fresh while the page is open.
let timer
// The server announces mail as the scheduler pulls it in (utils/mailbox.py's
// on_new_communication), so the list updates as it arrives; the timer is only a
// safety net for a dropped connection.
const socket = getSocket()
function onNewMail(mail) {
  notify.success(`New mail from ${mail?.sender || 'someone'}${mail?.subject ? `: ${mail.subject}` : ''}`)
  if (!composing.value) load({ quiet: true })
}
onMounted(() => {
  load()
  sync({ quiet: true })
  socket.on('verp_new_mail', onNewMail)
  timer = setInterval(() => document.visibilityState === 'visible' && !composing.value && sync({ quiet: true }), 120_000)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  socket.off('verp_new_mail', onNewMail)
})
</script>
