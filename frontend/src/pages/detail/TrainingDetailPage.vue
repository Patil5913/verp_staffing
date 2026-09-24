<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" :detail="detail" @back="goBack">
    <template #actions>
      <RecordActionBar
        show-save
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="false"
        :delete-loading="deleting"
        @save="onSave"
        @delete="showDeleteDialog = true"
      >
        <ForwardCandidateButton
          v-if="!detail.isNew.value && detail.hidden.customer"
          doctype="Training"
          :name="name"
          :customer="detail.hidden.customer"
          from-service-name="Training"
          @forwarded="detail.refresh"
        />
        <FieldUpdateActions :detail="detail" :doctype="doctype" :name="name" mode="service" />
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView
            :doctype="doctype"
            :detail="detail"
            :fieldnames="['assign_to', 'status']"
            :field-link-queries="{ assign_to: { query: assignToQuery, filters: assignToFilters } }"
            :read-only-fields="locked ? ['assign_to', 'status'] : []"
          />
          <ServiceResumePanel :customer="detail.hidden.customer" />

          <div class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
            <h3 class="mb-3 text-p-base font-medium text-app-text">Customer Feedback</h3>
            <!-- Customer Feedback is a normal (visible) child table: its rows live in
                 values, not hidden. Read-only list: when it was given, then what was said. -->
            <ul v-if="feedbackRows.length" class="flex flex-col gap-3">
              <li v-for="(row, i) in feedbackRows" :key="row.name || i" class="rounded-lg border border-app-border bg-app-panel-2/40 p-3">
                <p class="text-p-xs font-medium text-app-text-muted">{{ formatDatetime(row.date) || '—' }}</p>
                <p class="mt-1 whitespace-pre-wrap text-p-sm text-app-text">{{ row.feedback || '—' }}</p>
              </li>
            </ul>
            <p v-else class="py-4 text-center text-p-sm text-app-text-muted">No Feedback Yet</p>
          </div>
        </div>
      </div>
    </template>

    <template #tab-proof-of-work>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <ChildTableField
          v-if="proofOfWorkTable"
          :table="proofOfWorkTable"
          :rows="detail.values.proof_of_work || []"
          :disabled="!detail.canWrite.value || locked"
          :on-file-meta="autoTitleFromFile"
          @update:rows="(rows) => (detail.values.proof_of_work = rows)"
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

    <template #tab-customer>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <CustomerContextPanel :customer="detail.hidden.customer" display-key="Training" />
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
// Training's detail page — a "service record" for a Customer, same shape
// as Interview Support and Technical Other Services (see those pages'
// header comments and public/js/reusable.js's refresh() for the desk form
// this mirrors). assign_to/status lock once status is "Completed", same as
// the desk form's frm.set_df_property calls.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import { formatDatetime } from '@/utils/list/formatValue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import ServiceResumePanel from '@/components/detail/lead/ServiceResumePanel.vue'
import ForwardCandidateButton from '@/components/detail/actions/ForwardCandidateButton.vue'
import CustomerContextPanel from '@/components/detail/customer/CustomerContextPanel.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { autoTitleFromFile } from '@/utils/detail/documentTitle'

const route = useRoute()

const doctype = computed(() => 'Training')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

const locked = computed(() => detail.values.status === 'Completed')

const TABS = [
  { key: 'details', label: 'Details' },
  { key: 'proof-of-work', label: 'Proof Of Work' },
  { key: 'customer', label: 'Customer' },
  { key: 'notes', label: 'Notes' },
  { key: 'updates', label: 'Updates' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? TABS.filter((t) => t.key === 'details') : TABS))
const activeTab = ref('details')

const proofOfWorkTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'proof_of_work'))
const feedbackRows = computed(() => detail.values.customer_feedback || [])

const assignToQuery = 'verp_staffing.crm.api.helpers.get_assign_to_by_service'
const assignToFilters = computed(() => ({ service: 'Training', customer: detail.hidden.customer }))
</script>
