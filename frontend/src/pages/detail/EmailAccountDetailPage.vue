<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" :detail="detail" @back="goBack">
    <template #actions>
      <RecordActionBar
        show-save
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="!detail.isNew.value && detail.canDelete.value"
        :delete-loading="deleting"
        @save="saveWithDefaults"
        @delete="showDeleteDialog = true"
      />
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4 flex flex-col gap-6">
        <DocDetailView
          v-for="section in sections"
          :key="section.title"
          :doctype="doctype"
          :detail="detail"
          :title="section.title"
          :fieldnames="section.fieldnames"
        />
      </div>
    </template>
  </DetailPageLayout>

  <Dialog
    v-model="showDeleteDialog"
    :options="{
      title: `Delete this ${doctype}?`,
      message: `This permanently deletes this record. This can't be undone.`,
      icon: { name: 'trash-2', appearance: 'danger' },
    }"
  >
    <template #actions>
      <AppButton variant="danger" icon="trash-2" :loading="deleting" @click="onDelete">Delete</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// Email Account's own detail page - currently just the generic Details/
// Notes/Activity layout with the doctype pinned, kept separate from the
// generic DocDetailPage.vue on purpose so any Email-Account-specific
// customization added later has a dedicated place to live instead of
// growing another doctype branch in the shared fallback. See router.js for
// how /Email Account/:name is routed here ahead of the generic
// /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog, call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { isSystemManager } from '@/utils/common/roles'

const route = useRoute()

const doctype = computed(() => 'Email Account')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

// override/email_account.js: everything but these fields is hidden, and only a
// System Manager gets to choose the default outgoing account. Outgoing,
// incoming and the Basic auth method are fixed rather than chosen.
const sections = computed(() => [
  { title: 'Account', fieldnames: ['email_account_name', 'email_id', 'domain', 'password'] },
  {
    title: 'Mail Preferences',
    fieldnames: isSystemManager() ? ['attachment_limit', 'default_outgoing'] : ['attachment_limit'],
  },
  { title: 'Branding', fieldnames: ['brand_logo'] },
])

const FIXED_VALUES = { enable_outgoing: 1, enable_incoming: 1, auth_method: 'Basic' }
// The desk form copies these from the Email Domain client-side; the server
// doesn't, so without them Frappe falls back to plain SMTP (no SSL) and the
// connection check times out on implicit-SSL ports like 465.
const DOMAIN_FIELDS = [
  'email_server', 'use_imap', 'use_ssl', 'use_starttls', 'use_tls', 'attachment_limit',
  'smtp_server', 'smtp_port', 'use_ssl_for_outgoing', 'append_emails_to_sent_folder', 'incoming_port',
]
async function saveWithDefaults() {
  if (detail.values.domain) {
    const domain = await call('frappe.client.get', { doctype: 'Email Domain', name: detail.values.domain })
    for (const f of DOMAIN_FIELDS) detail.values[f] = domain[f]
  }
  Object.assign(detail.values, FIXED_VALUES)
  // Email Account.validate rejects IMAP incoming with no folder; the desk form
  // seeds Inbox, this one hides the table so it has to be seeded here.
  if (!detail.values.imap_folder?.length) detail.values.imap_folder = [{ folder_name: 'INBOX' }]
  return onSave()
}

const tabs = [{ key: 'details', label: 'Details' }]
const activeTab = ref('details')
</script>
