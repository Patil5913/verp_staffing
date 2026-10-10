<template>
  <SectionCard
    title="Party & Outstanding"
    :subtitle="refund ? 'Refund to a backed-out candidate - pay the bank account below.' : 'Pick a party to fill its account, then pull in what it owes.'"
  >
    <div class="flex flex-wrap items-center gap-x-6 gap-y-1 text-p-sm">
      <span class="text-app-text-muted">Party balance: <b class="text-app-text">{{ balanceText(info?.party_balance) }}</b></span>
      <span class="text-app-text-muted">Account balance: <b class="text-app-text">{{ balanceText(info?.account_balance) }}</b></span>
      <span v-if="loadingParty" class="text-app-text-muted">Loading…</span>
    </div>
    <!-- A refund entry: where the candidate wants the money, and what is actually being paid out -->
    <div v-if="refund" class="flex flex-col gap-3 rounded-lg border border-app-border bg-app-panel-2 p-4 text-p-sm">
      <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">
        Candidate bank account details - refund {{ values.refund_request }}
      </p>
      <dl class="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        <div v-for="row in bankRows" :key="row.label" class="flex flex-col">
          <dt class="text-p-xs text-app-text-muted">{{ row.label }}</dt>
          <dd class="break-words font-medium text-app-text" :class="row.mono ? 'tabular-nums' : ''">{{ row.value || '-' }}</dd>
        </div>
      </dl>
      <div class="border-t border-app-border pt-2">
        <div class="flex justify-between"><span class="text-app-text-muted">Refund amount</span><span class="tabular-nums">{{ money(refund.refund_amount) }}</span></div>
        <div class="flex justify-between"><span class="text-app-text-muted">Less: transaction fee recovered</span><span class="tabular-nums">- {{ money(refund.fee_recovered) }}</span></div>
        <div class="mt-1 flex justify-between border-t border-app-border pt-1 font-semibold"><span>Amount to pay the candidate</span><span class="tabular-nums">{{ money(refund.net_payout) }}</span></div>
      </div>
      <p v-if="refund.reason" class="text-p-xs text-app-text-muted">Reason: {{ refund.reason }}</p>
    </div>
    <div v-if="editable && !values.refund_request" class="flex flex-wrap gap-2">
      <AppButton variant="outline" size="sm" icon="file-text" :disabled="!ready" @click="openDialog(true)">Get Outstanding Invoices</AppButton>
      <AppButton variant="outline" size="sm" icon="shopping-cart" :disabled="!ready" @click="openDialog(false)">Get Outstanding Orders</AppButton>
    </div>

    <Dialog v-model="open" :options="{ title: fetchInvoices ? 'Get Outstanding Invoices' : 'Get Outstanding Orders', size: 'md' }">
      <template #body-content>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <AppInput type="date" label="From Date" v-model="filters.from_posting_date" />
          <AppInput type="date" label="To Date" v-model="filters.to_posting_date" />
          <AppInput type="number" label="Outstanding Greater Than" v-model="filters.outstanding_amt_greater_than" />
          <AppInput type="number" label="Outstanding Less Than" v-model="filters.outstanding_amt_less_than" />
          <div class="col-span-2"><AppCheckbox label="Allocate payment amount" v-model="filters.allocate_payment_amount" /></div>
        </div>
      </template>
      <template #actions>
        <AppButton :loading="fetching" @click="fetchOutstanding">Fetch</AppButton>
      </template>
    </Dialog>
  </SectionCard>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
import { siteTodayDate } from '@/utils/common/siteTime'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
// The client-side help the desk Payment Entry form gives while you fill it
// in (payment_entry.js): choosing a party fills its receivable/payable
// account, currency and name; choosing an account fills its currency;
// "Get Outstanding Invoices / Orders" pulls the party's open documents into
// the references table. Allocation totals themselves are recomputed by the
// server on save.
import { computed, reactive, ref, watch } from 'vue'
import { call, Dialog } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { formatFieldValue } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  locked: { type: Boolean, default: false },
})

const values = props.detail.values
const editable = computed(() => !props.locked && props.detail.canWrite.value)
const info = ref(null)
const loadingParty = ref(false)

// Only react to the user's own edits, not the values loading in from the
// server: a saved record's own party/accounts must never be overwritten.
const saved = () => props.detail.meta.resource.data?.values || {}

watch(
  () => [values.party, values.party_type, values.company, values.payment_type],
  async ([party, partyType, company, paymentType]) => {
    if (!editable.value || !(party && partyType && company && paymentType)) return
    if (party === saved().party && partyType === saved().party_type) return
    if (!values.posting_date) {
      notify.error('Please select Posting Date before selecting Party.')
      return
    }
    loadingParty.value = true
    try {
      const r = await call('verp_staffing.accounts.doctype.payment_entry.payment_entry.get_party_details', {
        company, party_type: partyType, party, date: values.posting_date,
      })
      info.value = r
      if (paymentType === 'Receive') {
        values.paid_from = r.party_account
        values.paid_from_account_currency = r.party_account_currency
      } else if (paymentType === 'Pay') {
        values.paid_to = r.party_account
        values.paid_to_account_currency = r.party_account_currency
      }
      values.party_name = r.party_name
      if (!values.currency) values.currency = r.party_account_currency
      values.references = []
    } catch (error) {
      notify.error(normalizeError(error).message)
    } finally {
      loadingParty.value = false
    }
  },
)

async function fillAccountCurrency(account, field) {
  if (!editable.value || !account || !values.posting_date || account === saved()[field.replace('_account_currency', '')]) return
  try {
    const r = await call('verp_staffing.accounts.doctype.payment_entry.payment_entry.get_account_details', {
      account, date: values.posting_date,
    })
    values[field] = r.account_currency
    if (!info.value) info.value = { account_balance: r.account_balance }
    else info.value.account_balance = r.account_balance
  } catch {
    // the server re-validates accounts on save
  }
}
watch(() => values.paid_from, (a) => fillAccountCurrency(a, 'paid_from_account_currency'))
watch(() => values.paid_to, (a) => fillAccountCurrency(a, 'paid_to_account_currency'))

// A refund payment entry carries its Refund Request: show the candidate's bank details and the net payout.
const refund = ref(null)
watch(
  () => values.refund_request,
  async (name) => {
    refund.value = null
    if (!name) return
    try {
      refund.value = await call('frappe.client.get_value', {
        doctype: 'Refund Request',
        filters: name,
        fieldname: [
          'account_holder_name', 'bank_name', 'account_number', 'routing_code', 'branch', 'bank_notes',
          'refund_amount', 'fee_recovered', 'net_payout', 'reason', 'currency',
        ],
      })
    } catch {
      refund.value = null // not allowed to read it, or gone: the remarks still carry the essentials
    }
  },
  { immediate: true },
)
const bankRows = computed(() => [
  { label: 'Account holder', value: refund.value?.account_holder_name },
  { label: 'Bank', value: refund.value?.bank_name },
  { label: 'Account number', value: refund.value?.account_number, mono: true },
  { label: 'IFSC / SWIFT / Routing code', value: refund.value?.routing_code },
  { label: 'Branch', value: refund.value?.branch },
  { label: 'Other details', value: refund.value?.bank_notes },
])
const money = (n) => `${formatFieldValue(n || 0, { fieldtype: 'Currency' })} ${refund.value?.currency || values.currency || ''}`.trim()

const balanceText = (n) => (n === undefined || n === null ? '-' : formatFieldValue(n, { fieldtype: 'Currency' }))

const ready = computed(() => values.company && values.party_type && values.party && values.payment_type)

const open = ref(false)
const fetchInvoices = ref(true)
const fetching = ref(false)
const filters = reactive({ from_posting_date: '', to_posting_date: '', outstanding_amt_greater_than: 0, outstanding_amt_less_than: '', allocate_payment_amount: true })

function openDialog(invoices) {
  fetchInvoices.value = invoices
  const today = siteTodayDate()
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  filters.from_posting_date = iso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 30))
  filters.to_posting_date = iso(today)
  open.value = true
}

async function fetchOutstanding() {
  fetching.value = true
  try {
    const args = {
      posting_date: values.posting_date,
      company: values.company,
      party_type: values.party_type,
      payment_type: values.payment_type,
      party: values.party,
      party_account: values.payment_type === 'Receive' ? values.paid_from : values.paid_to,
      ...filters,
      allocate_payment_amount: filters.allocate_payment_amount ? 1 : 0,
      [fetchInvoices.value ? 'get_outstanding_invoices' : 'get_orders_to_be_billed']: true,
    }
    const rows = await call('verp_staffing.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents', { args })
    values.references = (rows || []).map((d) => ({
      reference_doctype: d.voucher_type,
      reference_name: d.voucher_no,
      invoice_currency: d.currency,
      due_date: d.due_date,
      total_amount: d.invoice_amount,
      outstanding_amount: d.outstanding_amount,
      allocated_amount: filters.allocate_payment_amount ? d.allocated_amount : 0,
      exchange_rate: d.exchange_rate || 1,
    }))
    open.value = false
    if (!rows?.length) notify.info('Nothing outstanding for this party.')
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    fetching.value = false
  }
}
</script>
