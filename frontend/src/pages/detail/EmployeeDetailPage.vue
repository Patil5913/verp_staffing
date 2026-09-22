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
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <DocDetailView
          :doctype="doctype"
          :detail="detail"
          :fieldnames="PROFILE_FIELDS"
          :read-only-fields="userFieldReadOnly"
          :field-link-queries="userFieldLinkQueries"
        />
      </div>
    </template>

    <template #tab-assignments>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <ChildTableField
          v-if="assignmentsTable"
          :table="assignmentsTable"
          :rows="detail.values.employee_assignment_details_table || []"
          :disabled="!detail.canWrite.value"
          :link-queries="assignmentLinkQueries"
          :validate-row="validateAssignmentRow"
          :on-field-change="onAssignmentFieldChange"
          @update:rows="(rows) => (detail.values.employee_assignment_details_table = rows)"
        />
      </div>
    </template>

    <template #tab-linkedin>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
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
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
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
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call, Dialog } from 'frappe-ui'
import { isAdministrator, isSystemManager } from '@/utils/common/roles'
import AppButton from '@/components/ui/AppButton.vue'
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
// Linkedin/Target aren't relevant to every employee — Linkedin only for one
// assigned to the Lead department, Target only for Sales (per its own
// Employee Assignment Details rows, not the employee's single top-level
// department) — both tabs were showing for everyone.
const tabs = computed(() =>
  TABS.filter((t) => {
    if (t.key === 'linkedin') return hasLeadDepartment.value
    if (t.key === 'target') return hasSalesDepartment.value
    return true
  }),
)
const activeTab = ref('profile')

const PROFILE_FIELDS = ['employee_name', 'user', 'enabled']
// Once the Employee exists, the linked User can't be changed out from under
// it — matches employee.js leaving `user` unset_only_once-style read-only
// after creation.
const userFieldReadOnly = computed(() => (detail.isNew.value ? [] : ['user']))
// Only offer a User that isn't already the User of some other Employee —
// enforced server-side too (Employee.validate), this is just so a duplicate
// is never picked in the first place.
const userFieldLinkQueries = {
  user: { query: 'verp_staffing.employee.doctype.employee.employee.get_users_not_linked_to_employee' },
}

// employee.js's user(frm) handler: picking a User fills Employee Full Name
// from it. Only while still creating — once saved, `user` is read-only
// above, so this would never fire again anyway.
watch(
  () => detail.values.user,
  async (user) => {
    if (!user || !detail.isNew.value) return
    const fullName = await call('frappe.client.get_value', {
      doctype: 'User',
      filters: user,
      fieldname: 'full_name',
    }).catch(() => null)
    if (fullName?.full_name) detail.values.employee_name = fullName.full_name
  },
)
// start_date sits right next to target/target_based_on in the doctype's own
// field order — it's the Target's start date, not a general employee start
// date, so it belongs on the Target tab, not Profile.
const TARGET_FIELDS = ['start_date', 'target', 'target_based_on']

function hasDepartmentAssignment(department) {
  return (detail.values.employee_assignment_details_table || []).some((row) => row.department === department)
}
const hasSalesDepartment = computed(() => hasDepartmentAssignment('Sales'))
const hasLeadDepartment = computed(() => hasDepartmentAssignment('Lead'))
function openRevenueReport() {
  router.push({ path: '/report/Revenue%20Of%20Employee', query: { employee: name.value } })
}

const assignmentsTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'employee_assignment_details_table'))
const linkedinTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'linkedin_credentials'))

// designation options come from the row's own Department's Hierarchy (same
// API as ERP Configuration's Permission Request Configuration — see
// hierarchy.py), minus designations already used by sibling rows.
// assigned_to options come from employees holding the *parent* role of the
// row's own designation (who that designation reports to) in the same
// hierarchy — get_assign_to_query resolves both steps server-side.
function assignmentLinkQueries(draft, rows, editingIndex) {
  return {
    designation: {
      query: 'verp_staffing.settings.doctype.hierarchy.hierarchy.get_department_hierarchy_roles_query',
      filters: {
        department: draft.department,
        exclude: rows
          .filter((_, i) => i !== editingIndex)
          .map((r) => r.designation)
          .filter(Boolean),
      },
    },
    assigned_to: {
      query: 'verp_staffing.settings.doctype.hierarchy.hierarchy.get_assign_to_query',
      filters: { department: draft.department, designation: draft.designation, current_emp: name.value },
    },
  }
}

// Department and Designation each narrow what the fields below them can be
// — changing either invalidates whatever was already picked further down
// the row, the same as the desk form clearing dependent fields on change.
function onAssignmentFieldChange(fieldname, value, draft) {
  if (fieldname === 'department') return { designation: '', assigned_to: '' }
  if (fieldname === 'designation') return { assigned_to: '' }
  return null
}

// Ported from employee.js's validate(frm) — written but its frappe.throw was
// left commented out there, so it never actually ran. Assigned To is
// required unless the row's designation is a top-level (root) role in its
// department's hierarchy.
async function validateAssignmentRow(draft) {
  if (!draft.department || !draft.designation || draft.assigned_to) return null
  const isTop = await call('verp_staffing.settings.doctype.hierarchy.hierarchy.is_role_top_level', {
    department: draft.department,
    role: draft.designation,
  })
  return isTop ? null : `Assigned To is required for designation ${draft.designation} in department ${draft.department}.`
}
</script>
