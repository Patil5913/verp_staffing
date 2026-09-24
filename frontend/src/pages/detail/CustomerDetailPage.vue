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
        <AppButton v-if="!detail.isNew.value && Number(detail.hidden?.lock_form)" variant="outline" icon="lock-open" @click="showUnlock = true">Unlock Form</AppButton>
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
        <ForwardCandidateButton
          v-if="!detail.isNew.value"
          doctype="Customer"
          :name="name"
          :customer="name"
          from-service-name="Customer"
          @forwarded="detail.refresh"
        />
        <FieldUpdateActions :detail="detail" :doctype="doctype" :name="name" mode="owner" />
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
        <CustomerHistoryPanel :customer="name" :detail="detail" />
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

  <UnlockFormDialog v-if="!detail.isNew.value" v-model="showUnlock" :customer="name" />
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
// actions ported from customer.js — "Portal & Chat Access" (opens the email
// for review; sending it creates the customer's website user), "Create
// Sales Order" (desk form's sales_order Button field just does
// frappe.new_doc("Sales Order", {customer}); Sales Order isn't one of this
// app's ported doctypes yet, so this opens its own new-record route without
// the customer prefill the desk form has), "Forward Candidate" (shared with
// every service record page — see ForwardCandidateButton.vue, which branches
// on doctype === "Customer" the same way add_forward_button did), and a
// Candidate Profile tab + History tab (get_customer_history, same as the
// customer portal / public/js/customer_history.js).
//
// Deliberately not ported: the owner "Update Detail"/"Accept Updates"
// field-change-request dialogs' desk-specific HTML widgets (their
// functionality is ported — see FieldUpdateActions — just not their exact
// markup).
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog, call } from 'frappe-ui'
import { notify } from '@/utils/common/notify'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import FieldUpdateActions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'
import ForwardCandidateButton from '@/components/detail/actions/ForwardCandidateButton.vue'
import UnlockFormDialog from '@/components/detail/customer/UnlockFormDialog.vue'
import PortalAccessDialog from '@/components/detail/customer/PortalAccessDialog.vue'
import CustomerHistoryPanel from '@/components/detail/customer/CustomerHistoryPanel.vue'
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

// The linked Lead Detail Form's candidate-facing fields — same "Candidate
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
  { key: 'history', label: 'History' },
  { key: 'sales-orders', label: 'Sales Orders' },
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
])
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.value.filter((t) => t.key === 'details') : DEFAULT_TABS.value))
const activeTab = ref('details')

const DETAIL_FIELDS = ['name1', 'customer_from', 'party_name', 'customer_owner', 'overall_status', 'chat_user', 'chat_access']

// customer_from/party_name are set_only_once on the doctype — the desk form
// never lets you re-pick where a Customer came from after creation.
const readOnlyFields = computed(() => (detail.isNew.value ? [] : ['customer_from', 'party_name']))

// Customer From only makes sense as a Lead or an Opportunity (Party then
// resolves to whichever of those was picked — see FieldControl's Dynamic
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
// own linked Employee — no department check either way (that's what the
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
