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
          doctype="JDC"
          :name="name"
          :customer="detail.hidden.customer"
          from-service-name="JDC"
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
            :fieldnames="DETAIL_FIELDS"
            :field-link-queries="{ assign_to: { query: assignToQuery, filters: assignToFilters } }"
            :read-only-fields="locked ? LOCK_FIELDS : []"
          />

          <div class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
            <h3 class="mb-3 text-p-base font-medium text-app-text">Customer Feedback</h3>
            <ChildTableField
              v-if="feedbackTable && (detail.values.customer_feedback || []).length"
              :table="feedbackTable"
              :rows="detail.values.customer_feedback || []"
              disabled
              @update:rows="() => {}"
            />
            <p v-else class="py-4 text-center text-p-sm text-app-text-muted">No Feedback Yet</p>
          </div>
        </div>
      </div>
    </template>

    <template #tab-proof>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <ChildTableField
          v-if="proofTable"
          :table="proofTable"
          :rows="detail.values.proof_of_work || []"
          :disabled="!detail.canWrite.value || locked"
          :on-file-meta="autoTitleFromFile"
          @update:rows="(rows) => (detail.values.proof_of_work = rows)"
        />
      </div>
    </template>

    <template #tab-notes>
      <ActivityTimeline :doctype="doctype" :name="name" :types="['note']" show-composer empty-text="Nothing here yet - add the first note below." />
    </template>

    <template #tab-updates>
      <ActivityTimeline :doctype="doctype" :name="name" :types="['update']" empty-text="No updates yet." />
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

    <template #tab-customer>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <CustomerContextPanel :customer="detail.hidden.customer" display-key="JDC" />
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
// JDC's (interview session) detail page: Details/Proof of Work/Feedback/
// Notes/Activity - `customer_feedback` is read_only on the doctype itself
// (filled in by the customer's own feedback flow, not edited here), so its
// tab renders the child table disabled rather than letting edits queue up
// with nowhere to go. `customer` is hidden + set_only_once server-side and
// never reaches DETAIL_FIELDS. See router.js for how /JDC/:name is routed
// here ahead of the generic /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import ForwardCandidateButton from '@/components/detail/actions/ForwardCandidateButton.vue'
import CustomerContextPanel from '@/components/detail/customer/CustomerContextPanel.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { autoTitleFromFile } from '@/utils/detail/documentTitle'

const route = useRoute()

const doctype = computed(() => 'JDC')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

const locked = computed(() => detail.values.status === 'Completed')

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'proof', label: 'Proof of Work' },
  { key: 'customer', label: 'Customer' },
  { key: 'notes', label: 'Notes' },
  { key: 'updates', label: 'Updates' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')

const DETAIL_FIELDS = ['interview_round', 'assign_to', 'status', 'scheduled_on', 'from_time', 'to_time']
// Once Completed, the schedule is frozen along with status - matches the
// desk form locking Schedule On/From/To the same moment it locks Status.
const LOCK_FIELDS = ['status', 'scheduled_on', 'from_time', 'to_time']

const assignToQuery = 'verp_staffing.crm.api.helpers.get_assign_to_by_service'
const assignToFilters = computed(() => ({ service: 'JDC', customer: detail.hidden.customer }))

const proofTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'proof_of_work'))
const feedbackTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'customer_feedback'))
</script>
