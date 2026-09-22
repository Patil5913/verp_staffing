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
          doctype="Cover Letter"
          :name="name"
          :customer="detail.values.customer"
          from-service-name="Cover Letter"
          @forwarded="detail.refresh"
        />
        <FieldUpdateActions :detail="detail" :doctype="doctype" :name="name" mode="service" />
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="DETAIL_FIELDS" :read-only-fields="locked ? ['status'] : []" />
      </div>
    </template>

    <template #tab-proof>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <ChildTableField
          v-if="proofTable"
          :table="proofTable"
          :rows="detail.values.proof_of_work || []"
          :disabled="!detail.canWrite.value || locked"
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
// Cover Letter's detail page: Details/Proof of Work/Notes/Activity — same
// shape as Resume/RUC/JDC, this app's other Customer-attached "service"
// doctypes. `customer` is hidden + set_only_once server-side and never
// reaches DETAIL_FIELDS. See router.js for how /Cover%20Letter/:name is
// routed here ahead of the generic /:doctype/:name.
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
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()

const doctype = computed(() => 'Cover Letter')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

// Same as Training/Interview Support/Technical Other Services: a Completed
// service record is frozen — status/proof of work can no longer change.
const locked = computed(() => detail.values.status === 'Completed')

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'proof', label: 'Proof of Work' },
  { key: 'notes', label: 'Notes' },
  { key: 'updates', label: 'Updates' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')

const DETAIL_FIELDS = ['assign_to', 'status']

const proofTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'proof_of_work'))
</script>
