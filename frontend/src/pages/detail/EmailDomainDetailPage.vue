<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" :detail="detail" @back="goBack">
    <template #actions>
      <RecordActionBar
        show-save
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="!detail.isNew.value && detail.canDelete.value"
        :delete-loading="deleting"
        @save="onSave"
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
// Email Domain's own detail page - currently just the generic Details/
// Notes/Activity layout with the doctype pinned, kept separate from the
// generic DocDetailPage.vue on purpose so any Email-Domain-specific
// customization added later (e.g. surfacing its linked Email Accounts) has
// a dedicated place to live instead of growing another doctype branch in
// the shared fallback. See router.js for how /Email Domain/:name is routed
// here ahead of the generic /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()

const doctype = computed(() => 'Email Domain')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

// Details tab split into four cards, each a curated field subset.
const sections = [
  { title: 'Domain', fieldnames: ['domain_name'] },
  { title: 'Outgoing Mail', fieldnames: ['smtp_server', 'smtp_port', 'use_tls', 'use_ssl_for_outgoing'] },
  { title: 'Incoming Mail', fieldnames: ['email_server', 'incoming_port', 'use_imap', 'use_ssl', 'use_starttls'] },
  { title: 'Mail Preferences', fieldnames: ['attachment_limit', 'append_emails_to_sent_folder', 'sent_folder_name'] },
]

const tabs = [{ key: 'details', label: 'Details' }]
const activeTab = ref('details')
</script>
