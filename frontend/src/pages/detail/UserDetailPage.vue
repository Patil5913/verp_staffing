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
        <AppButton variant="outline" icon="mail" :loading="sendingResetEmail" @click="onSendResetEmail">
          Send Reset Password Email
        </AppButton>
        <AppButton
          v-if="name !== 'Administrator'"
          :variant="detail.values.enabled ? 'danger' : 'outline'"
          :icon="detail.values.enabled ? 'user-x' : 'user-check'"
          :loading="togglingEnabled"
          @click="onToggleEnabled"
        >
          {{ detail.values.enabled ? 'Disable User' : 'Enable User' }}
        </AppButton>
      </RecordActionBar>
    </template>

    <template #tab-profile>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="PROFILE_FIELDS" />
      </div>
    </template>

    <template #tab-roles>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <UserRolesTab :user="name" :can-write="detail.canWrite.value" />
      </div>
    </template>

    <template #tab-email>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="EMAIL_FIELDS" />
          <ChildTableField
            v-if="userEmailsTable"
            :table="userEmailsTable"
            :rows="detail.values.user_emails || []"
            :disabled="!detail.canWrite.value"
            @update:rows="(rows) => (detail.values.user_emails = rows)"
          />
        </div>
      </div>
    </template>

    <template #tab-general>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="GENERAL_FIELDS" />
          <UserChangePassword :user="name" />
        </div>
      </div>
    </template>

    <template #tab-security>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="SECURITY_FIELDS" />
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

  <Dialog
    v-model="showCreateEmployeePrompt"
    :options="{
      title: 'Create an Employee for this user?',
      message: `${createdUserName} isn't linked to an Employee record yet — most of the app treats a user as staff through their Employee, not the User doctype directly.`,
      icon: { name: 'user-plus' },
    }"
  >
    <template #actions>
      <div class="flex w-full items-center justify-between gap-2">
        <AppButton variant="outline" @click="goToEmployeeList">View Employee List</AppButton>
        <AppButton variant="primary" icon="user-plus" @click="goToCreateEmployee">Create Employee</AppButton>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
// User's detail page: curated Profile/Roles/Email/General/Security tabs
// instead of the generic Details/Notes/Activity — User doesn't need an
// activity timeline, and its fields split naturally into desk's own User
// form sections. See router.js for how /User/:name is routed here ahead of
// the generic /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog, call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import UserRolesTab from '@/components/detail/user/UserRolesTab.vue'
import UserChangePassword from '@/components/detail/user/UserChangePassword.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'User')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave: baseSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

// warn_if_employee_missing (overrides/user.py) flags a just-created User
// that has no linked Employee yet — check once, right after a create,
// rather than on every save.
const showCreateEmployeePrompt = ref(false)
const createdUserName = ref('')

async function onSave() {
  const wasNew = detail.isNew.value
  const ok = await baseSave()
  if (ok && wasNew) {
    createdUserName.value = detail.meta.resource.data?.name || name.value
    const missing = await call('verp_staffing.overrides.user.check_employee_missing', {
      user: createdUserName.value,
    })
    if (missing) showCreateEmployeePrompt.value = true
  }
  return ok
}

function goToEmployeeList() {
  showCreateEmployeePrompt.value = false
  router.push({ name: 'DocList', params: { doctype: 'Employee' } })
}

function goToCreateEmployee() {
  showCreateEmployeePrompt.value = false
  router.push(`/Employee/new?user=${encodeURIComponent(createdUserName.value)}`)
}

const TABS = [
  { key: 'profile', label: 'Profile' },
  { key: 'roles', label: 'Roles & Permissions' },
  { key: 'email', label: 'Email' },
  { key: 'general', label: 'General' },
  { key: 'security', label: 'Security' },
]
const tabs = computed(() => TABS)
const activeTab = ref('profile')

const PROFILE_FIELDS = ['full_name', 'first_name', 'last_name', 'username', 'email']
const EMAIL_FIELDS = ['thread_notify', 'send_me_a_copy', 'allowed_in_mentions']
const GENERAL_FIELDS = ['language', 'time_zone', 'desk_theme']
const SECURITY_FIELDS = ['simultaneous_sessions', 'restrict_ip', 'login_after', 'login_before']

// User's linked email accounts (the "user_emails" child table) — shown as
// its own reusable table on the Email tab instead of the read-only
// email_signature field.
const userEmailsTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'user_emails'))

const toggleEnabled = useResource({
  url: 'verp_staffing.utils.user_view.set_user_enabled',
  // Reload rather than patch `detail.values.enabled` directly — a direct
  // patch would drift from the load-time snapshot isDirty diffs against,
  // falsely flagging the page as having unsaved changes.
  onSuccess: () => detail.refresh(),
})
const togglingEnabled = computed(() => toggleEnabled.isLoading)

function onToggleEnabled() {
  toggleEnabled.resource.submit({ user: name.value, enabled: detail.values.enabled ? 0 : 1 })
}

const resetEmail = useResource({
  url: 'frappe.core.doctype.user.user.reset_password',
})
const sendingResetEmail = computed(() => resetEmail.isLoading)

async function onSendResetEmail() {
  await resetEmail.resource.submit({ user: name.value })
  notify.success('If this email is registered, reset instructions have been sent.')
}
</script>
