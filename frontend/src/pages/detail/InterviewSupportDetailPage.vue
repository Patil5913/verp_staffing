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
          doctype="Interview Support"
          :name="name"
          :customer="detail.hidden.customer"
          from-service-name="Interview Support"
          @forwarded="detail.refresh"
        />
        <FieldUpdateActions :detail="detail" :doctype="doctype" :name="name" mode="service" />
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <div v-if="!detail.values.interview_round" class="flex flex-col gap-1.5">
            <label class="text-p-sm font-medium text-app-text-muted">Interview Round</label>
            <AppLinkField doctype="Interview Round" v-model="detail.values.interview_round" :disabled="!detail.canWrite.value" />
          </div>

          <div v-if="interviewDetails.resource.data" class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
            <h3 class="mb-2 text-p-base font-medium text-app-text">Interview Details</h3>
            <dl class="flex flex-col gap-1.5 text-p-sm">
              <div v-if="interviewDetails.resource.data.interview_round" class="flex gap-2">
                <dt class="font-medium text-app-text-muted">Interview Round</dt>
                <dd class="text-app-text">{{ interviewDetails.resource.data.interview_round }}</dd>
              </div>
              <div v-if="interviewDetails.resource.data.role" class="flex gap-2">
                <dt class="font-medium text-app-text-muted">Role</dt>
                <dd class="text-app-text">{{ interviewDetails.resource.data.role }}</dd>
              </div>
              <div v-if="interviewDetails.resource.data.client_name" class="flex gap-2">
                <dt class="font-medium text-app-text-muted">Client Name</dt>
                <dd class="text-app-text">{{ interviewDetails.resource.data.client_name }}</dd>
              </div>
            </dl>
          </div>

          <DocDetailView
            :doctype="doctype"
            :detail="detail"
            :fieldnames="['assign_to', 'status']"
            :field-link-queries="{ assign_to: { query: assignToQuery, filters: assignToFilters } }"
            :read-only-fields="locked ? ['assign_to', 'status'] : []"
          />

          <div class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
            <h3 class="mb-2 text-p-base font-medium text-app-text">Candidate Feedback</h3>
            <p v-if="detail.values.candidate_feedback" class="whitespace-pre-wrap text-p-sm text-app-text">{{ detail.values.candidate_feedback }}</p>
            <p v-else class="py-4 text-center text-p-sm text-app-text-muted">No Feedback Yet</p>
          </div>

          <ServiceResumePanel :customer="detail.hidden.customer" />
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
      <ActivityTimeline :doctype="doctype" :name="name" :types="['note']" show-composer empty-text="Nothing here yet - add the first note below." />
    </template>

    <template #tab-updates>
      <ActivityTimeline :doctype="doctype" :name="name" :types="['update']" empty-text="No updates yet." />
    </template>

    <template #tab-activity>
      <ActivityTimeline :doctype="doctype" :name="name" :types="['task', 'event']" allow-create empty-text="No tasks or events linked to this record yet." />
    </template>

    <template #tab-customer>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <CustomerContextPanel :customer="detail.hidden.customer" display-key="Interview Support" />
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
import { hasRole } from '@/utils/common/roles'
// Interview Support's detail page - same "service record" shape as
// Training/Technical Other Services, plus an Interview Round link (hidden
// once set, per the desk form) whose Interview Details panel is fetched
// from get_interview_details. See public/js/reusable.js's refresh() for
// the desk form this mirrors.
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import ServiceResumePanel from '@/components/detail/lead/ServiceResumePanel.vue'
import ForwardCandidateButton from '@/components/detail/actions/ForwardCandidateButton.vue'
import CustomerContextPanel from '@/components/detail/customer/CustomerContextPanel.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { useResource } from '@/composables/list/useResource'
import { autoTitleFromFile } from '@/utils/detail/documentTitle'

const route = useRoute()

const doctype = computed(() => 'Interview Support')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

const locked = computed(() => detail.values.status === 'Completed' && !hasRole('System Manager'))

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

const assignToQuery = 'verp_staffing.crm.api.helpers.get_assign_to_by_service'
const assignToFilters = computed(() => ({ service: 'Interview Support', customer: detail.hidden.customer }))

const interviewDetails = useResource({
  url: 'verp_staffing.technical.doctype.interview_support.interview_support.get_interview_details',
  notifyOnError: false,
})
watch(
  () => detail.values.interview_round,
  (round) => {
    if (round) interviewDetails.resource.submit({ interview_round: round })
  },
  { immediate: true },
)
</script>
