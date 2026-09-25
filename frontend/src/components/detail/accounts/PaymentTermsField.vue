<template>
  <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-p-base font-medium text-app-text">Payment Terms</h3>
        <p class="text-p-sm text-app-text-muted">
          {{ rows.length }} {{ rows.length === 1 ? 'term' : 'terms' }} ·
          {{ formatFieldValue(total, { fieldtype: 'Currency' }) }} of {{ formatFieldValue(soTotal, { fieldtype: 'Currency' }) }} scheduled
        </p>
      </div>
      <AppButton v-if="!disabled && hasRoom" variant="outline" size="sm" icon="plus" @click="addRow">Add Row</AppButton>
    </div>

    <div v-if="rows.length" class="overflow-x-auto rounded-lg border border-app-border">
      <table class="w-full table-fixed border-collapse text-left text-p-sm">
        <thead>
          <tr class="bg-app-panel-2">
            <th class="h-9 w-6 border-b border-app-border" />
            <th class="h-9 truncate border-b border-app-border px-2 text-p-xs font-medium text-app-text-muted">Condition</th>
            <th class="h-9 w-16 truncate border-b border-app-border px-2 text-p-xs font-medium text-app-text-muted">Count</th>
            <th class="h-9 truncate border-b border-app-border px-2 text-p-xs font-medium text-app-text-muted">Start Date</th>
            <th class="h-9 truncate border-b border-app-border px-2 text-p-xs font-medium text-app-text-muted">Due Date</th>
            <th class="h-9 truncate border-b border-app-border px-2 text-p-xs font-medium text-app-text-muted">Decided Amount</th>
            <th class="h-9 truncate border-b border-app-border px-2 text-p-xs font-medium text-app-text-muted">Received Amount</th>
            <th class="h-9 truncate border-b border-app-border px-2 text-p-xs font-medium text-app-text-muted">Status</th>
            <th class="h-9 w-28 border-b border-app-border" />
          </tr>
        </thead>
        <tbody>
          <template v-for="(row, idx) in rows" :key="idx">
            <tr
              class="cursor-pointer border-b border-app-border align-top last:border-0 hover:bg-app-panel-2/40"
              :class="{ 'bg-app-primary-tint/30': activeIdx === idx }"
              @click="activate(idx)"
            >
              <td class="px-1 py-2 text-center" @click.stop="toggleExpand(idx)">
                <FeatherIcon :name="expandedIdx === idx ? 'chevron-down' : 'chevron-right'" class="mx-auto h-4 w-4 text-app-text-muted" />
              </td>
              <td class="px-2 py-1.5" @click.stop>
                <AppCombobox
                  v-if="isRowActive(idx) && !isConditionLocked(row)"
                  :model-value="row.payment_condition || ''"
                  :options="CONDITION_OPTIONS"
                  @update:model-value="(v) => onChange(idx, 'payment_condition', v)"
                />
                <span v-else class="truncate">{{ row.payment_condition || '-' }}</span>
              </td>
              <td class="px-2 py-1.5" @click.stop>
                <AppInput
                  v-if="isRowActive(idx) && row.payment_condition != 'Not Applied'"
                  type="number"
                  compact
                  :model-value="row.counter ?? ''"
                  @update:model-value="(v) => onChange(idx, 'counter', v)"
                />
                <span v-else class="truncate">{{ row.counter ?? '-' }}</span>
              </td>
              <td class="px-2 py-1.5" @click.stop>
                <AppDatePicker
                  v-if="isRowActive(idx) && row.payment_condition === 'Number of Days'"
                  compact
                  mode="date"
                  :model-value="row.start_date || ''"
                  @update:model-value="(v) => onChange(idx, 'start_date', v)"
                />
                <span v-else class="truncate">{{ formatDate(row.start_date) || '-' }}</span>
              </td>
              <td class="px-2 py-1.5 truncate text-app-text-muted">{{ formatDate(row.due_date) || '-' }}</td>
              <td class="px-2 py-1.5" @click.stop>
                <div v-if="isRowActive(idx)" class="flex items-center gap-1">
                  <AppInput type="number" compact :model-value="row.amount ?? ''" @update:model-value="(v) => onChange(idx, 'amount', v)" />
                  <span class="shrink-0 text-p-xs text-app-text-muted">{{ row.so_currency || soCurrency }}</span>
                </div>
                <span v-else class="truncate">{{ formatFieldValue(row.amount, { fieldtype: 'Currency' }) }} {{ row.so_currency || soCurrency }}</span>
              </td>
              <td class="px-2 py-1.5 truncate text-app-text-muted">
                {{ formatFieldValue(row.received_amount, { fieldtype: 'Currency' }) }} {{ row.currency || '' }}
              </td>
              <td class="px-2 py-1.5"><DocStatusBadge :status="row.payment_status || 'Unpaid'" doctype="Sales Order" field="payment_status" /></td>
              <td class="px-2 py-1.5 text-right" @click.stop>
                <AppButton
                  v-if="!isRowActive(idx) && canMarkAsPaid(row)"
                  size="sm"
                  :variant="row.payment_status === 'Rejected' ? 'outline' : 'primary'"
                  @click="openMarkAsPaid(row)"
                >
                  {{ row.payment_status === 'Rejected' ? 'Re-request' : 'Mark as Paid' }}
                </AppButton>
                <span v-else-if="row.payment_status === 'Pending Verification'" class="text-p-xs text-app-text-muted">Awaiting verification</span>
                <AppButton
                  v-if="!disabled && !isTermLocked(row) && !isRowActive(idx)"
                  variant="ghost"
                  size="icon"
                  icon="edit-2"
                  title="Edit row"
                  @click.stop="activate(idx)"
                />
                <AppButton v-if="!disabled && !isTermLocked(row)" variant="ghost" size="icon" icon="trash-2" title="Delete row" @click.stop="removeRow(idx)" />
              </td>
            </tr>

            <!-- Expanded: every field on the row - all read-only, Description
            included (auto-generated from the row's other fields, same as
            the desk form; never manually typed there either). -->
            <tr v-if="expandedIdx === idx" class="border-b border-app-border bg-app-panel-2/30 last:border-0">
              <td />
              <td colspan="8" class="p-4">
                <div class="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-3">
                  <div v-for="col in expandedColumns" :key="col.fieldname" class="min-w-0">
                    <p class="text-p-xs text-app-text-muted">{{ col.label }}</p>
                    <p class="truncate text-p-sm text-app-text">{{ displayValue(row, col) }}</p>
                  </div>
                </div>

                <!-- Verify/Reject/Re-request history (_append_verification_log
                on the backend) - one timestamped line per event, never shown
                anywhere in this SPA before now. -->
                <div v-if="row.verification_log" class="mt-4 border-t border-app-border pt-3">
                  <p class="mb-1.5 text-p-xs font-medium text-app-text-muted">Verification Log</p>
                  <div class="flex flex-col gap-1 rounded-lg bg-app-panel-2/50 p-3">
                    <p v-for="(line, i) in verificationLogLines(row)" :key="i" class="text-p-xs text-app-text">
                      {{ line }}
                    </p>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <p v-else class="rounded-lg border border-dashed border-app-border py-6 text-center text-p-sm text-app-text-muted">
      No payment terms on this order.
    </p>

    <Dialog v-model="markAsPaidOpen" :options="{ title: rerequest ? 'Re-request Verification' : 'Mark as Paid', size: 'lg' }">
      <template #body-content>
        <div v-if="markAsPaidRow" class="flex flex-col gap-4">
          <div class="rounded-lg bg-app-primary-tint px-4 py-3 text-p-sm text-app-text">
            <p><b>Amount:</b> {{ formatFieldValue(markAsPaidRow.received_amount || markAsPaidRow.amount, { fieldtype: 'Currency' }) }} {{ markAsPaidRow.currency || soCurrency }}</p>
            <p v-if="markAsPaidRow.sales_invoice"><b>Invoice:</b> {{ markAsPaidRow.sales_invoice }}</p>
            <p v-else class="text-app-text-muted">An invoice will be created for the company selected below.</p>
          </div>

          <template v-if="!markAsPaidRow.sales_invoice">
            <AppLinkField label="Company" doctype="Company" v-model="form.company" hide-add-new />
            <AppInput v-if="foreign" type="number" :label="`Exchange Rate (1 ${soCurrency} = ?)`" v-model="form.conversion_rate" required />
            <p v-if="form.company" class="text-p-sm text-app-text-muted">
              Received: <b>{{ formatFieldValue(receivedPreview, { fieldtype: 'Currency' }) }} {{ targetCurrency }}</b>
            </p>
          </template>

          <AppInput label="Payer's Account Name" v-model="form.payer_account_name" required />
          <AppInput label="Reference Id / Transaction No / Cheque No" v-model="form.reference_no" required />
          <AppInput type="textarea" label="Remarks (amount paid in which account)" v-model="form.remarks" required />
          <AppInput type="date" label="Reference Date" v-model="form.reference_date" required />
        </div>
      </template>
      <template #actions>
        <AppButton :loading="submittingMarkAsPaid" :disabled="!markAsPaidValid" @click="submitMarkAsPaid">
          {{ rerequest ? 'Re-request' : 'Submit for Verification' }}
        </AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
// Sales Order's Payment Terms - the ONLY place they're editable (no
// separate dialog-per-row, no second read-only display table below this
// one): each row is a summary line that becomes inline-editable on click,
// with an expand arrow for the rest of its fields (only Description is
// ever editable there - everything else is server/workflow-derived), and
// its own "Mark as Paid" trigger folded in rather than living in a
// duplicate component. Ported from sales_order.js's Customer Payment Terms
// row handlers (condition-based clearing / interview-count fetch / due-date
// calc) and the old PaymentTermsPanel.vue's Mark as Paid dialog - both
// consolidated here instead of split across two components.
import { computed, reactive, ref, watch } from 'vue'
import { Dialog, FeatherIcon, call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import AppDatePicker from '@/components/ui/AppDatePicker.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import { useResource } from '@/composables/list/useResource'
import { formatDate, formatFieldValue } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, required: true },
  locked: { type: Boolean, default: false },
})

// payment_terms is allow_on_submit: still editable after the Sales Order is
// submitted (the generic `locked`/canWrite freeze everything on docstatus 1).
const editableAfterSubmit = computed(
  () => props.detail.docstatus.value === 1 && !!props.detail.meta.resource.data?.perms?.write,
)
const disabled = computed(() => !(editableAfterSubmit.value || (!props.locked && props.detail.canWrite.value)))
const rows = computed(() => props.detail.values.payment_terms || [])
const soCurrency = computed(() => props.detail.values.currency || '')
const soTotal = computed(() =>
  Number(props.detail.values.disable_rounded_total ? props.detail.values.grand_total : props.detail.values.rounded_total || props.detail.values.grand_total) || 0,
)
const total = computed(() => rows.value.reduce((s, r) => s + (Number(r.amount) || 0), 0))
// "Add Row" only makes sense while there's still budget left to schedule -
// a new row always starts at 0 and would either sit stuck there or trip
// amountWithinBudget the instant it's given anything, so hide the action
// entirely once the terms already account for the full order total.
const hasRoom = computed(() => total.value < soTotal.value)

const CONDITION_OPTIONS = ['Number of Interviews', 'Number of Days', 'Not Applied']

const activeIdx = ref(null)
const expandedIdx = ref(null)
const isRowActive = (idx) => activeIdx.value === idx

// A row already in the verification pipeline (or already verified) is
// frozen - its condition/amount can't retroactively change what a
// Payment Entry was already raised against. Gated on payment_entry itself
// being set, not just the status text: a row with no linked Payment Entry
// yet has nothing to protect, so it must stay editable regardless of what
// payment_status happens to say.
function isRowReadOnly(row) {
  return !!row.payment_entry && ['Pending Verification', 'Verified'].includes(row.payment_status)
}
// A term that already has a Sales Invoice raised against it can't be edited or removed at
// all - only Mark as Paid / Re-request remain (canMarkAsPaid below looks at isRowReadOnly).
function isTermLocked(row) {
  return isRowReadOnly(row) || !!row.sales_invoice
}
function isConditionLocked(row) {
  return isTermLocked(row)
}

function activate(idx) {
  if (disabled.value || isTermLocked(rows.value[idx])) return
  activeIdx.value = activeIdx.value === idx ? null : idx
}
function toggleExpand(idx) {
  expandedIdx.value = expandedIdx.value === idx ? null : idx
}

// Once the document actually saves (isLoading true -> false with no
// error), every row drops back to its inactive/display state.
watch(
  () => props.detail.save?.isLoading,
  (loading, wasLoading) => {
    if (wasLoading && !loading) activeIdx.value = null
  },
)

function setRows(next) {
  props.detail.values.payment_terms = next
}

function addRow() {
  const remaining = Math.max(0, soTotal.value - total.value)
  const row = { payment_condition: '', counter: 0, amount: remaining, payment_status: 'Unpaid', so_currency: soCurrency.value }
  row.description = buildDescription(row)
  setRows([...rows.value, row])
  activeIdx.value = rows.value.length - 1
}
function removeRow(idx) {
  if (isTermLocked(rows.value[idx])) return
  const next = [...rows.value]
  next.splice(idx, 1)
  setRows(next)
}

function addDays(dateStr, days) {
  const d = new Date(`${dateStr}T00:00:00`)
  d.setDate(d.getDate() + Number(days || 0))
  return d.toISOString().slice(0, 10)
}
const today = () => new Date().toISOString().slice(0, 10)

// Decided Amount can never push the scheduled total past the order's own
// rounded_total - rejects the edit outright (row keeps its previous value)
// with a clear error, rather than silently clamping to whatever room is
// left, which just left the user wondering why their typed number didn't
// stick.
function amountWithinBudget(idx, value) {
  const others = rows.value.filter((_, i) => i !== idx).reduce((s, r) => s + (Number(r.amount) || 0), 0)
  const room = Math.max(0, soTotal.value - others)
  if ((Number(value) || 0) > room) {
    notify.error(
      `Total of Decided Amount in Payment Terms cannot be greater than the Sales Order total (${formatFieldValue(soTotal.value, { fieldtype: 'Currency' })}).`,
    )
    return false
  }
  return true
}

async function onChange(idx, fieldname, value) {
  if (isTermLocked(rows.value[idx])) return // an invoiced / verified term is never edited
  const next = rows.value.map((r) => ({ ...r }))
  const row = next[idx]
  row[fieldname] = value

  if (fieldname === 'payment_condition') {
    if (value === 'Not Applied') {
      Object.assign(row, { start_date: null, due_date: null, counter: 0, current_interview_count: 0 })
    } else if (value === 'Number of Days') {
      Object.assign(row, { due_date: null, current_interview_count: 0 })
    } else if (value === 'Number of Interviews') {
      row.start_date = null
      row.due_date = null
      const count = await call('verp_staffing.accounts.doctype.sales_order.sales_order.get_interview_count_for_customer', {
        customer: props.detail.values.customer,
      }).catch(() => 0)
      row.current_interview_count = count || 0
    }
  } else if (fieldname === 'counter') {
    if (row.payment_condition === 'Number of Days' && row.start_date) row.due_date = addDays(row.start_date, value)
  } else if (fieldname === 'start_date') {
    if (value && value < today()) {
      notify.error('Start date cannot be before today.')
      row.start_date = today()
    }
    if (row.payment_condition === 'Number of Days' && row.counter) row.due_date = addDays(row.start_date, row.counter)
  } else if (fieldname === 'amount') {
    if (!amountWithinBudget(idx, value)) return
    row.amount = Number(value) || 0
  }

  row.description = buildDescription(row)
  setRows(next)
}

// Ported from sales_order.js's update_payment_term_description - same
// wording, same three branches - but computed purely client-side (no
// separate API round-trip) on every relevant field change, and carried in
// with the row like any other field so it's whatever gets sent on the next
// actual save. Not user-editable any more (it never was on the desk form
// either): it's fully derived from the row's other fields.
function fmtAmount(value, currency) {
  return `${formatFieldValue(value, { fieldtype: 'Currency' })} ${currency || ''}`.trim()
}
function buildDescription(row) {
  if (!row.payment_condition) return row.description || ''

  const currency = row.so_currency || soCurrency.value
  const converted =
    row.currency && row.currency !== currency && row.received_amount ? ` (${fmtAmount(row.received_amount, row.currency)})` : ''
  const amountDisplay = `${fmtAmount(row.amount, currency)}${converted}`

  if (row.payment_condition === 'Not Applied') {
    return `Pay ${amountDisplay} - No condition applied (immediate or pre-paid)`
  }
  if (row.payment_condition === 'Number of Days') {
    const days = row.counter || '?'
    const start = row.start_date ? formatDate(row.start_date) : '?'
    const due = row.due_date ? formatDate(row.due_date) : 'not computed'
    return `Pay ${amountDisplay} after ${days} day(s) from ${start} - Due: ${due}`
  }
  const required = row.counter || '?'
  const current = row.current_interview_count != null ? row.current_interview_count : '…'
  const remaining = row.counter != null && row.current_interview_count != null ? Math.max(0, row.counter - row.current_interview_count) : '?'
  return `Pay ${amountDisplay} after ${required} interview(s) - Current: ${current}, Remaining: ${remaining}`
}

// ── Expanded row: every field, Description the only editable one ──────────
const EXPANDED_FIELDNAMES = [
  'payment_condition', 'counter', 'start_date', 'due_date', 'amount', 'received_amount',
  'payment_status', 'current_interview_count', 'company', 'so_currency', 'currency',
  'conversion_rate', 'sales_invoice', 'payment_entry', 'description',
]
const LABELS = {
  payment_condition: 'Condition', counter: 'Count', start_date: 'Start Date', due_date: 'Due Date',
  amount: 'Decided Amount', received_amount: 'Received Amount', payment_status: 'Status',
  current_interview_count: 'Current Interview Count', company: 'Company', so_currency: 'So Currency',
  currency: 'Invoice Currency', conversion_rate: 'Exchange Rate', sales_invoice: 'Sales Invoice',
  payment_entry: 'Payment Entry', description: 'Description',
}
const expandedColumns = EXPANDED_FIELDNAMES.map((fieldname) => ({ fieldname, label: LABELS[fieldname] }))
const CURRENCY_FIELDS = new Set(['amount', 'received_amount'])
const DATE_FIELDS = new Set(['start_date', 'due_date'])
function displayValue(row, col) {
  const v = row[col.fieldname]
  if (v === null || v === undefined || v === '') return '-'
  if (CURRENCY_FIELDS.has(col.fieldname)) return formatFieldValue(v, { fieldtype: 'Currency' })
  if (DATE_FIELDS.has(col.fieldname)) return formatDate(v) || '-'
  return String(v)
}

// _append_verification_log writes one "[<datetime>] <message>" line per
// event, newline-joined - split back out for one line per entry instead of
// a single run-on block of text.
function verificationLogLines(row) {
  return String(row.verification_log || '')
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

// ── Mark as Paid / Re-request (ported from the old PaymentTermsPanel) ─────
function canMarkAsPaid(row) {
  return !isRowReadOnly(row) && props.detail.docstatus.value === 1
}

const markAsPaidOpen = ref(false)
const markAsPaidRow = ref(null)
const rerequest = computed(() => markAsPaidRow.value?.payment_status === 'Rejected')
const form = reactive({ company: '', conversion_rate: 1, payer_account_name: '', reference_no: '', remarks: '', reference_date: '' })

const companyCurrency = useResource({ url: 'frappe.client.get_value', notifyOnError: false })
watch(
  () => form.company,
  (company) => company && companyCurrency.resource.submit({ doctype: 'Company', filters: company, fieldname: 'default_currency' }),
)
const targetCurrency = computed(() => companyCurrency.resource.data?.default_currency || soCurrency.value)
const foreign = computed(() => form.company && targetCurrency.value !== soCurrency.value)
const receivedPreview = computed(() =>
  foreign.value ? Number(markAsPaidRow.value?.amount || 0) * Number(form.conversion_rate || 0) : Number(markAsPaidRow.value?.amount || 0),
)

function openMarkAsPaid(row) {
  markAsPaidRow.value = row
  Object.assign(form, {
    // Sales Order hides `company` (set_only_once from ERP Configuration's
    // default) - get_doc_meta drops hidden fields from `values`, so the
    // real value only ever shows up under `hidden`.
    company: row.sales_invoice ? '' : props.detail.values.company || props.detail.hidden.company || '',
    conversion_rate: 1,
    payer_account_name: '',
    reference_no: '',
    remarks: '',
    reference_date: today(),
  })
  markAsPaidOpen.value = true
}

const markAsPaidValid = computed(
  () =>
    form.payer_account_name.trim() &&
    form.reference_no.trim() &&
    form.remarks.trim() &&
    form.reference_date &&
    (markAsPaidRow.value?.sales_invoice || form.company) &&
    (!foreign.value || Number(form.conversion_rate) > 0),
)

const create = useResource({ url: 'verp_staffing.accounts.doctype.sales_order.sales_order.create_payment_entry_from_term' })
const submittingMarkAsPaid = computed(() => create.isLoading)

async function submitMarkAsPaid() {
  const needsCompany = !markAsPaidRow.value.sales_invoice
  const result = await create.resource.submit({
    sales_order: props.name,
    payment_term_row: markAsPaidRow.value.name,
    reference_no: form.reference_no,
    reference_date: form.reference_date,
    remarks: form.remarks,
    payer_account_name: form.payer_account_name,
    company: needsCompany ? form.company : undefined,
    conversion_rate: needsCompany && foreign.value ? form.conversion_rate : undefined,
  })
  if (!result) return
  markAsPaidOpen.value = false
  notify.success(`Payment Entry ${result.payment_entry} submitted for verification.`)
  props.detail.refresh()
}
</script>
