<template>
  <DetailPageLayout
    :title="recordTitle"
    :tabs="tabs"
    v-model:active-tab="activeTab"
    :detail="detail"
    :hide-draft-notice="hideDraftNotice"
    @back="goBack"
  >
    <template #title-extra>
      <DocStatusBadge
        v-if="!detail.isNew.value"
        :status="!detail.isSubmittable.value || overridesDocstatus ? statusText : ''"
        :docstatus="detail.isSubmittable.value && !overridesDocstatus ? detail.docstatus.value : null"
        :doctype="doctype"
        :field="resolvedStatusField"
      />
    </template>

    <template #actions>
      <RecordActionBar
        :show-save="showSave"
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="!detail.isNew.value && detail.canDelete.value && !config.noDelete"
        :delete-loading="deleting"
        :show-submit="!detail.isNew.value && detail.canSubmit.value && !locked"
        :submit-loading="detail.transitioning.value"
        :show-cancel="!detail.isNew.value && detail.canCancel.value"
        @save="onSave"
        @delete="showDeleteDialog = true"
        @submit="triggerSubmit"
        @cancel="showCancelDialog = true"
      >
        <component
          :is="action.component"
          v-for="(action, i) in visibleActions"
          :key="i"
          v-bind="action.props"
          :detail="detail"
          :doctype="doctype"
          :name="name"
          :locked="locked"
          :save="onSave"
        />
      </RecordActionBar>
    </template>

    <template v-for="tab in tabs" #[`tab-${tab.key}`]>
      <ActivityTimeline
        v-if="tab.timeline"
        :doctype="doctype"
        :name="name"
        :types="tab.timeline.types"
        :show-composer="tab.timeline.composer"
        :allow-create="tab.timeline.create"
        :empty-text="tab.timeline.empty"
      />
      <div v-else class="h-full overflow-y-auto px-3 md:px-6 py-4">
        <div class="flex flex-col gap-6">
          <template v-for="(section, i) in visibleSections(tab)" :key="i">
            <DocDetailView
              v-if="section.type === 'fields'"
              :doctype="doctype"
              :detail="detail"
              :fieldnames="section.fieldnames"
              :title="section.title"
              :force-disabled="locked || section.readOnly === true"
              :read-only-fields="readOnlyFields"
              :field-link-queries="linkQueriesFor(section)"
            />
            <ChildTableField
              v-else-if="sectionKind(section) === 'table' && tableFor(section.fieldname)"
              :table="tableFor(section.fieldname)"
              :rows="detail.values[section.fieldname] || []"
              :disabled="locked || !detail.canWrite.value || section.readOnly === true"
              :link-queries="rowQueriesFor(section)"
              :hidden-columns="section.hiddenColumns"
              :field-overrides="section.fieldOverrides"
              :on-field-change="onFieldChangeFor(section)"
              :on-file-meta="section.onFileMeta"
              @update:rows="(rows) => (detail.values[section.fieldname] = rows)"
            />
            <GridTableField
              v-else-if="sectionKind(section) === 'grid' && tableFor(section.fieldname)"
              :table="tableFor(section.fieldname)"
              :rows="detail.values[section.fieldname] || []"
              :columns="section.columns"
              :hidden-columns="section.hiddenColumns"
              :read-only-columns="section.readOnlyColumns"
              :disabled="locked || !detail.canWrite.value || section.readOnly === true"
              :link-queries="rowQueriesFor(section)"
              :on-field-change="onFieldChangeFor(section)"
              @update:rows="(rows) => (detail.values[section.fieldname] = rows)"
            />
            <component
              :is="section.component"
              v-else-if="section.type === 'component'"
              v-bind="section.props"
              :detail="detail"
              :doctype="doctype"
              :name="name"
              :locked="locked"
            />
          </template>
        </div>
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
    v-model="showSubmitDialog"
    :options="{
      title: `Submit this ${doctype}?`,
      icon: { name: 'check-circle', appearance: 'success' },
    }"
  >
    <template #body-content>
      <div v-html="submitConfirmHtml" />
    </template>
    <template #actions>
      <AppButton variant="solid" icon="check" :loading="detail.transitioning.value" @click="confirmSubmit">
        Submit
      </AppButton>
    </template>
  </Dialog>

  <MissingEmailDialog v-model="missingEmailOpen" :customer="detail.values.customer" @saved="onEmailSaved" />

  <Dialog
    v-model="showCancelDialog"
    :options="{
      title: `Cancel this ${doctype}?`,
      message: cancelConfirmHtml ? undefined : `Cancelling reverses this document's postings. This can't be undone.`,
      icon: { name: 'x-circle', appearance: 'danger' },
    }"
  >
    <template v-if="cancelConfirmHtml" #body-content>
      <div v-html="cancelConfirmHtml" />
    </template>
    <template #actions>
      <AppButton variant="danger" icon="x-circle" :loading="detail.transitioning.value" @click="onCancelDoc">
        Cancel document
      </AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// One config-driven detail page for every doctype whose form is "some field
// groups + some child tables + a few custom panels/actions" — i.e. all of
// them except the handful with a bespoke layout (Lead, User, Hierarchy, ...).
// A doctype's page is just its config (see detailConfigs/), routed through
// router.js; this file owns the chrome once: tabs, Save/Delete, Submit/Cancel
// for submittable doctypes, the Notes/Updates/Activity timeline tabs, and
// the "locked" state that freezes a record.
//
// config = {
//   doctype,
//   tabs: [{ key, label, sections: [
//     { type: 'fields', fieldnames: [...], readOnly?, show?(detail) },
//     { type: 'table', fieldname, readOnly?, show?(detail) },
//     { type: 'grid', fieldname, columns: [...], readOnlyColumns?, show?(detail) },
//     { type: 'component', component, props?, show?(detail) },   // gets detail/doctype/name/locked
//   ] }],
//   timeline: 'full' | 'service' | false,   // Notes/Activity (+Updates) tabs
//   locked?(detail): boolean,               // freezes every field/table
//   readOnlyFields?(detail): string[],
//   actions?: [{ component, props?, show?(detail) }],  // before Save/Delete; also get `save` (the
//                                                       // page's Save, incl. new-record redirect)
//   statusField?: 'status',
//   hideDraftNotice?(detail): boolean,      // suppress the generic "submit
//                                            // this to confirm" draft banner
//                                            // (Payment Entry: hidden while
//                                            // Rejected, its own messaging)
//   fieldGuards?: [{ field, check(value, saved, detail) }],  // confirm / block a field edit
//   noDelete?: boolean,
//   autoCalculate?: boolean,                // live-recompute Items/Taxes/
//                                            // Totals client-side on every
//                                            // relevant edit (docCalculator.js
//                                            // — same math as the server's
//                                            // run_calculation), instead of
//                                            // only reflecting the last save
//   submitConfirm?(detail): string,         // HTML body for a confirm
//                                            // dialog before Submit; omitted
//                                            // = Submit fires immediately
//   cancelConfirm?(detail): string,         // HTML body for Cancel's
//                                            // confirm dialog; omitted =
//                                            // the generic one-line message
// }
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import GridTableField from '@/components/detail/GridTableField.vue'
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import MissingEmailDialog from '@/components/common/MissingEmailDialog.vue'
import { confirmLeave } from '@/utils/common/confirmDialog'
import { notify } from '@/utils/common/notify'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'
import { recalcDocTotals } from '@/utils/detail/docCalculator'
import { useInvoiceDynamics } from '@/composables/detail/useInvoiceDynamics'

const props = defineProps({
  config: { type: Object, required: true },
})

const route = useRoute()
const doctype = computed(() => props.config.doctype)
const name = computed(() => route.params.name)

const {
  detail,
  recordTitle,
  isDirty,
  onSave,
  goBack,
  showDeleteDialog,
  deleting,
  onDelete,
  onSubmit,
  onCancelDoc,
  showCancelDialog,
} = useDetailPageController(doctype, name)

// A config can supply submitConfirm(detail)/cancelConfirm(detail) returning
// an HTML string for a doctype-specific "here's what this actually does"
// dialog (Payment Entry: submitting locks it in as Verified, cancelling
// reverses the GL entries) — Submit had no confirmation at all before this,
// and Cancel only ever showed one generic sentence regardless of doctype.
// A config without either keeps exactly the previous behavior (submit
// fires immediately; cancel shows the generic message).
const showSubmitDialog = ref(false)
const submitConfirmHtml = computed(() => props.config.submitConfirm?.(detail) || '')
const cancelConfirmHtml = computed(() => props.config.cancelConfirm?.(detail) || '')

// A submit that fails because the customer has no email to send the
// candidate form/agreement to (Sales Order's pre-submit checks) offers a
// small dialog to collect one instead of dead-ending — see
// useDetailPageController's onSubmit / MissingEmailDialog.vue.
const missingEmailOpen = ref(false)
function onEmailSaved() {
  triggerSubmit()
}

async function triggerSubmit() {
  if (props.config.submitConfirm) {
    showSubmitDialog.value = true
  } else {
    const result = await onSubmit()
    if (result?.emailMissing) missingEmailOpen.value = true
  }
}
async function confirmSubmit() {
  const result = await onSubmit()
  showSubmitDialog.value = false
  if (result?.emailMissing) missingEmailOpen.value = true
}

// Items/Taxes/discount/rounding/currency — the full set docCalculator.js's
// recalcDocTotals reads. Deep so an edit inside an existing item/tax row
// (not just adding/removing one) triggers it too; recalcDocTotals writing
// the same numbers back doesn't cause a loop since Vue skips a reactive set
// that doesn't actually change the value.
watch(
  () => [
    detail.values.items,
    detail.values.taxes,
    detail.values.additional_discount_percentage,
    detail.values.disable_rounded_total,
    detail.values.conversion_rate,
  ],
  () => {
    // Only a draft is being edited; a submitted doc's totals (and its outstanding
    // amount, which Payment Entries reduce) must not be recomputed from scratch.
    if (props.config.autoCalculate && detail.docstatus.value === 0) recalcDocTotals(detail.values)
  },
  { deep: true },
)

if (props.config.autoCalculate) useInvoiceDynamics(detail, { expenseSide: /^Purchase/.test(props.config.doctype) })

const locked = computed(() => Boolean(props.config.locked?.(detail)) || detail.docstatus.value !== 0)
const readOnlyFields = computed(() => props.config.readOnlyFields?.(detail) || [])
// statusField is usually a plain fieldname, but can be a function of the
// record when which status field applies is conditional — Payment Entry
// shows verification_status instead of docstatus, but only once
// doc.payment_term is set (see paymentEntryConfig); otherwise it's a plain
// docstatus-driven Draft/Submitted/Cancelled payment like any other.
const resolvedStatusField = computed(() =>
  typeof props.config.statusField === 'function' ? props.config.statusField(detail) : props.config.statusField,
)
// A purely computed status label (Sales Invoice's Paid/Unpaid/Partly Paid
// from outstanding_amount — not backed by any real field) instead of a
// fieldname to read off the doc — takes precedence over statusField.
const computedStatusText = computed(() => props.config.statusText?.(detail) ?? null)
// Whether the status badge should override docstatus even on an otherwise-
// submittable doctype (true when either mechanism actually produced text).
const overridesDocstatus = computed(
  () => computedStatusText.value != null || (typeof props.config.statusField === 'function' && !!resolvedStatusField.value),
)
// The generic draft notice ("submit this to confirm") is suppressed when the
// config opts out — Payment Entry's own verification_status already covers
// "Rejected" with more specific messaging, so the generic one would be
// redundant/confusing there.
const hideDraftNotice = computed(() => Boolean(props.config.hideDraftNotice?.(detail)))
const statusText = computed(() => {
  if (computedStatusText.value != null) return computedStatusText.value
  const field = resolvedStatusField.value || 'status'
  return detail.values[field] || detail.hidden[field] || ''
})

// A submitted doc is normally frozen, but a config can opt in to keeping Save
// available for the fields the doctype marks allow_on_submit (Sales Order's
// payment_terms) — the server only applies those on a submitted doc.
const canEditAfterSubmit = computed(
  () => Boolean(props.config.allowOnSubmitEdit) && detail.docstatus.value === 1 && !!detail.meta.resource.data?.perms?.write,
)
const showSave = computed(() => !locked.value || detail.isNew.value || canEditAfterSubmit.value)

const TIMELINE_TABS = {
  full: [
    { key: 'notes', label: 'Notes', timeline: { types: ['note', 'update'], composer: true, empty: 'Nothing here yet — add the first note below.' } },
    { key: 'activity', label: 'Activity', timeline: { types: ['task', 'event'], create: true, empty: 'No tasks or events linked to this record yet.' } },
  ],
  service: [
    { key: 'notes', label: 'Notes', timeline: { types: ['note'], composer: true, empty: 'Nothing here yet — add the first note below.' } },
    { key: 'updates', label: 'Updates', timeline: { types: ['update'], empty: 'No updates yet.' } },
    { key: 'activity', label: 'Activity', timeline: { types: ['task', 'event'], create: true, empty: 'No tasks or events linked to this record yet.' } },
  ],
}

const allTabs = computed(() => [
  ...props.config.tabs.filter((t) => !t.show || t.show(detail)),
  ...(TIMELINE_TABS[props.config.timeline] || []),
])
// Every tab past the first needs a saved docname (history, timeline, ...).
const tabs = computed(() => (detail.isNew.value ? allTabs.value.slice(0, 1) : allTabs.value))
const activeTab = ref(props.config.tabs[0].key)

// fieldGuards: [{ field, check(value, savedValue, detail) }] — intercepts the
// user's own edit of a field (never a value loading in from the server). check
// returns { block: 'message' } to refuse the change, { confirm: { title,
// message, confirmLabel } } to ask first, or nothing to allow it. Either way a
// refused change snaps back — the desk form's frappe.confirm() on a checkbox.
for (const guard of props.config.fieldGuards || []) {
  let reverting = false
  watch(
    () => detail.values[guard.field],
    async (value, previous) => {
      if (reverting || previous === undefined) return
      const saved = detail.meta.resource.data?.values?.[guard.field]
      if (value === saved) return
      const verdict = guard.check(value, saved, detail)
      if (!verdict) return
      let allowed = false
      if (verdict.confirm) {
        allowed = await confirmLeave({
          title: verdict.confirm.title,
          message: verdict.confirm.message,
          leaveLabel: verdict.confirm.confirmLabel || 'Continue',
          cancelLabel: 'Cancel',
        })
      } else if (verdict.block) {
        notify.error(verdict.block)
      }
      if (!allowed) {
        reverting = true
        detail.values[guard.field] = previous
        await Promise.resolve()
        reverting = false
      }
    },
  )
}

const visibleActions = computed(() => (props.config.actions || []).filter((a) => !a.show || a.show(detail)))
const visibleSections = (tab) => (tab.sections || []).filter((s) => !s.show || s.show(detail))
// A table section's `linkQueries` is an object, or a function of the page
// ({ detail, name }) when it depends on the record (Fiscal Year's company
// picker excludes companies already in another year).
const linkQueriesFor = (section) =>
  typeof section.linkQueries === 'function' ? section.linkQueries({ detail, name: name.value }) : section.linkQueries
// A table section's onFieldChange (row cross-field logic — see
// ChildTableField's own prop) gets the same { detail, name } context a
// component section does, since it often needs sibling doc fields (Sales
// Order's Items Table needs the doc's own `company`). GridTableField also
// passes a 4th argument (the row's index) that ChildTableField has no
// equivalent for (a dialog edits one row in isolation, with no stable
// index) — that index is forwarded here as `idx` on the context object
// rather than as a bare positional argument, so existing onFieldChange
// signatures (fieldname, value, draft, { detail, name }) don't silently
// break; a grid-backed section that needs it just destructures `idx` too.
// Previously this argument was dropped entirely, which is fine for a table
// section (idx is always undefined there) but was a real gap for any grid
// section whose logic depends on row position (e.g. Taxes and Charges'
// "no previous row for the first row" check).
const onFieldChangeFor = (section) =>
  section.onFieldChange
    ? (fieldname, value, draft, idx) => section.onFieldChange(fieldname, value, draft, { detail, name: name.value, idx })
    : null
// type 'auto': the child doctype's own "Editable Grid" flag decides between the
// inline grid and the per-row dialog; 'grid' / 'table' force one.
const sectionKind = (section) =>
  section.type === 'auto' ? (tableFor(section.fieldname)?.editable_grid ? 'grid' : 'table') : section.type
// The section's static/record-level link queries plus an optional per-row
// `rowLinkQueries(row, rows, idx, { detail })` (e.g. Items: exclude items already
// picked in other rows) — returned as one (row, rows, idx) function.
const rowQueriesFor = (section) => {
  const base = linkQueriesFor(section)
  if (!section.rowLinkQueries) return base
  return (row, rows, idx) => ({ ...(base || {}), ...section.rowLinkQueries(row, rows, idx, { detail }) })
}
const tableFor = (fieldname) => detail.tables.value.find((t) => t.fieldname === fieldname)
</script>