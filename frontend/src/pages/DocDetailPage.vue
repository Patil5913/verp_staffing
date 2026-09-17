<template>
  <DetailPageLayout
    :title="recordTitle"
    :tabs="tabs"
    v-model:active-tab="activeTab"
    @back="goBack"
  >
    <template #actions>
      <RecordActionBar
        :show-save="!isLead || !leadLocked"
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="detail.canDelete.value"
        :delete-loading="deleting"
        @save="onSave"
        @delete="showDeleteDialog = true"
      >
        <AppButton
          v-if="isLead && !leadLocked"
          variant="outline"
          icon="target"
          @click="leadExtrasRef?.showCreateOpportunity()"
        >
          Create Opportunity
        </AppButton>
        <AppButton v-if="isUser" variant="outline" icon="mail" :loading="sendingResetEmail" @click="onSendResetEmail">
          Send Reset Password Email
        </AppButton>
        <AppButton
          v-if="isUser && name !== 'Administrator'"
          :variant="detail.values.enabled ? 'danger' : 'outline'"
          :icon="detail.values.enabled ? 'user-x' : 'user-check'"
          :loading="togglingEnabled"
          @click="onToggleEnabled"
        >
          {{ detail.values.enabled ? 'Disable User' : 'Enable User' }}
        </AppButton>
      </RecordActionBar>
    </template>

    <template v-if="isUser" #tab-profile>
      <div class="h-full overflow-y-auto px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="USER_PROFILE_FIELDS" />
      </div>
    </template>

    <template v-if="isUser" #tab-roles>
      <div class="h-full overflow-y-auto px-6 py-4">
        <UserRolesTab :user="name" :can-write="detail.canWrite.value" />
      </div>
    </template>

    <template v-if="isUser" #tab-email>
      <div class="h-full overflow-y-auto px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="USER_EMAIL_FIELDS" />
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

    <template v-if="isUser" #tab-general>
      <div class="h-full overflow-y-auto px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="USER_GENERAL_FIELDS" />
          <UserChangePassword :user="name" />
        </div>
      </div>
    </template>

    <template v-if="isUser" #tab-security>
      <div class="h-full overflow-y-auto px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="USER_SECURITY_FIELDS" />
      </div>
    </template>

    <template v-if="!isUser" #tab-details>
      <div class="h-full overflow-y-auto px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView
            :doctype="doctype"
            :detail="detail"
            :force-disabled="isLead && leadLocked"
            :read-only-fields="leadReadOnlyFields"
          />
          <LeadExtras
            v-if="isLead"
            ref="leadExtrasRef"
            :lead-name="name"
            @locked-change="(v) => (leadLocked = v)"
          />
        </div>
      </div>
    </template>

    <template v-if="!isUser" #tab-notes>
      <ActivityTimeline
        :doctype="doctype"
        :name="name"
        :types="['note', 'update']"
        show-composer
        empty-text="Nothing here yet — add the first note below."
      />
    </template>

    <template v-if="!isUser" #tab-activity>
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
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import LeadExtras from '@/components/detail/LeadExtras.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import UserRolesTab from '@/components/detail/UserRolesTab.vue'
import UserChangePassword from '@/components/detail/UserChangePassword.vue'
import { useDocDetail } from '@/composables/detail/useDocDetail'
import { useResource } from '@/composables/list/useResource'
import { useUnsavedChangesGuard } from '@/composables/common/useUnsavedChangesGuard'
import { notify } from '@/utils/common/notify'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => route.params.doctype)
const name = computed(() => route.params.name)

const detail = useDocDetail(doctype, name)

const isUser = computed(() => doctype.value === 'User')

// User gets its own curated tabs instead of the generic Details/Notes/
// Activity — it doesn't need an activity timeline, and its fields split
// naturally into desk's own User form sections.
const USER_TABS = [
  { key: 'profile', label: 'Profile' },
  { key: 'roles', label: 'Roles & Permissions' },
  { key: 'email', label: 'Email' },
  { key: 'general', label: 'General' },
  { key: 'security', label: 'Security' },
]
const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (isUser.value ? USER_TABS : DEFAULT_TABS))
const activeTab = ref('details')
watch(isUser, (value) => (activeTab.value = value ? 'profile' : 'details'), { immediate: true })

const USER_PROFILE_FIELDS = ['full_name', 'first_name', 'last_name', 'username', 'email']
const USER_EMAIL_FIELDS = ['thread_notify', 'send_me_a_copy', 'allowed_in_mentions']
const USER_GENERAL_FIELDS = ['language', 'time_zone', 'desk_theme']
const USER_SECURITY_FIELDS = ['simultaneous_sessions', 'restrict_ip', 'login_after', 'login_before']

// User's linked email accounts (the "user_emails" child table) — shown as
// its own reusable table on the Email tab instead of the read-only
// email_signature field.
const userEmailsTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'user_emails'))

const recordTitle = computed(() => {
  const titleField = detail.titleField.value
  return (titleField !== 'name' && detail.values[titleField]) || name.value
})

const isLead = computed(() => doctype.value === 'Lead')
const leadLocked = ref(false)
const leadExtrasRef = ref(null)

// Matches the old desk Lead form's onload(): status is always read-only,
// lead_owner only for non-Administrators — enforced here since these are
// Lead-specific UI rules, not something detail_view.py's generic
// get_doc_meta should know about.
const leadReadOnlyFields = computed(() => {
  if (!isLead.value) return []
  const fields = ['status']
  if (window.user !== 'Administrator') fields.push('lead_owner')
  return fields
})

// Combines this page's own field-grid dirty state with LeadExtras' separate
// Lead Detail Form dirty state (a different composable/save flow) so the
// unsaved-changes guard below covers both.
const isDirty = computed(() => detail.isDirty.value || (leadExtrasRef.value?.isDirty?.value ?? false))

// Saves whichever of this page's forms is actually dirty — this is what
// backs the "Save" option the unsaved-changes dialog offers alongside
// Leave/Stay, so choosing it there doesn't need its own separate flow.
async function saveAll() {
  let ok = true
  if (detail.isDirty.value) ok = (await detail.submit()) && ok
  if (leadExtrasRef.value?.isDirty?.value) ok = (await leadExtrasRef.value.save()) && ok
  return ok
}

// Only bypassNext() is used directly here — the router-level leave/unload
// prompts from this guard already cover the back button (it navigates via
// router.push below), so a second manual confirmDiscard() check there would
// just double the prompt.
const { bypassNext } = useUnsavedChangesGuard(isDirty, saveAll)

async function onSave() {
  // save's onSuccess already re-snapshots `values` from the response, so
  // isDirty clears synchronously — no separate detail.refresh() round-trip
  // needed (that gap was letting a just-saved page still look "dirty" for
  // a moment, triggering the leave-guard even right after a save).
  await detail.submit()
}

function goBack() {
  router.push({ name: 'DocList', params: { doctype: doctype.value } })
}

const showDeleteDialog = ref(false)

const deleteResource = useResource({
  url: 'verp_staffing.utils.list_view.delete_docs',
})
const deleting = computed(() => deleteResource.isLoading)

async function onDelete() {
  const result = await deleteResource.resource.submit({ doctype: doctype.value, names: [name.value] })
  if (!result) return // request itself failed; useResource already toasted it

  if (result.failed.length) {
    notify.error(result.failed[0].error)
    return
  }

  showDeleteDialog.value = false
  notify.success('Deleted.')
  // Not goBack() — the record is already gone, so there's nothing left to
  // discard and no reason to ask.
  bypassNext()
  router.push({ name: 'DocList', params: { doctype: doctype.value } })
}

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
