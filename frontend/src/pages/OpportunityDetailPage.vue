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
      <div class="h-full overflow-y-auto px-6 py-4">
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
import AppButton from '@/components/common/AppButton.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

const route = useRoute()
const router = useRouter()

const doctype = computed(() => 'Opportunity')
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
const readOnlyFields = computed(() => (detail.values.status === 'Converted' ? ['status'] : []))

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
