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
        <FieldUpdateActions :detail="detail" :doctype="doctype" :name="name" mode="service" />
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="DETAIL_FIELDS" />
      </div>
    </template>

    <template #tab-attachments>
      <div class="h-full overflow-y-auto px-6 py-4">
        <ChildTableField
          v-if="resumeTable"
          :table="resumeTable"
          :rows="detail.values.resume_table || []"
          :disabled="!detail.canWrite.value"
          @update:rows="(rows) => (detail.values.resume_table = rows)"
        />
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
// Resume's detail page: Details/Attachments/Notes/Activity instead of the
// generic Details/Notes/Activity — the resume attachment(s) get their own
// tab (child table "resume_table") instead of being stacked under the
// field grid. `customer` and `owner` aren't editable here: `customer` is
// hidden + set_only_once on the doctype (the server already drops hidden
// fields from its meta, so it never reaches DETAIL_FIELDS), and `status`
// flips to "Completed" automatically once a resume attachment lands — see
// resume.py's handle_resume_status. See router.js for how /Resume/:name is
// routed here ahead of the generic /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()

const doctype = computed(() => 'Resume')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'attachments', label: 'Attachments' },
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')

const DETAIL_FIELDS = ['assign_to', 'status']

const resumeTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'resume_table'))
</script>
