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
          doctype="Technical Other Services"
          :name="name"
          :customer="detail.hidden.customer"
          :from-service-name="detail.values.service || 'Technical Other Services'"
          @forwarded="detail.refresh"
        />
        <FieldUpdateActions :detail="detail" :doctype="doctype" :name="name" mode="service" />
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <div class="flex flex-col gap-1.5">
            <label class="text-p-sm font-medium text-app-text-muted">Customer</label>
            <AppLinkField doctype="Customer" v-model="detail.hidden.customer" :disabled="!detail.canWrite.value || !detail.isNew.value" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-p-sm font-medium text-app-text-muted">Service</label>
            <AppLinkField doctype="Item" v-model="detail.values.service" :disabled="!detail.canWrite.value || !detail.isNew.value" :filters="{ is_service: 1 }" />
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="text-p-sm font-medium text-app-text-muted">Assign To</label>
            <AppLinkField
              doctype="Employee"
              v-model="detail.values.assign_to"
              :disabled="!detail.canWrite.value || locked"
              :query="assignToQuery"
              :filters="{ department: 'Technical' }"
            />
          </div>
          <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="['status']" :read-only-fields="locked ? ['status'] : []" />
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
        <CustomerContextPanel :customer="detail.hidden.customer" display-key="Technical Other Services" />
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
// Technical Other Services' detail page - same "service record" shape as
// Training/Interview Support, but for an arbitrary Item (service="..."):
// Customer + Service are picked once at creation (desk form's
// set_only_once) and assign_to is filtered to the Technical department's
// employees rather than by service name. See public/js/reusable.js's
// refresh() for the desk form this mirrors.
import { computed, ref } from 'vue'
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
import { autoTitleFromFile } from '@/utils/detail/documentTitle'

const route = useRoute()

const doctype = computed(() => 'Technical Other Services')
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

const assignToQuery = 'verp_staffing.crm.api.helpers.get_subordinate_employees'
</script>
