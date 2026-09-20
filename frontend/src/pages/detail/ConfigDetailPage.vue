<template>
  <DetailPageLayout :title="recordTitle" :tabs="tabs" v-model:active-tab="activeTab" @back="goBack">
    <template #title-extra>
      <DocStatusBadge
        v-if="!detail.isNew.value"
        :status="!detail.isSubmittable.value ? statusText : ''"
        :docstatus="detail.isSubmittable.value ? detail.docstatus.value : null"
      />
    </template>

    <template #actions>
      <RecordActionBar
        :show-save="showSave"
        :save-dirty="isDirty"
        :save-loading="detail.save.isLoading"
        :show-delete="!detail.isNew.value && detail.canDelete.value && !config.noDelete"
        :delete-loading="deleting"
        :show-submit="!detail.isNew.value && detail.canSubmit.value"
        :submit-loading="detail.transitioning.value"
        :show-cancel="!detail.isNew.value && detail.canCancel.value"
        @save="onSave"
        @delete="showDeleteDialog = true"
        @submit="onSubmit"
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
            />
            <ChildTableField
              v-else-if="section.type === 'table' && tableFor(section.fieldname)"
              :table="tableFor(section.fieldname)"
              :rows="detail.values[section.fieldname] || []"
              :disabled="locked || !detail.canWrite.value || section.readOnly === true"
              :link-queries="linkQueriesFor(section)"
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
    v-model="showCancelDialog"
    :options="{
      title: `Cancel this ${doctype}?`,
      message: `Cancelling reverses this document's postings. This can't be undone.`,
      icon: { name: 'x-circle', appearance: 'danger' },
    }"
  >
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
//     { type: 'component', component, props?, show?(detail) },   // gets detail/doctype/name/locked
//   ] }],
//   timeline: 'full' | 'service' | false,   // Notes/Activity (+Updates) tabs
//   locked?(detail): boolean,               // freezes every field/table
//   readOnlyFields?(detail): string[],
//   actions?: [{ component, props?, show?(detail) }],  // before Save/Delete; also get `save` (the
//                                                       // page's Save, incl. new-record redirect)
//   statusField?: 'status',
//   fieldGuards?: [{ field, check(value, saved, detail) }],  // confirm / block a field edit
//   noDelete?: boolean,
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
import ActivityTimeline from '@/components/detail/ActivityTimeline.vue'
import { confirmLeave } from '@/utils/common/confirmDialog'
import { notify } from '@/utils/common/notify'
import { useDetailPageController } from '@/composables/detail/useDetailPageController'

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

const locked = computed(() => Boolean(props.config.locked?.(detail)) || detail.docstatus.value !== 0)
const readOnlyFields = computed(() => props.config.readOnlyFields?.(detail) || [])
const statusText = computed(() => {
  const field = props.config.statusField || 'status'
  return detail.values[field] || detail.hidden[field] || ''
})

const showSave = computed(() => !locked.value || detail.isNew.value)

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
const tableFor = (fieldname) => detail.tables.value.find((t) => t.fieldname === fieldname)
</script>
