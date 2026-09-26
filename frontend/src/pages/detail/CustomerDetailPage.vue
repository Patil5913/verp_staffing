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
        <Dropdown v-if="!detail.isNew.value && actionMenu.length" :options="actionMenu" placement="right">
          <template #default="{ open }">
            <AppButton variant="outline" icon="zap" :class="open ? 'bg-app-panel-2' : ''">Actions</AppButton>
          </template>
        </Dropdown>
        <!-- Their buttons live in the Actions menu; these keep their dialogs and state. -->
        <ForwardCandidateButton
          v-if="!detail.isNew.value && hasSalesOrder && !forwardBlocked"
          ref="forwardRef"
          hide-button
          doctype="Customer"
          :name="name"
          :customer="name"
          from-service-name="Customer"
          @forwarded="detail.refresh"
        />
        <FieldUpdateActions ref="fieldUpdateRef" hide-buttons :detail="detail" :doctype="doctype" :name="name" mode="owner" />
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <DocDetailView
          :doctype="doctype"
          :detail="detail"
          :fieldnames="DETAIL_FIELDS"
          :read-only-fields="readOnlyFields"
          :field-link-queries="fieldLinkQueries"
          hide-empty-read-only
        />
      </div>
    </template>

    <template #tab-profile>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <LeadProfilePanel :form="profile" :tried-save="triedSaveProfile" />
      </div>
    </template>

    <template #tab-history>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <CustomerTimeline :customer="name" />
      </div>
    </template>

    <template #tab-agreements>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <CustomerAgreementsPanel :customer="name" />
      </div>
    </template>

    <template #tab-sales-orders>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <CustomerSalesOrdersPanel :customer="name" />
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

  <UnlockFormDialog v-if="!detail.isNew.value" v-model="showUnlock" :customer="name" :sales-order="detailsFormOrder" />
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
// Customer's detail page: the generic Details/Notes/Activity tabs, plus
// actions ported from customer.js - "Portal & Chat Access" (opens the email
// for review; sending it creates the customer's website user), "Create
// Sales Order" (desk form's sales_order Button field just does
// frappe.new_doc("Sales Order", {customer}); Sales Order isn't one of this
// app's ported doctypes yet, so this opens its own new-record route without
// the customer prefill the desk form has), "Forward Candidate" (shared with
// every service record page - see ForwardCandidateButton.vue, which branches
// on doctype === "Customer" the same way add_forward_button did), and a
// Candidate Profile tab + History tab (one timeline: crm/api/customer_timeline.py).
//
// Deliberately not ported: the owner "Update Detail"/"Accept Updates"
// field-change-request dialogs' desk-specific HTML widgets (their
// functionality is ported - see FieldUpdateActions - just not their exact
// markup).
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog, Dropdown, call } from 'frappe-ui'
import { notify } from '@/utils/common/notify'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import ForwardCandidateButton from '@/components/detail/actions/ForwardCandidateButton.vue'
import UnlockFormDialog from '@/components/detail/customer/UnlockFormDialog.vue'
import PortalAccessDialog from '@/components/detail/customer/PortalAccessDialog.vue'
import CustomerTimeline from '@/components/detail/customer/CustomerTimeline.vue'
import CustomerAgreementsPanel from '@/components/detail/customer/CustomerAgreementsPanel.vue'
import CustomerSalesOrdersPanel from '@/components/detail/customer/CustomerSalesOrdersPanel.vue'
import LeadProfilePanel from '@/components/detail/lead/LeadProfilePanel.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { useLeadDetailForm } from '@/composables/detail/useLeadDetailForm'
import { validateFieldValue } from '@/utils/detail/fieldFormats'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'Customer')
const name = computed(() => route.params.name)

// Portal & Chat Access, Forward Candidate and the History tab only make sense once the
// customer has a Sales Order (any that isn't cancelled), so they stay hidden until then.
const hasSalesOrder = ref(false)
async function checkSalesOrders() {
  if (!name.value || name.value === 'new') return (hasSalesOrder.value = false)
  try {
    const count = await call('frappe.client.get_count', { doctype: 'Sales Order', filters: { customer: name.value, docstatus: ['<', 2] } })
    hasSalesOrder.value = count > 0
  } catch {
    hasSalesOrder.value = false
  }
}
watch(name, checkSalesOrders, { immediate: true })

// The Sales Order (if any) whose services need the candidate details form - "Send Details Form".
const detailsFormOrder = ref('')
async function checkDetailsFormOrder() {
  if (!name.value || name.value === 'new') return (detailsFormOrder.value = '')
  detailsFormOrder.value = (await call('verp_staffing.accounts.doctype.sales_order.sales_order.get_candidate_form_order', { customer: name.value }).catch(() => null)) || ''
}
watch(name, checkDetailsFormOrder, { immediate: true })

// Forward Candidate waits for the details form / agreement when ERP Configuration makes them compulsory.
const forwardBlocked = ref(false)
async function checkForwardGate() {
  if (!name.value || name.value === 'new') return (forwardBlocked.value = false)
  const gate = await call('verp_staffing.accounts.doctype.sales_order.sales_order.get_forward_gate', { customer: name.value }).catch(() => null)
  forwardBlocked.value = !!gate?.blocked
}
watch(name, checkForwardGate, { immediate: true })

// The linked Lead Detail Form's candidate-facing fields - same "Candidate
// Profile" tab as Lead/Opportunity, and the same split-save folded into the
// one navbar Save (see OpportunityDetailPage.vue for the fuller rationale:
// the desk form embedded these inline via an HTML field with no Vue
// equivalent, so there was previously nowhere for an edit to actually go).
const profile = useLeadDetailForm('Customer', name)
const triedSaveProfile = ref(false)
async function saveProfile() {
  triedSaveProfile.value = true
  const invalid = profile.fields.value.find((f) => !f.read_only && validateFieldValue(f, profile.values[f.fieldname]))
  if (invalid) return false
  return profile.submit()
}

const { detail, recordTitle, isDirty, onSave, goBack, showDeleteDialog, deleting, onDelete } = useDetailPageController(
  doctype,
  name,
  { extraIsDirty: computed(() => profile.isDirty.value), extraSave: saveProfile },
)

const DEFAULT_TABS = computed(() => [
  { key: 'details', label: 'Details' },
  ...(profile.exists.value ? [{ key: 'profile', label: 'Candidate Profile' }] : []),
  ...(hasSalesOrder.value ? [{ key: 'history', label: 'History' }] : []),
  { key: 'sales-orders', label: 'Sales Orders' },
  ...(hasSalesOrder.value ? [{ key: 'agreements', label: 'Agreements' }] : []),
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
])
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.value.filter((t) => t.key === 'details') : DEFAULT_TABS.value))
const activeTab = ref('details')

const DETAIL_FIELDS = ['name1', 'customer_from', 'party_name', 'customer_owner', 'overall_status', 'chat_user', 'chat_access']

// customer_from/party_name are set_only_once on the doctype - the desk form
// never lets you re-pick where a Customer came from after creation.
const readOnlyFields = computed(() => (detail.isNew.value ? [] : ['customer_from', 'party_name']))

// Customer From only makes sense as a Lead or an Opportunity (Party then
// resolves to whichever of those was picked - see FieldControl's Dynamic
// Link support). Customer Owner: Sales department employees only, same
// get_employees_by_department join as Lead Owner (see LeadDetailPage.vue).
const fieldLinkQueries = {
  customer_from: { filters: { name: ['in', ['Lead', 'Opportunity']] } },
  customer_owner: {
    query: 'verp_staffing.crm.api.helpers.get_subordinate_employees',
    filters: { department: 'Sales' },
  },
}

// customer.js's set_customer_owner(frm): skip if already set; a Customer
// raised from an Opportunity inherits that Opportunity's owner; otherwise
// (from a Lead, or created standalone) it defaults to the current user's
// own linked Employee - no department check either way (that's what the
// customer_owner field's own Link filter above enforces on the *value*,
// separately, not on whether an auto-fill happens at all).
watch(
  () => [detail.meta.resource.data, detail.values.customer_from, detail.values.party_name],
  async ([data]) => {
    if (!data || !detail.isNew.value || detail.values.customer_owner) return

    if (detail.values.customer_from === 'Opportunity' && detail.values.party_name) {
      const owner = await call('frappe.client.get_value', {
        doctype: 'Opportunity',
        filters: detail.values.party_name,
        fieldname: 'opportunity_owner',
      }).catch(() => null)
      if (owner?.opportunity_owner) detail.values.customer_owner = owner.opportunity_owner
      return
    }

    const employee = await call('verp_staffing.employee.doctype.employee.employee.get_employee_from_user', {
      user: window.user,
    }).catch(() => null)
    if (employee) detail.values.customer_owner = employee
  },
  { immediate: true },
)

const showPortalAccess = ref(false)
const showUnlock = ref(false)
const forwardRef = ref(null)
const fieldUpdateRef = ref(null)

// Everything the customer page can do, as one Actions menu (only what applies right now).
const actionMenu = computed(() => {
  const items = []
  if (detailsFormOrder.value) items.push({ label: 'Send Details Form', icon: 'mail', onClick: () => (showUnlock.value = true) })
  else if (Number(detail.hidden?.lock_form)) items.push({ label: 'Unlock Form', icon: 'lock-open', onClick: () => (showUnlock.value = true) })
  if (hasSalesOrder.value && detail.values.chat_access !== 'Active') items.push({ label: 'Portal & Chat Access', icon: 'send', onClick: () => (showPortalAccess.value = true) })
  if (detail.values.chat_access === 'Active') items.push({ label: 'Revoke Portal Access', icon: 'user-x', theme: 'red', onClick: () => (showRevoke.value = true) })
  items.push({ label: 'Create Sales Order', icon: 'shopping-cart', onClick: onCreateSalesOrder })
  if (hasSalesOrder.value) {
    items.push({ label: 'Agreement', icon: 'file-signature', onClick: () => (activeTab.value = 'agreements') })
    if (!forwardBlocked.value) items.push({ label: 'Forward Candidate', icon: 'arrow-right', onClick: () => forwardRef.value?.openDialog() })
  }
  const fu = fieldUpdateRef.value
  if (fu?.state.canUpdate) items.push({ label: 'Update Detail', icon: 'pencil', onClick: () => fu.openUpdate() })
  if (fu?.state.requests.length) items.push({ label: `Accept Updates (${fu.state.requests.length})`, icon: 'check-check', onClick: () => fu.openReview() })
  return items
})

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
