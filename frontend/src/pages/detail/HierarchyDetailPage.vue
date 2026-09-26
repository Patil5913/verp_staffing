<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" :detail="detail" @back="goBack">
    <template #actions>
      <RecordActionBar
        show-save
        :save-dirty="isDirty"
        :save-loading="saving"
        :show-delete="!detail.isNew.value && detail.canDelete.value"
        :delete-loading="deleting"
        @save="onSave"
        @delete="showDeleteDialog = true"
      />
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <div class="rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <AppLinkField
              label="Department"
              doctype="Department"
              :filters="departmentFilters"
              :disabled="!detail.isNew.value"
              v-model="detail.values.department"
            />
          </div>

          <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <h3 class="text-p-base font-medium text-app-text">Role Hierarchy</h3>

            <p v-if="!detail.values.department" class="text-p-sm text-app-text-muted">
              Select a department above to define its role hierarchy.
            </p>
            <HierarchyTreeEditor v-else v-model="rows" :roles="departmentRoles" />
          </div>

          <div v-if="departmentRoles.length" class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <h3 class="text-p-base font-medium text-app-text">Auto Assignment Rule</h3>
            <p class="text-p-sm text-app-text-muted">
              Select one role to enable automatic assignment. Only users with this role will be
              considered for auto and manual assignment.
            </p>
            <div class="max-w-xs">
              <FieldControl :field="autoAssignField" v-model="autoAssignRole" />
            </div>
          </div>

          <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm">
            <h3 class="text-p-base font-medium text-app-text">Hierarchy Diagram</h3>
            <HierarchyDiagram :data="parsedRoleHierarchy" />
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

  <Dialog v-model="showUnusedRolesDialog" :options="{ title: 'Unused Department Roles', size: 'lg' }">
    <template #body-content>
      <p class="text-p-sm text-app-text">
        The following Department Roles are not used anywhere in the Hierarchy:
      </p>
      <ul class="my-3 list-disc pl-5 text-p-sm text-app-text">
        <li v-for="role in pendingUnusedRoles" :key="role">{{ role }}</li>
      </ul>
      <p class="text-p-sm text-app-text">
        Do you want to remove them from the Department, or continue without removing them?
      </p>
    </template>
    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <AppButton variant="outline" @click="resolveUnusedRolesDialog('continue')">
          Continue Without Removing
        </AppButton>
        <AppButton variant="danger" @click="resolveUnusedRolesDialog('remove')">Remove From Department</AppButton>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
// Hierarchy's own detail page - ports the old desk hierarchy.js widget
// (role_table_html + hierarchy_diagram + auto_assign_config) onto this
// app's reusable components (AppLinkField, FieldControl, AppButton,
// Dialog, HierarchyDiagram) instead of hand-built jQuery/HTML, but keeps
// the same behavior: role_hierarchy_json/auto_assign_config are hidden
// storage fields (excluded from the generic get_doc_meta payload, same as
// any other hidden field), so they're fetched once via the same generic
// frappe.client.get the old widget itself used, and written back through
// the generic save_doc_fields - no new backend endpoints needed. The
// unused-department-role precheck/confirm dance and every structural
// validation (self-loops, cycles, duplicate children, roles must belong to
// the department, ...) still run in hierarchy.py exactly as before; this
// page only re-implements the old client-side layout/diagram so errors
// surface before a round-trip, not the validation itself.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import HierarchyTreeEditor from '@/components/detail/hierarchy/HierarchyTreeEditor.vue'
import HierarchyDiagram from '@/components/detail/hierarchy/HierarchyDiagram.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDocDetail } from '@/composables/detail/useDocDetail'
import { useResource } from '@/composables/list/useResource'
import { useUnsavedChangesGuard } from '@/composables/common/useUnsavedChangesGuard'
import { useSaveShortcut } from '@/composables/common/useSaveShortcut'
import { notify } from '@/utils/common/notify'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'Hierarchy')
const name = computed(() => route.params.name)

const detail = useDocDetail(doctype, name)

const recordTitle = computed(() => {
  if (detail.isNew.value) return 'New Hierarchy'
  return detail.values.department || name.value
})

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'notes', label: 'Notes' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')

// ── Role hierarchy rows (role_table_html / role_hierarchy_json) ──────────
const rows = ref([{ parent_role: '', child_roles: [] }])
const rowsSnapshot = ref('')

function cleanRows(list) {
  return list.filter((r) => r.parent_role).map((r) => ({ parent_role: r.parent_role, child_roles: [...r.child_roles] }))
}
const parsedRoleHierarchy = computed(() => cleanRows(rows.value))
const roleHierarchyJson = computed(() => JSON.stringify(parsedRoleHierarchy.value))


// ── Auto assignment (auto_assign_config) ──────────────────────────────────
const autoAssignRole = ref('')
const autoAssignSnapshot = ref('')
const autoAssignConfigJson = computed(() => (autoAssignRole.value ? JSON.stringify({ role: autoAssignRole.value }) : ''))
const autoAssignField = computed(() => ({
  fieldname: 'auto_assign_role',
  label: 'Role for Auto Assignment',
  fieldtype: 'Select',
  options: departmentRoles.value.join('\n'),
}))

// ── Department roles / already-used departments ───────────────────────────
const departmentRoles = ref([])
const usedDepartments = ref([])
const departmentFilters = computed(() => ({ name: ['not in', usedDepartments.value] }))

const deptResource = useResource({ url: 'frappe.client.get', notifyOnError: false })
const usedDeptResource = useResource({ url: 'frappe.client.get_list', notifyOnError: false })
const existingResource = useResource({ url: 'frappe.client.get', notifyOnError: false })

async function loadDepartmentRoles(deptName) {
  if (!deptName) {
    departmentRoles.value = []
    return
  }
  const doc = await deptResource.resource.submit({ doctype: 'Department', name: deptName })
  const roles = (doc?.role || []).map((r) => r.role).filter(Boolean)
  departmentRoles.value = roles
  if (!roles.length) {
    notify.error(
      `Department "${deptName}" has no roles assigned. Configure roles in the Department before defining hierarchy relationships.`,
    )
  }
}

async function loadUsedDepartments() {
  const list = await usedDeptResource.resource.submit({
    doctype: 'Hierarchy',
    fields: ['department'],
    filters: detail.isNew.value ? {} : { name: ['!=', name.value] },
    limit_page_length: 1000,
  })
  usedDepartments.value = (list || []).map((d) => d.department).filter(Boolean)
}
loadUsedDepartments()

watch(
  () => detail.values.department,
  (dept) => loadDepartmentRoles(dept),
)

// Clear an auto-assign role that no longer belongs to the (possibly just
// changed) department - mirrors hierarchy.js's department() handler.
watch(departmentRoles, (roles) => {
  if (autoAssignRole.value && !roles.includes(autoAssignRole.value)) autoAssignRole.value = ''
})

// Seed rows/auto-assign/snapshots once the record loads. role_hierarchy_json
// and auto_assign_config are hidden fields, so get_doc_meta never returns
// them - fetched once here via the same generic frappe.client.get the old
// widget's own load_department_roles() used.
watch(
  () => detail.meta.resource.data,
  async (data) => {
    if (!data) return
    if (detail.isNew.value) {
      rows.value = [{ parent_role: '', child_roles: [] }]
      rowsSnapshot.value = roleHierarchyJson.value
      autoAssignRole.value = ''
      autoAssignSnapshot.value = ''
      return
    }
    const doc = await existingResource.resource.submit({ doctype: 'Hierarchy', name: name.value })
    if (!doc) return

    let parsed = []
    try {
      parsed = doc.role_hierarchy_json ? JSON.parse(doc.role_hierarchy_json) : []
    } catch {
      parsed = []
    }
    rows.value = parsed.length
      ? parsed.map((r) => ({ parent_role: r.parent_role, child_roles: [...(r.child_roles || [])] }))
      : [{ parent_role: '', child_roles: [] }]
    rowsSnapshot.value = JSON.stringify(cleanRows(rows.value))

    let autoCfg = {}
    try {
      autoCfg = doc.auto_assign_config ? JSON.parse(doc.auto_assign_config) : {}
    } catch {
      autoCfg = {}
    }
    autoAssignRole.value = autoCfg.role || ''
    autoAssignSnapshot.value = autoAssignConfigJson.value
  },
  { immediate: true },
)

const isDirty = computed(
  () =>
    detail.isDirty.value ||
    roleHierarchyJson.value !== rowsSnapshot.value ||
    autoAssignConfigJson.value !== autoAssignSnapshot.value,
)

// ── Unused-department-role confirmation dialog ─────────────────────────────
const showUnusedRolesDialog = ref(false)
const pendingUnusedRoles = ref([])
let pendingUnusedRolesResolve = null

function askUnusedRolesConfirmation(unusedRoles) {
  pendingUnusedRoles.value = unusedRoles
  showUnusedRolesDialog.value = true
  return new Promise((resolve) => {
    pendingUnusedRolesResolve = resolve
  })
}
function resolveUnusedRolesDialog(action) {
  showUnusedRolesDialog.value = false
  pendingUnusedRolesResolve?.(action)
  pendingUnusedRolesResolve = null
}
watch(showUnusedRolesDialog, (open) => {
  if (!open && pendingUnusedRolesResolve) {
    pendingUnusedRolesResolve(null)
    pendingUnusedRolesResolve = null
  }
})

// ── Save ────────────────────────────────────────────────────────────────
const precheckResource = useResource({
  url: 'verp_staffing.settings.doctype.hierarchy.hierarchy.precheck_department_role_consistency',
})
const confirmResource = useResource({
  url: 'verp_staffing.settings.doctype.hierarchy.hierarchy.process_hierarchy_confirmation',
})
const saving = ref(false)

async function onSave() {
  if (!parsedRoleHierarchy.value.length) {
    notify.error('Please add at least one role hierarchy row.')
    return false
  }
  if (!autoAssignConfigJson.value) {
    notify.error('Please select a role for Auto Assignment.')
    return false
  }

  saving.value = true
  try {
    const isNew = detail.isNew.value
    const hierarchyName = isNew ? null : name.value

    const precheck = await precheckResource.resource.submit({
      doc: {
        doctype: 'Hierarchy',
        name: hierarchyName,
        department: detail.values.department,
        role_hierarchy_json: roleHierarchyJson.value,
      },
    })
    if (!precheck) return false

    let extra = {}
    if (precheck.requires_confirmation) {
      const action = await askUnusedRolesConfirmation(precheck.unused_roles)
      if (!action) return false

      const confirmed = await confirmResource.resource.submit({
        hierarchy_name: hierarchyName,
        token: precheck.token,
        action,
      })
      if (!confirmed) return false
      extra = { __hierarchy_validation_token: precheck.token }
    }

    const ok = await detail.submit({
      department: detail.values.department,
      role_hierarchy_json: roleHierarchyJson.value,
      auto_assign_config: autoAssignConfigJson.value,
      ...extra,
    })
    if (!ok) return false

    rowsSnapshot.value = roleHierarchyJson.value
    autoAssignSnapshot.value = autoAssignConfigJson.value

    if (isNew) {
      const newName = detail.meta.resource.data?.name
      bypassNext()
      router.replace(`/${encodeURIComponent(doctype.value)}/${encodeURIComponent(newName)}`)
    }
    return true
  } finally {
    saving.value = false
  }
}

const { bypassNext } = useUnsavedChangesGuard(isDirty, onSave)
useSaveShortcut(isDirty, onSave)

function goBack() {
  router.push({ name: 'DocList', params: { doctype: doctype.value } })
}

const showDeleteDialog = ref(false)
const deleteResource = useResource({ url: 'verp_staffing.utils.list_view.delete_docs' })
const deleting = computed(() => deleteResource.isLoading)

async function onDelete() {
  const result = await deleteResource.resource.submit({ doctype: doctype.value, names: [name.value] })
  if (!result) return
  if (result.failed.length) {
    notify.error(result.failed[0].error)
    return
  }
  showDeleteDialog.value = false
  notify.success('Deleted.')
  bypassNext()
  router.push({ name: 'DocList', params: { doctype: doctype.value } })
}
</script>
