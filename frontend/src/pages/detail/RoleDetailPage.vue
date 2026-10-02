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
      >
        <AppButton
          v-if="!detail.isNew.value"
          variant="outline"
          icon="shield"
          @click="router.push({ name: 'PermissionManager', query: { role: name } })"
        >
          Manage Permissions
        </AppButton>
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <div v-for="group in DETAIL_GROUPS" :key="group.title" class="flex flex-col gap-2">
            <h2 class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">{{ group.title }}</h2>
            <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="group.fields" />
          </div>
        </div>
      </div>
    </template>

    <template #tab-permissions>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <RolePermissionsTab :role="name" :can-write="detail.canWrite.value" />
      </div>
    </template>

    <template #tab-users>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <RoleUsersTab :role="name" :can-write="detail.canWrite.value" />
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
// Role's detail page: a single curated field grid (no Notes/Activity -
// roles don't carry that kind of history) plus a shortcut into the Role
// Permissions Manager pre-selected for this role. See router.js for how
// /Role/:name is routed here ahead of the generic /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import RolePermissionsTab from '@/components/detail/role/RolePermissionsTab.vue'
import RoleUsersTab from '@/components/detail/role/RoleUsersTab.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'Role')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

const TABS = computed(() =>
  detail.isNew.value
    ? [{ key: 'details', label: 'Details' }]
    : [
        { key: 'details', label: 'Details' },
        { key: 'permissions', label: 'Permissions' },
        { key: 'users', label: 'Assigned Users' },
      ],
)
const tabs = TABS
const activeTab = ref('details')

const DETAIL_GROUPS = [
  { title: 'General', description: 'Name and status of the role.', fields: ['role_name', 'disabled', 'is_custom'] },
  { title: 'Access', description: 'How users with this role can sign in.', fields: ['desk_access', 'two_factor_auth'] },
  { title: 'Restrictions', description: 'Where this role lands and what it is limited to.', fields: ['home_page', 'restrict_to_domain'] },
]
</script>
