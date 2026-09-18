<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" @back="goBack">
    <template #actions>
      <RecordActionBar
        show-save
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="!detail.isNew.value && detail.canDelete.value"
        :delete-loading="deleting"
        @save="onSave"
        @delete="showDeleteDialog = true"
      >
        <ForwardCandidateButton
          v-if="!detail.isNew.value && detail.values.customer"
          doctype="Training"
          :name="name"
          :customer="detail.values.customer"
          from-service-name="Training"
          @forwarded="detail.refresh"
        />
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-6 py-4">
        <div class="flex flex-col gap-6">
          <div class="flex flex-col gap-1.5">
            <label class="text-p-sm font-medium text-app-text-muted">Assign To</label>
            <AppLinkField
              doctype="Employee"
              v-model="detail.values.assign_to"
              :disabled="!detail.canWrite.value || locked"
              :query="assignToQuery"
              :filters="assignToFilters"
            />
          </div>
          <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="['status']" :read-only-fields="locked ? ['status'] : []" />
          <ServiceResumePanel :customer="detail.values.customer" />
        </div>
      </div>
    </template>

    <template #tab-proof-of-work>
      <div class="h-full overflow-y-auto px-6 py-4">
        <ChildTableField
          v-if="proofOfWorkTable"
          :table="proofOfWorkTable"
          :rows="detail.values.proof_of_work || []"
          :disabled="!detail.canWrite.value || locked"
          @update:rows="(rows) => (detail.values.proof_of_work = rows)"
        />
      </div>
    </template>

    <template #tab-feedback>
      <div class="h-full overflow-y-auto px-6 py-4">
        <ChildTableField
          v-if="customerFeedbackTable"
          :table="customerFeedbackTable"
          :rows="detail.values.customer_feedback || []"
          disabled
          @update:rows="() => {}"
        />
      </div>
    </template>

    <template #tab-notes>
      <ActivityTimeline :doctype="doctype" :name="name" :types="['note']" show-composer empty-text="Nothing here yet — add the first note below." />
    </template>

    <template #tab-updates>
      <ActivityTimeline :doctype="doctype" :name="name" :types="['update']" empty-text="No updates yet." />
    </template>

    <template #tab-activity>
      <ActivityTimeline :doctype="doctype" :name="name" :types="['task', 'event']" allow-create empty-text="No tasks or events linked to this record yet." />
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
// Training's detail page — a "service record" for a Customer, same shape
// as Interview Support and Technical Other Services (see those pages'
// header comments and public/js/reusable.js's refresh() for the desk form
// this mirrors). assign_to/status lock once status is "Completed", same as
// the desk form's frm.set_df_property calls.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import ServiceResumePanel from '@/components/detail/ServiceResumePanel.vue'
import ForwardCandidateButton from '@/components/detail/ForwardCandidateButton.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()

const doctype = computed(() => 'Training')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

const locked = computed(() => detail.values.status === 'Completed')

const TABS = [
  { key: 'details', label: 'Details' },
  { key: 'proof-of-work', label: 'Proof Of Work' },
  { key: 'feedback', label: 'Customer Feedback' },
  { key: 'notes', label: 'Notes' },
  { key: 'updates', label: 'Updates' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? TABS.filter((t) => t.key === 'details') : TABS))
const activeTab = ref('details')

const proofOfWorkTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'proof_of_work'))
const customerFeedbackTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'customer_feedback'))

const assignToQuery = 'verp_staffing.crm.api.helpers.get_assign_to_by_service'
const assignToFilters = computed(() => ({ service: 'Training', customer: detail.values.customer }))
</script>
