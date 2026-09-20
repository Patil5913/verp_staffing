<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" @back="goBack">
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
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="visibleFields" />
      </div>
    </template>

    <template #tab-notes>
      <ActivityTimeline
        :doctype="doctype"
        :name="name"
        :types="['note', 'update']"
        show-composer
        empty-text="Nothing here yet — add the first note below."
      />
    </template>

    <template #tab-activity>
      <ActivityTimeline
        :doctype="doctype"
        :name="name"
        :types="['task', 'event']"
        allow-create
        empty-text="No tasks or events linked to this record yet."
      />
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
// Email Account's own detail page — currently just the generic Details/
// Notes/Activity layout with the doctype pinned, kept separate from the
// generic DocDetailPage.vue on purpose so any Email-Account-specific
// customization added later has a dedicated place to live instead of
// growing another doctype branch in the shared fallback. See router.js for
// how /Email Account/:name is routed here ahead of the generic
// /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
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
const VISIBLE_FIELDS = [
  'email_account_name',
  'email_id',
  'domain',
  'password',
  'brand_logo',
  'footer',
  'signature',
  'add_signature',
  'enable_auto_reply',
  'auto_reply_message',
  'attachment_limit',
]
const visibleFields = computed(() => (isSystemManager() ? [...VISIBLE_FIELDS, 'default_outgoing'] : VISIBLE_FIELDS))

const FIXED_VALUES = { enable_outgoing: 1, enable_incoming: 1, auth_method: 'Basic' }
function saveWithDefaults() {
  Object.assign(detail.values, FIXED_VALUES)
  return onSave()
}

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')
</script>
