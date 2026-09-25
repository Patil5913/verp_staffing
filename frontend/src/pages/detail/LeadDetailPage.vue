<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" :detail="detail" @back="goBack">
    <template #title-extra>
      <DocStatusBadge v-if="!detail.isNew.value" :status="detail.values.status" />
    </template>

    <template #actions>
      <RecordActionBar
        :show-save="!leadLocked"
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading || profile.save.isLoading"
        :show-delete="!detail.isNew.value && detail.canDelete.value"
        :delete-loading="deleting"
        @save="onSave"
        @delete="showDeleteDialog = true"
      >
        <AppButton v-if="!detail.isNew.value && !leadLocked" variant="outline" icon="target" @click="showOpportunityDialog = true">
          Create Opportunity
        </AppButton>
      </RecordActionBar>
    </template>

    <template #tab-details>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <NoticeBanner
            v-if="leadLocked"
            tone="info"
            message="This Lead is locked — an Opportunity already exists for it, so it can no longer be edited."
          />

          <!-- What the profile still needs, one click from the Details tab -->
          <button
            v-if="profile.exists.value"
            type="button"
            class="flex items-center gap-4 rounded-xl border border-app-border bg-app-panel px-5 py-4 text-left shadow-sm transition-colors hover:border-app-primary/40"
            @click="activeTab = 'profile'"
          >
            <span class="lucide-user-round-pen size-5 shrink-0 text-app-primary" />
            <span class="min-w-0 flex-1">
              <span class="block text-p-base font-medium text-app-text">Candidate profile</span>
              <span class="block text-p-sm text-app-text-muted">Education, experience, visa status, documents and consent.</span>
            </span>
            <span class="text-p-sm font-medium text-app-text">{{ completeness }}% complete</span>
            <span class="lucide-chevron-right size-4 text-app-text-muted" />
          </button>

          <DocDetailView
            :doctype="doctype"
            :detail="detail"
            :force-disabled="leadLocked"
            :read-only-fields="readOnlyFields"
            :field-link-queries="fieldLinkQueries"
            :field-overrides="fieldOverrides"
            title="Lead"
          />
        </div>
      </div>
    </template>

    <template #tab-profile>
      <div class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <NoticeBanner
            v-if="profileLockedByApproval"
            tone="info"
            message="This form is locked. Go to the Customer form and click 'Update Detail' to request changes."
          />
          <NoticeBanner
            v-else-if="leadClosed"
            tone="info"
            message="This Lead is Lost or Won, so its candidate form can no longer be edited."
          />
          <LeadProfilePanel :form="profile" :locked="profileLocked" :tried-save="triedSaveProfile" />
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

  <LeadOpportunityDialog v-model="showOpportunityDialog" :lead-name="name" @created="opportunity.resource.reload()" />

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
// Lead's detail page. Details holds the Lead itself; the candidate's
// "Lead Detail Form" (education, experience, visa, documents, consent) gets
// its own Candidate Profile tab, grouped into the doctype's sections, and
// both save from the one navbar Save. Once an Opportunity exists for the
// Lead it's locked (lead.js). See router.js for how /Lead/:name is routed
// here ahead of the generic /:doctype/:name.
//
// The profile form's state lives here, not in a tab component: tabs unmount
// when you leave them, and an unsaved profile edit must survive that.
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import NoticeBanner from '@/components/common/NoticeBanner.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import LeadOpportunityDialog from '@/components/detail/lead/LeadOpportunityDialog.vue'
import LeadProfilePanel from '@/components/detail/lead/LeadProfilePanel.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { useLeadDetailForm } from '@/composables/detail/useLeadDetailForm'
import { useResource } from '@/composables/list/useResource'
import { validateFieldValue } from '@/utils/detail/fieldFormats'

const route = useRoute()

const doctype = computed(() => 'Lead')
const name = computed(() => route.params.name)

const profile = useLeadDetailForm('Lead', name)
const triedSaveProfile = ref(false)

const opportunity = useResource({
  url: 'verp_staffing.crm.doctype.lead.lead.lead_has_opportunity',
  makeParams: () => ({ lead_name: name.value }),
  notifyOnError: false,
  auto: true,
})
const leadLocked = computed(() => !!opportunity.resource.data)
const showOpportunityDialog = ref(false)

// lead_detail_form.js: once a Sales Order needs the candidate form, its owner
// can't edit the profile directly — they ask via Update Detail on the Customer.
const formLock = useResource({
  url: 'verp_staffing.crm.api.permission_request.get_lead_detail_form_lock_status',
  notifyOnError: false,
})
watch(
  () => profile.docname.value,
  (docname) => docname && formLock.resource.submit({ lead_detail_doc: docname }),
  { immediate: true },
)
const profileLockedByApproval = computed(() => !!formLock.resource.data?.candidate_form_required && !!formLock.resource.data?.is_owner)
// A Lost or Won lead's candidate form is frozen (like its status).
const leadClosed = computed(() => ['Lost', 'Won', 'Opportunity'].includes(detail.meta.resource.data?.values?.status))
const profileLocked = computed(() => leadLocked.value || profileLockedByApproval.value || leadClosed.value)

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

// The lead person can change the status while the Lead is still being worked —
// Open, Lead or Interested (judged on the SAVED status, so picking Won doesn't lock
// the field mid-edit). Once it is Won / Lost / Opportunity the status is read-only,
// as in the old desk form. lead_owner stays Administrator-only.
const EDITABLE_STATUSES = ['Open', 'Lead', 'Interested']
const savedStatus = computed(() => detail.meta.resource.data?.values?.status || 'Open')
const statusEditable = computed(() => detail.isNew.value || EDITABLE_STATUSES.includes(savedStatus.value))
const readOnlyFields = computed(() => {
  const fields = statusEditable.value ? [] : ['status']
  if (window.user !== 'Administrator') fields.push('lead_owner')
  return fields
})
// Only these four can be picked; "Won" / "Opportunity" are set by the system (converting to an
// Opportunity) and never by hand.
// (Shown as-is once it is the saved value, so a read-only Opportunity still displays.)
const fieldOverrides = computed(() => ({
  status: { options: ['Lead', 'Lost', 'Interested', 'Open', ...(statusEditable.value ? [] : [savedStatus.value])].filter((v, i, a) => a.indexOf(v) === i).join('\n') },
}))

// Lead Owner: Sales or Lead department employees only (Employee has no
// plain department field — see get_employees_by_department), matching the
// old desk lead.js set_query("lead_owner", { department: ["in", [...]] }).
const fieldLinkQueries = {
  lead_owner: {
    query: 'verp_staffing.employee.doctype.employee.employee.get_employees_by_department',
    filters: { department: ['Sales', 'Lead'] },
  },
}

const completeness = computed(() => profile.completeness.value)

const allTabs = computed(() => [
  { key: 'details', label: 'Details' },
  ...(profile.exists.value ? [{ key: 'profile', label: 'Candidate Profile' }] : []),
  { key: 'notes', label: 'Notes' },
  { key: 'activity', label: 'Activity' },
])
const tabs = computed(() => (detail.isNew.value ? allTabs.value.slice(0, 1) : allTabs.value))
const activeTab = ref('details')
</script>
