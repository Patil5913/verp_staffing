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
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="['department_name', 'head_of_department']" />
          <div v-if="!detail.meta.isLoading || detail.meta.resource.data" class="flex flex-col gap-6">
            <template v-for="table in detail.tables.value" :key="table.fieldname">
              <TableMultiSelectField
                v-if="TABLE_META[table.fieldname]"
                :table="table"
                :rows="detail.values[table.fieldname] || []"
                :disabled="!detail.canWrite.value"
                :query="TABLE_QUERIES[table.fieldname]"
                :description="TABLE_META[table.fieldname].description"
                @update:rows="(rows) => (detail.values[table.fieldname] = rows)"
              />
            </template>
          </div>
        </div>
      </div>
    </template>

    <template #tab-notes>
      <ActivityTimeline
        :doctype="doctype"
        :name="name"
        :types="['note', 'update']"
        show-composer
        empty-text="Nothing here yet - add the first note below."
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
// Department's own detail page - currently just the generic Details/Notes/
// Activity layout with the doctype pinned, kept separate from the generic
// DocDetailPage.vue on purpose so any Department-specific customization
// added later (e.g. its Hierarchy headline banner, or the role/service
// query filtering department.js does today) has a dedicated place to live
// instead of growing another doctype branch in the shared fallback. See
// router.js for how /Department/:name is routed here ahead of the generic
// /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import TableMultiSelectField from '@/components/detail/TableMultiSelectField.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()

const doctype = computed(() => 'Department')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'notes', label: 'Notes' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')

// Excludes a role/service already picked for this department, or any other
// department (role is a global one-department-only assignment) - see
// get_department_role_query / get_department_service_query in
// department.py, ported from the old desk department.js set_query calls.
const TABLE_META = {
  role: { description: 'Roles that belong to this department. A role can only be in one department.' },
  services: { description: 'Services this department offers.' },
}
const TABLE_QUERIES = {
  role: 'verp_staffing.settings.doctype.department.department.get_department_role_query',
  services: 'verp_staffing.settings.doctype.department.department.get_department_service_query',
}
</script>
