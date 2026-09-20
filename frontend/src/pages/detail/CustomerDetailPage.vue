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
          v-if="!detail.isNew.value"
          variant="outline"
          icon="send"
          :loading="sendingPortalLink"
          @click="onSendPortalLink"
        >
          Send Portal Link
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
// actions ported from customer.js — "Send Portal Link" (calls the
// doctype's whitelisted send_portal_link, same as the desk form's button)
// and "Create Sales Order" (desk form's sales_order Button field just does
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
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

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

const DETAIL_FIELDS = ['name1', 'customer_from', 'party_name', 'customer_owner', 'overall_status']

// customer_from/party_name are set_only_once on the doctype — the desk form
// never lets you re-pick where a Customer came from after creation.
const readOnlyFields = computed(() => (detail.isNew.value ? [] : ['customer_from', 'party_name']))

const sendingPortalLink = ref(false)
const portalLink = useResource({
  url: 'verp_staffing.crm.doctype.customer.customer.send_portal_link',
})
async function onSendPortalLink() {
  sendingPortalLink.value = true
  try {
    const ok = await portalLink.resource.submit({
      customer: name.value,
      customer_name: detail.values.name1,
    })
    if (ok) notify.success('Portal link sent successfully.')
  } finally {
    sendingPortalLink.value = false
  }
}

// Sales Order's page applies the query string to a new record (the desk's
// frappe.new_doc("Sales Order", { customer })), so the customer comes with it.
function onCreateSalesOrder() {
  router.push(`/Sales%20Order/new?customer=${encodeURIComponent(name.value)}`)
}
</script>
