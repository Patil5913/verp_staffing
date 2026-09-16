<template>
  <div class="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8">
    <h1 class="text-2xl font-semibold text-app-text">Role Permissions Manager</h1>

    <StateBanner
      v-if="options.hasError"
      icon="alert-triangle"
      title="Couldn't load roles/doctypes"
      :description="options.errorMessage"
    />

    <div class="flex flex-wrap items-end gap-3 rounded-lg border border-app-border bg-app-panel p-4">
      <div class="w-64">
        <Autocomplete :value="doctype" :options="doctypeOptions" placeholder="DocType" @change="(o) => (doctype = o.value)" />
      </div>
      <div class="w-64">
        <Autocomplete :value="role" :options="roleOptions" placeholder="Role" @change="(o) => (role = o.value)" />
      </div>
      <Button variant="outline" icon="plus" :disabled="!doctype || !role" @click="onAddLevel">
        Add Permission Level
      </Button>
      <Button variant="outline" theme="red" :disabled="!doctype" :loading="resetting.loading" @click="onReset">
        Reset to Defaults
      </Button>
    </div>

    <StateBanner
      v-if="!doctype || !role"
      icon="shield"
      title="Pick a DocType and Role"
      description="Select both above to view and edit their permissions."
    />
    <StateBanner
      v-else-if="perms.hasError"
      icon="alert-triangle"
      title="Couldn't load permissions"
      :description="perms.errorMessage"
    />
    <div v-else-if="perms.isLoading && !perms.resource.data" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>

    <div v-else-if="perms.resource.data" class="overflow-auto rounded-lg border border-app-border bg-app-panel">
      <table class="w-full text-left text-p-sm">
        <thead class="border-b border-app-border text-app-text-muted">
          <tr>
            <th class="px-3 py-2 font-medium">Level</th>
            <th class="px-3 py-2 font-medium">Only if creator</th>
            <th v-for="pt in PTYPES" :key="pt" class="px-3 py-2 font-medium capitalize">{{ pt }}</th>
            <th class="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in perms.resource.data" :key="row.permlevel" class="border-b border-app-border last:border-0">
            <td class="px-3 py-2 font-medium text-app-text">{{ row.permlevel }}</td>
            <td class="px-3 py-2">
              <input type="checkbox" :checked="!!row.if_owner" @change="onToggle(row, 'if_owner', $event.target.checked)" />
            </td>
            <td v-for="pt in PTYPES" :key="pt" class="px-3 py-2">
              <input type="checkbox" :checked="!!row[pt]" @change="onToggle(row, pt, $event.target.checked)" />
            </td>
            <td class="px-3 py-2">
              <Button variant="ghost" icon="x" @click="onRemove(row)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Autocomplete, Button, LoadingIndicator } from 'frappe-ui'
import { useResource } from '@/composables/useResource'
import { notify } from '@/utils/notify'
import StateBanner from '@/components/StateBanner.vue'

const PTYPES = [
  'read', 'write', 'create', 'delete', 'submit', 'cancel', 'amend',
  'report', 'export', 'import', 'share', 'print', 'email', 'select',
]

const doctype = ref('')
const role = ref('')

const options = useResource({
  url: 'frappe.core.page.permission_manager.permission_manager.get_roles_and_doctypes',
  auto: true,
})
const doctypeOptions = computed(() => options.resource.data?.doctypes || [])
const roleOptions = computed(() => options.resource.data?.roles || [])

const perms = useResource({
  url: 'frappe.core.page.permission_manager.permission_manager.get_permissions',
  makeParams: () => ({ doctype: doctype.value, role: role.value }),
})

function reload() {
  if (doctype.value && role.value) perms.resource.submit({ doctype: doctype.value, role: role.value })
}

// Refetch whenever both selectors have a value.
watch([doctype, role], reload)

const toggling = useResource({
  url: 'frappe.core.page.permission_manager.permission_manager.update',
})
function onToggle(row, ptype, checked) {
  row[ptype] = checked ? 1 : 0
  toggling.resource.submit({
    doctype: doctype.value,
    role: role.value,
    permlevel: row.permlevel,
    ptype,
    value: checked ? 1 : 0,
    if_owner: row.if_owner ? 1 : 0,
  })
}

const adding = useResource({
  url: 'frappe.core.page.permission_manager.permission_manager.add',
  onSuccess: reload,
})
function onAddLevel() {
  const levels = (perms.resource.data || []).map((r) => r.permlevel)
  const nextLevel = levels.length ? Math.max(...levels) + 1 : 0
  adding.resource.submit({ parent: doctype.value, role: role.value, permlevel: nextLevel })
}

const removing = useResource({
  url: 'frappe.core.page.permission_manager.permission_manager.remove',
  onSuccess: reload,
})
function onRemove(row) {
  removing.resource.submit({
    doctype: doctype.value,
    role: role.value,
    permlevel: row.permlevel,
    if_owner: row.if_owner ? 1 : 0,
  })
}

const resetting = useResource({
  url: 'frappe.core.page.permission_manager.permission_manager.reset',
  onSuccess() {
    notify.success(`Permissions for ${doctype.value} reset to defaults.`)
    reload()
  },
})
function onReset() {
  resetting.resource.submit({ doctype: doctype.value })
}
</script>
