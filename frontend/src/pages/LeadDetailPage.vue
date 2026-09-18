<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" @back="goBack">
    <template #actions>
      <RecordActionBar
        :show-save="!leadLocked"
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="!detail.isNew.value && detail.canDelete.value"
        :delete-loading="deleting"
        @save="onSave"
        @delete="showDeleteDialog = true"
      >
        <AppButton v-if="!leadLocked" variant="outline" icon="target" @click="leadExtrasRef?.showCreateOpportunity()">
          Create Opportunity
        </AppButton>
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView :doctype="doctype" :detail="detail" :force-disabled="leadLocked" :read-only-fields="readOnlyFields" />
          <LeadExtras ref="leadExtrasRef" :lead-name="name" @locked-change="(v) => (leadLocked = v)" />
        </div>
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
// Lead's detail page: the generic Details/Notes/Activity tabs, plus the
// Lead-specific "Lead Detail Form" (candidate-facing fields) and the
// Create Opportunity flow — both live in LeadExtras.vue below the main
// field grid, per the Lead doctype's own layout, not in the generic
// DocDetailPage. See router.js for how /Lead/:name is routed here ahead of
// the generic /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import LeadExtras from '@/components/detail/LeadExtras.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()

const doctype = computed(() => 'Lead')
const name = computed(() => route.params.name)

const leadLocked = ref(false)
const leadExtrasRef = ref(null)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } = useDetailPageController(
  doctype,
  name,
  {
    extraIsDirty: computed(() => leadExtrasRef.value?.isDirty?.value ?? false),
    extraSave: () => leadExtrasRef.value?.save(),
  },
)

// Matches the old desk Lead form's onload(): status is always read-only,
// lead_owner only for non-Administrators — enforced here since these are
// Lead-specific UI rules, not something detail_view.py's generic
// get_doc_meta should know about.
const readOnlyFields = computed(() => {
  const fields = ['status']
  if (window.user !== 'Administrator') fields.push('lead_owner')
  return fields
})

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')
</script>
