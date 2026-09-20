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
        <AppButton
          v-if="!detail.isNew.value && detail.values.chat_access !== 'Active'"
          variant="outline"
          icon="send"
          @click="showPortalAccess = true"
        >
          Portal &amp; Chat Access
        </AppButton>
        <AppButton
          v-if="!detail.isNew.value && detail.values.chat_access === 'Active'"
          variant="outline"
          theme="red"
          icon="user-x"
          @click="showRevoke = true"
        >
          Revoke Portal Access
        </AppButton>
        <AppButton v-if="!detail.isNew.value" variant="outline" icon="shopping-cart" @click="onCreateSalesOrder">
          Create Sales Order
        </AppButton>
        <FieldUpdateActions :detail="detail" :doctype="doctype" :name="name" mode="owner" />
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <DocDetailView :doctype="doctype" :detail="detail" :fieldnames="DETAIL_FIELDS" :read-only-fields="readOnlyFields" />
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

  <PortalAccessDialog v-if="!detail.isNew.value" v-model="showPortalAccess" :customer="name" @sent="detail.refresh()" />
  <Dialog
    v-model="showRevoke"
    :options="{
      title: 'Revoke portal access',
      message: 'The customer will be signed out and lose access to the portal and chat straight away. You can restore it later by sending access again.',
      icon: { name: 'user-x', appearance: 'danger' },
    }"
  >
    <template #actions>
      <AppButton variant="danger" icon="user-x" :loading="revoking" @click="onRevoke">Revoke</AppButton>
    </template>
  </Dialog>
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
// Customer's detail page: the generic Details/Notes/Activity tabs, plus two
// actions ported from customer.js — "Portal & Chat Access" (opens the email
// for review; sending it creates the customer's website user) and "Create
// Sales Order" (desk form's sales_order Button field just does
// frappe.new_doc("Sales Order", {customer}); Sales Order isn't one of this
// app's ported doctypes yet, so this opens its own new-record route without
// the customer prefill the desk form has).
//
// Deliberately not ported: the desk form's History/Sales Orders tab
// widgets, the owner "Update Detail"/"Accept Updates" field-change-request
// dialogs, and the department-forwarding button — those lean on
// desk-specific HTML widgets and multi-step approval flows (see
// verp_staffing.crm.api.permission_request) that don't have a frontend
// equivalent yet.
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog, call } from 'frappe-ui'
import { notify } from '@/utils/common/notify'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import PortalAccessDialog from '@/components/detail/customer/PortalAccessDialog.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'Customer')
const name = computed(() => route.params.name)

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } =
  useDetailPageController(doctype, name)

const DEFAULT_TABS = [
  { key: 'details', label: 'Details' },
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
]
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.filter((t) => t.key === 'details') : DEFAULT_TABS))
const activeTab = ref('details')

const DETAIL_FIELDS = ['name1', 'customer_from', 'party_name', 'customer_owner', 'overall_status', 'chat_user', 'chat_access']

// customer_from/party_name are set_only_once on the doctype — the desk form
// never lets you re-pick where a Customer came from after creation.
const readOnlyFields = computed(() => (detail.isNew.value ? [] : ['customer_from', 'party_name']))

const showPortalAccess = ref(false)

const showRevoke = ref(false)
const revoking = ref(false)
async function onRevoke() {
  revoking.value = true
  try {
    await call('verp_staffing.crm.api.customer_chat.revoke_portal_access', { customer: name.value })
    notify.success('Portal access revoked.')
    showRevoke.value = false
    detail.refresh()
  } catch (e) {
    notify.error(e?.messages?.[0] || e?.message || 'Could not revoke access')
  } finally {
    revoking.value = false
  }
}

// Sales Order's page applies the query string to a new record (the desk's
// frappe.new_doc("Sales Order", { customer })), so the customer comes with it.
function onCreateSalesOrder() {
  router.push(`/Sales%20Order/new?customer=${encodeURIComponent(name.value)}`)
}
</script>
