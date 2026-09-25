<template>
  <div class="flex h-full flex-col bg-app-bg">
    <SubNavbar title="Payment Verification">
      <template #left>
        <div class="inline-flex shrink-0 items-center rounded-full border border-app-border bg-app-panel-2 p-0.5">
          <button
            v-for="tab in TABS"
            :key="tab.status"
            type="button"
            class="inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-p-xs font-medium transition-colors"
            :class="tab.status === activeStatus ? 'bg-app-panel text-app-text shadow-sm' : 'text-app-text-muted hover:text-app-text'"
            @click="activeStatus = tab.status"
          >
            {{ tab.label }}
            <span class="rounded-full px-1.5 text-p-xs" :class="tab.status === activeStatus ? tab.badge : 'bg-app-panel'">{{ counts[tab.status] ?? 0 }}</span>
          </button>
        </div>
      </template>

      <AppSearchInput v-model="search" class="w-full" placeholder="Search party, entry or mode of payment">
      </AppSearchInput>

      <template #right>
        <AppButton variant="ghost" icon="refresh-cw" tooltip="Refresh" @click="reload" />
      </template>
    </SubNavbar>

    <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-3 md:px-6 py-4">
      <StateBanner
        v-if="rows.isPermissionError"
        icon="lock"
        title="Permission denied"
        description="You don't have access to view Payment Entry."
      />
      <StateBanner v-else-if="rows.hasError" icon="alert-triangle" title="Couldn't load payment entries" :description="rows.errorMessage" />
      <div v-else-if="rows.isLoading && !rows.resource.data" class="flex justify-center py-16">
        <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
      </div>

      <template v-else>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div v-for="card in summaryCards" :key="card.label" class="rounded-xl border border-app-border bg-app-panel p-4 shadow-sm">
            <p class="text-p-xs font-medium uppercase tracking-wide text-app-text-muted">{{ card.label }}</p>
            <p class="mt-1 text-2xl font-semibold tabular-nums text-app-text">{{ card.value }}</p>
            <p class="text-p-xs text-app-text-muted">{{ card.hint }}</p>
          </div>
        </div>

        <StateBanner
          v-if="!visible.length"
          :icon="activeStatus === 'Pending Verification' ? 'check-circle' : 'inbox'"
          :title="activeStatus === 'Pending Verification' ? 'Nothing pending' : 'No entries'"
          :description="emptyText"
        />

        <div v-else class="overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-sm">
          <table class="w-full table-fixed border-collapse text-left text-p-sm">
            <thead class="bg-app-panel-2 text-p-xs uppercase tracking-wide text-app-text-muted">
              <tr>
                <th class="h-10 px-4 font-semibold">Payment Entry</th>
                <th class="h-10 px-3 font-semibold">Party</th>
                <th class="h-10 w-32 px-3 font-semibold">Date</th>
                <th class="h-10 w-40 px-3 text-right font-semibold">Amount</th>
                <th class="h-10 w-36 px-3 font-semibold">Mode</th>
                <th class="h-10 w-52 px-3" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in visible"
                :key="row.name"
                class="cursor-pointer border-t border-app-border transition-colors hover:bg-app-panel-2"
                @click="router.push(`/Payment%20Entry/${encodeURIComponent(row.name)}`)"
              >
                <td class="px-4 py-3">
                  <p class="truncate font-medium text-app-primary">{{ row.name }}</p>
                  <p v-if="row.reference_no" class="truncate text-p-xs text-app-text-muted">Ref {{ row.reference_no }}</p>
                </td>
                <td class="truncate px-3 py-3 text-app-text">{{ row.party_name || row.party || '—' }}</td>
                <td class="px-3 py-3 text-app-text-muted">{{ formatDate(row.posting_date) }}</td>
                <td class="px-3 py-3 text-right font-medium tabular-nums text-app-text">
                  {{ formatFieldValue(row.paid_amount, { fieldtype: 'Currency' }) }}
                  <span class="text-p-xs font-normal text-app-text-muted">{{ row.currency }}</span>
                </td>
                <td class="truncate px-3 py-3 text-app-text-muted">{{ row.mode_of_payment || '—' }}</td>
                <td class="px-3 py-3" @click.stop>
                  <div v-if="row.verification_status !== 'Verified'" class="flex justify-end gap-2">
                    <AppButton size="sm" icon="check" @click="openVerify(row)">
                      Verify
                    </AppButton>
                    <AppButton
                      v-if="row.verification_status === 'Pending Verification'"
                      size="sm"
                      variant="danger"
                      icon="x"
                      :loading="reject.isLoading && actingOn === row.name"
                      @click="openReject(row.name)"
                    >
                      Reject
                    </AppButton>
                  </div>
                  <div v-else class="flex justify-end"><DocStatusBadge status="Verified" /></div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <Dialog v-model="verifyDialog.show" :options="{ title: `Submit ${actingOn}?`, size: 'md', icon: { name: 'check-circle', appearance: 'success' } }">
      <template #body-content>
        <div class="flex flex-col gap-4">
          <div v-html="verifyConfirmHtml" />
          <AppLinkField label="Paid From" doctype="Account" v-model="verifyDialog.paidFrom" :filters="paidFromFilters" />
          <AppLinkField label="Paid To" doctype="Account" v-model="verifyDialog.paidTo" :filters="paidToFilters" />

          <div class="flex flex-col gap-2 rounded-lg border border-app-border p-3">
            <AppInput label="Platform / Other Charges (optional)" type="number" v-model="verifyDialog.charges" placeholder="0" />
            <p class="text-p-xs text-app-text-muted">
              Enter a negative amount if charges were deducted from your end (e.g. -60), positive if the customer paid extra. Refer to the final received amount below.
            </p>
            <AppLinkField v-if="chargesAmount" label="Expense Account (required)" doctype="Account" v-model="verifyDialog.chargesAccount" :filters="chargesAccountFilters" />
            <div v-if="chargesAmount" class="rounded-md bg-app-panel-2 p-3 text-p-sm">
              <div class="flex justify-between"><span class="text-app-text-muted">Payment received</span><span>{{ money(paidAmount) }}</span></div>
              <div class="flex justify-between"><span class="text-app-text-muted">Charges</span><span :class="chargesAmount < 0 ? 'text-red-600' : 'text-green-600'">{{ chargesAmount > 0 ? '+' : '' }}{{ money(chargesAmount) }}</span></div>
              <div class="mt-1 flex justify-between border-t border-app-border pt-1 font-semibold"><span>Final received amount</span><span :class="finalAmount <= 0 ? 'text-red-600' : ''">{{ money(finalAmount) }}</span></div>
              <p v-if="finalAmount <= 0" class="mt-1 text-p-xs text-red-600">Charges cannot be larger than the amount paid.</p>
            </div>
          </div>
        </div>
      </template>
      <template #actions>
        <AppButton icon="check" :loading="verify.isLoading" @click="submitVerify">Submit</AppButton>
      </template>
    </Dialog>

    <Dialog v-model="rejectDialog.show" :options="{ title: `Reject ${actingOn}`, size: 'md' }">
      <template #body-content>
        <AppInput
          type="textarea"
          label="Remarks"
          v-model="rejectDialog.remarks"
          required
          description="Required — explains why this payment entry was rejected. It's added to the payment term's verification log."
        />
      </template>
      <template #actions>
        <AppButton variant="danger" icon="x" :loading="reject.isLoading" :disabled="!rejectDialog.remarks.trim()" @click="submitReject">
          Reject
        </AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppInput from '@/components/ui/AppInput.vue'
// Payment Verification queue (the old "Pending PE Requests" page): payment
// entries raised against a Sales Order's payment terms wait here to be
// verified — Verify submits the entry and marks the term verified, Reject
// needs a reason and sends it back. Same filters as the desk block (see
// fixtures/custom_html_block.json); the tabs add the Verified / Rejected
// history the desk page didn't have.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, FeatherIcon, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import { useResource } from '@/composables/list/useResource'
import { usePendingPaymentRequests } from '@/composables/layout/usePendingPaymentRequests'
import { formatDate, formatFieldValue } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'
import { paidAccountFilterFor } from '@/utils/detail/paymentAccounts'
import { paymentEntrySubmitConfirm, TAX_ACCOUNT_TYPES } from '@/configs/detail/accounts'

const router = useRouter()

const TABS = [
  { status: 'Pending Verification', label: 'Pending', badge: 'bg-orange-100 text-orange-700' },
  { status: 'Rejected', label: 'Rejected', badge: 'bg-red-100 text-red-700' },
  { status: 'Verified', label: 'Verified', badge: 'bg-green-100 text-green-700' },
]
const activeStatus = ref('Pending Verification')
const search = ref('')

const rows = useResource({
  url: 'frappe.client.get_list',
  params: {
    doctype: 'Payment Entry',
    filters: [
      ['verification_status', 'in', ['Pending Verification', 'Rejected', 'Verified']],
      ['payment_term_row', 'is', 'set'],
    ],
    fields: [
      'name', 'party', 'party_name', 'posting_date', 'paid_amount', 'currency', 'mode_of_payment',
      'reference_no', 'verification_status', 'modified',
      // Needed for the Verify dialog's Paid From/Paid To pickers — same
      // filter inputs Payment Entry's own detail page uses.
      'party_type', 'payment_type', 'company', 'paid_from', 'paid_to',
    ],
    order_by: 'modified desc',
    limit_page_length: 500,
  },
  auto: true,
})
const { refresh: refreshSidebarDot } = usePendingPaymentRequests()
// Reloading the queue also updates the sidebar's red dot right away.
const reload = () => {
  rows.resource.reload()
  refreshSidebarDot()
}

const all = computed(() => rows.resource.data || [])
const counts = computed(() => {
  const out = {}
  for (const r of all.value) out[r.verification_status] = (out[r.verification_status] || 0) + 1
  return out
})

const visible = computed(() => {
  const q = search.value.trim().toLowerCase()
  return all.value.filter(
    (r) =>
      r.verification_status === activeStatus.value &&
      (!q || [r.name, r.party, r.party_name, r.mode_of_payment, r.reference_no].some((v) => String(v ?? '').toLowerCase().includes(q))),
  )
})

const pendingTotal = computed(() =>
  all.value.filter((r) => r.verification_status === 'Pending Verification').reduce((sum, r) => sum + Number(r.paid_amount || 0), 0),
)
const oldestPending = computed(() => {
  const dates = all.value.filter((r) => r.verification_status === 'Pending Verification').map((r) => r.posting_date).sort()
  return dates[0] ? formatDate(dates[0]) : '—'
})
const summaryCards = computed(() => [
  { label: 'Awaiting verification', value: counts.value['Pending Verification'] ?? 0, hint: 'payment entries in the queue' },
  { label: 'Pending amount', value: formatFieldValue(pendingTotal.value, { fieldtype: 'Currency' }), hint: 'sum across pending entries' },
  { label: 'Oldest pending', value: oldestPending.value, hint: 'posting date' },
])

const emptyText = computed(
  () =>
    ({
      'Pending Verification': 'There are no payment entries waiting for verification.',
      Rejected: 'No rejected payment entries.',
      Verified: 'No verified payment entries yet.',
    })[activeStatus.value],
)

const actingOn = ref(null)

// Same submit-confirmation content as Payment Entry's own detail page
// (verify_payment_entry submits the entry, same as that page's Submit
// button), plus its Paid From/Paid To — filtered exactly the same way as
// there — so the verifier can confirm or correct them without leaving this
// queue.
const verifyDialog = ref({ show: false, paidFrom: '', paidTo: '', charges: '', chargesAccount: '' })
const chargesAmount = computed(() => Number(verifyDialog.value.charges) || 0)
const paidAmount = computed(() => Number(verifyingRow.value?.paid_amount) || 0)
const finalAmount = computed(() => paidAmount.value + chargesAmount.value)
const money = (v) => `${formatFieldValue(v, { fieldtype: 'Currency' })} ${verifyingRow.value?.currency || ''}`.trim()
// Same filter the Payment Entry's tax rows use for account_head.
const chargesAccountFilters = computed(() => ({
  account_type: ['in', TAX_ACCOUNT_TYPES],
  is_group: 0,
  disabled: 0,
  company: verifyingRow.value?.company,
}))
const verifyingRow = ref(null)
const verifyConfirmHtml = computed(() => (verifyingRow.value ? paymentEntrySubmitConfirm({ values: verifyingRow.value }) : ''))
const paidFromFilters = computed(() =>
  verifyingRow.value
    ? paidAccountFilterFor({
        partyType: verifyingRow.value.party_type,
        paymentType: verifyingRow.value.payment_type,
        company: verifyingRow.value.company,
        bankCashPaymentTypes: ['Pay', 'Internal Transfer'],
      }).filters
    : {},
)
const paidToFilters = computed(() =>
  verifyingRow.value
    ? paidAccountFilterFor({
        partyType: verifyingRow.value.party_type,
        paymentType: verifyingRow.value.payment_type,
        company: verifyingRow.value.company,
        bankCashPaymentTypes: ['Receive', 'Internal Transfer'],
      }).filters
    : {},
)

function openVerify(row) {
  actingOn.value = row.name
  verifyingRow.value = row
  verifyDialog.value = { show: true, paidFrom: row.paid_from || '', paidTo: row.paid_to || '', charges: '', chargesAccount: '' }
}

const verify = useResource({
  url: 'verp_staffing.accounts.doctype.sales_order.sales_order.verify_payment_entry',
  onSuccess() {
    notify.success(`${actingOn.value} verified.`)
    verifyDialog.value.show = false
    reload()
  },
})
function submitVerify() {
  if (chargesAmount.value) {
    if (!verifyDialog.value.chargesAccount) return notify.error('Select the expense account for the charges.')
    if (finalAmount.value <= 0) return notify.error('Charges cannot be larger than the amount paid.')
  }
  verify.resource.submit({
    charges: chargesAmount.value || undefined,
    charges_account: chargesAmount.value ? verifyDialog.value.chargesAccount : undefined,
    payment_entry: actingOn.value,
    paid_from: verifyDialog.value.paidFrom || undefined,
    paid_to: verifyDialog.value.paidTo || undefined,
  })
}

const reject = useResource({
  url: 'verp_staffing.accounts.doctype.sales_order.sales_order.reject_payment_entry',
  onSuccess() {
    notify.success(`${actingOn.value} rejected.`)
    rejectDialog.value.show = false
    reload()
  },
})
const rejectDialog = ref({ show: false, remarks: '' })
function openReject(name) {
  actingOn.value = name
  rejectDialog.value = { show: true, remarks: '' }
}
function submitReject() {
  if (!rejectDialog.value.remarks.trim()) return
  reject.resource.submit({ payment_entry: actingOn.value, remarks: rejectDialog.value.remarks.trim() })
}
</script>
