<template>
  <div class="flex flex-col gap-2">
    <div class="overflow-x-auto rounded-lg border border-app-border">
      <table class="w-full border-collapse">
        <thead>
          <tr class="bg-app-panel-2 text-left text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
            <th class="h-9 w-12 border-b border-app-border px-3">#</th>
            <th class="h-9 border-b border-app-border px-3">Department</th>
            <th class="h-9 border-b border-app-border px-3">Role</th>
            <th class="h-9 w-12 border-b border-app-border" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="idx" class="align-top">
            <td class="border-b border-app-border px-3 py-4 text-p-sm text-app-text-muted">{{ idx + 1 }}</td>
            <td class="w-1/2 border-b border-app-border p-2">
              <AppLinkField
                doctype="Department"
                placeholder="Select department"
                :disabled="disabled"
                :model-value="row.department"
                @update:model-value="(v) => setDepartment(idx, v)"
              />
            </td>
            <td class="border-b border-app-border p-2">
              <AppLinkField
                :key="row.department"
                doctype="Role"
                placeholder="Select role"
                :disabled="disabled || !row.department"
                :query="ROLE_QUERY"
                :filters="roleFilters(idx)"
                :hide-add-new="true"
                :model-value="row.role"
                @update:model-value="(v) => setRole(idx, v)"
              />
            </td>
            <td class="border-b border-app-border p-2 text-right">
              <AppButton v-if="!disabled" variant="ghost" icon="trash-2" @click="removeRow(idx)" />
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="4" class="p-6 text-center text-p-sm text-app-text-muted">
              No permission requests configured yet - use Add Row.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!disabled">
      <AppButton variant="outline" icon="plus" @click="addRow">Add Row</AppButton>
    </div>
  </div>
</template>

<script setup>
import AppButton from '@/components/ui/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'

// Inline-editable Permission Request Configuration rows ({department, role}).
// Role options come from the row's own Department's Hierarchy - the same
// query Employee's Assignment Details table uses - minus roles already
// picked in other rows of that department.
const ROLE_QUERY = 'verp_staffing.settings.doctype.hierarchy.hierarchy.get_department_hierarchy_roles_query'

const rows = defineModel({ type: Array, default: () => [] })
defineProps({ disabled: { type: Boolean, default: false } })

function update(idx, patch) {
  rows.value = rows.value.map((r, i) => (i === idx ? { ...r, ...patch } : r))
}
function setDepartment(idx, department) {
  update(idx, { department, role: '' })
}
function setRole(idx, role) {
  update(idx, { role })
}
function addRow() {
  rows.value = [...rows.value, { department: '', role: '' }]
}
function removeRow(idx) {
  rows.value = rows.value.filter((_, i) => i !== idx)
}
function roleFilters(idx) {
  const dept = rows.value[idx].department
  return {
    department: dept,
    exclude: rows.value.filter((r, i) => i !== idx && r.department === dept).map((r) => r.role).filter(Boolean),
  }
}
</script>
