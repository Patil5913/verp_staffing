<template>
  <SectionCard title="Interview Rounds" :subtitle="`${rows.length} ${rows.length === 1 ? 'round' : 'rounds'}`">
    <template #actions>
      <AppButton v-if="editable" variant="outline" size="sm" icon="plus" @click="addRound">Add Round</AppButton>
    </template>

    <div v-if="rows.length" class="flex flex-col gap-3">
      <div
        v-for="(row, idx) in rows"
        :key="row.name || `new-${idx}`"
        class="rounded-lg border border-app-border bg-app-panel-2/40 p-4"
      >
        <div class="mb-3 flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="flex size-6 items-center justify-center rounded-full bg-app-primary-tint text-p-xs font-semibold text-app-primary">
              {{ idx + 1 }}
            </span>
            <span class="text-p-sm font-medium text-app-text">Round {{ row.round || idx + 1 }}</span>
            <DocStatusBadge :status="row.status" />
            <span v-if="row.support" class="rounded-full bg-indigo-100 px-2 py-0.5 text-p-xs font-semibold text-indigo-700" title="Support taken">Support</span>
          </div>
          <AppButton
            v-if="editable && (isAdministrator() || (isSuperior && !row.name))"
            variant="ghost"
            size="icon"
            icon="trash-2"
            @click="removeRound(idx)"
          />
        </div>

        <div class="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          <template v-for="col in columns" :key="col.fieldname">
            <div v-if="showColumn(col, row)" :class="wide(col) ? 'col-span-full' : ''">
              <FieldControl
                :field="col"
                :model-value="row[col.fieldname]"
                :disabled="fieldDisabled(col, row, idx)"
                @update:model-value="(v) => onChange(idx, col.fieldname, v)"
              />
            </div>
          </template>
        </div>
      </div>
    </div>
    <p v-else class="rounded-lg border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      No rounds scheduled yet.
    </p>
    <p v-if="editable && !isSuperior && rows.length > 1" class="text-p-xs text-app-text-muted">
      Only the latest round is editable — a manager can change earlier rounds.
    </p>
  </SectionCard>

  <!-- interview_list.js's prompt_cancellation_details, ported: collects
  who it's attributed to + a reason before a round can actually move into
  Cancelled/Rescheduled/Rejected — extended here to also cover Rejected,
  which the desk dialog never did. -->
  <Dialog v-model="statusDialogOpen" :options="{ title: `Confirm ${pendingStatus}`, size: 'sm' }">
    <template #body-content>
      <div class="flex flex-col gap-4">
        <AppCombobox :label="`${pendingStatus} By`" :options="['Company', 'Candidate']" v-model="statusForm.cancelled_by" required />
        <AppInput :label="`Reason of ${pendingStatus}`" v-model="statusForm.reason_of_cancel" required />
      </div>
    </template>
    <template #actions>
      <AppButton :disabled="!statusForm.cancelled_by || !statusForm.reason_of_cancel.trim()" @click="confirmStatusDialog">
        Confirm
      </AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// The Interview's rounds table, with the desk form's rules from
// interview.js/interview_list.js kept intact:
//  * rounds are append-only, numbered by position — a superior can take back a
//    round they just added, and only Administrator can remove a saved one
//    (interview.js's cannot_delete_rows);
//  * unless you're a superior of the Marketing assignee, only the latest
//    round is editable;
//  * a round whose status is Cancelled / Rescheduled / Rejected / Completed
//    (case-insensitive) is fully locked, every field, the moment it's set —
//    not just once saved;
//  * Cancelled / Rescheduled / Rejected all go through the same
//    confirmation dialog first, collecting who it's attributed to and a
//    reason (interview_list.js's prompt_cancellation_details);
//  * follow_up may only step up by exactly one.
import { computed, reactive, ref, watch } from 'vue'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import FieldControl from '@/components/detail/FieldControl.vue'
import { useResource } from '@/composables/list/useResource'
import { useIsSuperior } from '@/composables/detail/useIsSuperior'
import { confirmLeave } from '@/utils/common/confirmDialog'
import { notify } from '@/utils/common/notify'
import { isAdministrator } from '@/utils/common/roles'

// Rejected joins the desk's own Cancelled/Rescheduled grouping here — same
// "ask who it's attributed to + why" dialog, same terminal lock. Matched
// case-insensitively against the row's live status (not just what was last
// saved), so a round is disabled the moment it's actually set to one of
// these, same edit session or not.
const CANCELLED_LIKE = ['cancelled', 'rescheduled', 'rejected']
const FINAL = ['cancelled', 'rescheduled', 'rejected', 'completed']
const statusOf = (row) => String(row?.status || '').toLowerCase()

const props = defineProps({
  detail: { type: Object, required: true },
  locked: { type: Boolean, default: false },
})

const table = computed(() => props.detail.tables.value.find((t) => t.fieldname === 'interview_rounds_table'))
// "round" is the position number, shown in the card header instead.
const columns = computed(() => (table.value?.columns || []).filter((c) => c.fieldname !== 'round'))
const rows = computed(() => props.detail.values.interview_rounds_table || [])
const editable = computed(() => !props.locked && props.detail.canWrite.value)

// A round whose *current* status (live, not just what was last saved) is
// Rescheduled/Rejected/Completed/Cancelled is fully locked — every field,
// not only Status.
const finalized = (row) => FINAL.includes(statusOf(row))

// Superior of the Marketing record's assignee, resolved off marketing_link.
const marketing = useResource({ url: 'frappe.client.get_value', notifyOnError: false })
watch(
  () => props.detail.values.marketing_link,
  (link) => link && marketing.resource.submit({ doctype: 'Marketing', filters: link, fieldname: 'assign_to' }),
  { immediate: true },
)
const { isSuperior } = useIsSuperior(computed(() => marketing.resource.data?.assign_to), 'Marketing')

const defaultStatus = useResource({
  url: 'frappe.client.get_single_value',
  params: { doctype: 'ERP Configuration', field: 'default_interview_status' },
  notifyOnError: false,
  auto: true,
})

// A new Interview starts in ERP Configuration's default status (its status
// field is read-only, so the user can't pick one) — interview.js's
// initialize_default_interview_status.
watch(
  () => defaultStatus.resource.data,
  (status) => {
    if (status && props.detail.isNew.value && !props.detail.values.status) props.detail.values.status = status
  },
  { immediate: true },
)

function fieldDisabled(col, row, idx) {
  if (!editable.value || col.read_only) return true
  if (finalized(row)) return true
  if (!isSuperior.value && idx !== rows.value.length - 1) return true
  return false
}
const showColumn = (col, row) =>
  !['cancelled_by', 'reason_of_cancel'].includes(col.fieldname) || CANCELLED_LIKE.includes(statusOf(row))
const wide = (col) => ['Small Text', 'Long Text'].includes(col.fieldtype)

function commit(next) {
  props.detail.values.interview_rounds_table = next
}
const patch = (idx, changes) => commit(rows.value.map((r, i) => (i === idx ? { ...r, ...changes } : r)))

function addRound() {
  const idx = rows.value.length + 1
  commit([
    ...rows.value,
    { round: String(idx), follow_up: 0, status: defaultStatus.resource.data || '', date: new Date().toISOString().slice(0, 10) },
  ])
}
const removeRound = (idx) => commit(rows.value.filter((_, i) => i !== idx))

// interview_list.js's prompt_cancellation_details — asks who it's
// attributed to (cancelled_by, doubling as "rejected by" here) and a
// reason before a Cancelled/Rescheduled/Rejected status actually commits.
const statusDialogOpen = ref(false)
const statusForm = reactive({ cancelled_by: '', reason_of_cancel: '' })
const pending = ref(null) // { idx, value }
const pendingStatus = computed(() => pending.value?.value || '')

function openStatusDialog(idx, value) {
  pending.value = { idx, value }
  Object.assign(statusForm, { cancelled_by: '', reason_of_cancel: '' })
  statusDialogOpen.value = true
}
function confirmStatusDialog() {
  if (!statusForm.cancelled_by || !statusForm.reason_of_cancel.trim()) return
  const { idx, value } = pending.value
  patch(idx, { status: value, cancelled_by: statusForm.cancelled_by, reason_of_cancel: statusForm.reason_of_cancel.trim() })
  statusDialogOpen.value = false
  pending.value = null
}

async function onChange(idx, fieldname, value) {
  const row = rows.value[idx]

  if (fieldname === 'follow_up') {
    const prev = Number(row.follow_up || 0)
    const next = Number(value || 0)
    if (next !== prev && next !== prev + 1) {
      notify.error(`Invalid Follow Up value. Only allowed value is ${prev + 1}`)
      return
    }
  }

  if (fieldname === 'status' && value !== row.status) {
    const next = String(value || '').toLowerCase()
    if (CANCELLED_LIKE.includes(next)) {
      openStatusDialog(idx, value)
      return
    }
    if (FINAL.includes(next)) {
      const ok = await confirmLeave({
        title: 'Lock this round?',
        message: `Once this round's status is set to '${value}', it cannot be changed again. Continue?`,
        leaveLabel: 'Continue',
        cancelLabel: 'Cancel',
      })
      if (!ok) return
    }
  }

  patch(idx, { [fieldname]: value })
}
</script>
