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
          v-if="!detail.isNew.value && detail.values.status !== 'Converted'"
          variant="outline"
          icon="user-plus"
          :loading="creatingCustomer"
          @click="onCreateCustomer"
        >
          Create Customer
        </AppButton>
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <DocDetailView
            :doctype="doctype"
            :detail="detail"
            :fieldnames="DETAIL_FIELDS"
            :read-only-fields="readOnlyFields"
          />
          <ChildTableField
            v-if="callDetailsTable"
            :table="callDetailsTable"
            :rows="detail.values.call_details || []"
            :disabled="!detail.canWrite.value"
            @update:rows="(rows) => (detail.values.call_details = rows)"
          />
        </div>
      </div>
    </template>

    <template #tab-profile>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <LeadProfilePanel :form="profile" :tried-save="triedSaveProfile" />
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
// Opportunity's detail page: the generic Details/Notes/Activity tabs, plus
// the "Create Customer" action ported from opportunity.js's
// handle_create_customer — it calls the doctype's own whitelisted
// create_customer() instance method (see opportunity.py), which converts
// this Opportunity to a Customer and marks it Converted. Status is
// read-only once Converted, same as the desk form. See router.js for how
// /Opportunity/:name is routed here ahead of the generic /:doctype/:name.
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import LeadProfilePanel from '@/components/detail/lead/LeadProfilePanel.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { useLeadDetailForm } from '@/composables/detail/useLeadDetailForm'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import { isAdministrator } from '@/utils/common/roles'
import { validateFieldValue } from '@/utils/detail/fieldFormats'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'Opportunity')
const name = computed(() => route.params.name)

// The linked Lead Detail Form's candidate-facing fields (education,
// experience, visa status...) — same "Candidate Profile" tab Lead's own
// detail page has, and the same split-save (this form has its own save
// endpoint, folded into the one navbar Save via extraIsDirty/extraSave
// below) so editing it here doesn't silently only update the in-memory
// copy: Opportunity previously had no way to view/edit these fields at all
// (the old desk form embedded them inline via an HTML field with no Vue
// equivalent), so "saving" them looked successful but there was nowhere
// for the edit to actually go.
const profile = useLeadDetailForm('Opportunity', name)
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
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
])
const tabs = computed(() => (detail.isNew.value ? DEFAULT_TABS.value.filter((t) => t.key === 'details') : DEFAULT_TABS.value))
const activeTab = ref('details')

const DETAIL_FIELDS = [
  'name1',
  'status',
  'source',
  'opportunity_owner',
  'sales_stage',
  'expected_closing_date',
  'probability_',
  'currency',
  'opportunity_amount',
  'opportunity_from_lead',
  'referral_customer',
]

// Converted is a one-way transition on the desk form (opportunity.js sets
// status read-only once Converted) — mirrored here the same way.
// opportunity_owner is read-only for everyone but Administrator (opportunity.js onload).
const readOnlyFields = computed(() => [
  ...(detail.values.status === 'Converted' ? ['status'] : []),
  ...(isAdministrator() ? [] : ['opportunity_owner']),
])

const callDetailsTable = computed(() => detail.tables.value.find((t) => t.fieldname === 'call_details'))

const creatingCustomer = ref(false)
const createCustomer = useResource({
  url: 'run_doc_method',
})
async function onCreateCustomer() {
  creatingCustomer.value = true
  try {
    const result = await createCustomer.resource.submit({
      dt: doctype.value,
      dn: name.value,
      method: 'create_customer',
    })
    if (!result) return
    const customerName = result.message?.customer || result.customer
    notify.success(`Customer ${customerName} created.`)
    detail.refresh()
    if (customerName) router.push(`/Customer/${encodeURIComponent(customerName)}`)
  } finally {
    creatingCustomer.value = false
  }
}
</script>
