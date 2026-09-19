<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" @back="goBack">
    <template #actions>
      <RecordActionBar
        :show-save="detail.canWrite.value"
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="!detail.isNew.value && detail.canDelete.value && !detail.locked.value"
        :delete-loading="deleting"
        @save="onSave"
        @delete="showDeleteDialog = true"
      >
        <AppButton v-if="hasSalesDepartment && !detail.isNew.value" variant="outline" icon="bar-chart-3" @click="openRevenueReport">Revenue Report</AppButton>
      </RecordActionBar>
    </template>

    <template #tab-profile>
      <div class="h-full overflow-y-auto px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="PROFILE_FIELDS" />
      </div>
    </template>

    <template #tab-assignments>
      <div class="h-full overflow-y-auto px-6 py-4">
        <ChildTableField
          v-if="assignmentsTable"
          :table="assignmentsTable"
          :rows="detail.values.employee_assignment_details_table || []"
          :disabled="!detail.canWrite.value"
          @update:rows="(rows) => (detail.values.employee_assignment_details_table = rows)"
        />
      </div>
    </template>

    <template #tab-linkedin>
      <div class="h-full overflow-y-auto px-6 py-4">
        <ChildTableField
          v-if="linkedinTable"
          :table="linkedinTable"
          :rows="detail.values.linkedin_credentials || []"
          :disabled="!detail.canWrite.value"
          @update:rows="(rows) => (detail.values.linkedin_credentials = rows)"
        />
      </div>
    </template>

    <template #tab-target>
      <div class="h-full overflow-y-auto px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="TARGET_FIELDS" />
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
// Employee's detail page: curated Profile/Assignments/LinkedIn/Target tabs
// instead of the generic Details/Notes/Activity — Employee's two child
// tables (assignment details, LinkedIn credentials) each get their own tab
// rather than being stacked under one Details grid. See router.js for how
// /Employee/:name is routed here ahead of the generic /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, Dialog } from 'frappe-ui'
import { isAdministrator, isSystemManager } from '@/utils/common/roles'
import AppButton from '@/components/common/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'Employee')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

// employee.js's apply_employee_read_only_restriction: outside the HR
// department (Administrator and System Manager excepted) the whole form is
// read-only. Locked until the server has said which departments the user is
// in, so it never flashes editable.
if (!isAdministrator() && !isSystemManager()) {
  detail.locked.value = true
  call('verp_staffing.employee.doctype.employee.employee.get_user_departments')
    .then((departments) => {
      detail.locked.value = !(departments || []).some((d) => (d || '').toLowerCase() === 'hr')
    })
    .catch(() => {})
}

const TABS = [
  { key: 'profile', label: 'Profile' },
  { key: 'assignments', label: 'Assignments' },
  { key: 'linkedin', label: 'LinkedIn' },
  { key: 'target', label: 'Target' },
]
const tabs = computed(() => TABS)
const activeTab = ref('profile')

const PROFILE_FIELDS = ['employee_name', 'user', 'enabled', 'start_date']
const TARGET_FIELDS = ['target', 'target_based_on']

// employee.js: employees assigned to Sales get a shortcut to their own
// Revenue Of Employee report.
const hasSalesDepartment = computed(() => (detail.values.employee_assignment_details_table || []).some((row) => row.department === 'Sales'))
function openRevenueReport() {
  router.push({ path: '/report/Revenue%20Of%20Employee', query: { employee: name.value } })
}

const assignmentsTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'employee_assignment_details_table'))
const linkedinTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'linkedin_credentials'))
</script>
