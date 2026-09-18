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

      <TextInput v-model="search" class="w-full" placeholder="Search party, entry or mode of payment">
        <template #prefix><FeatherIcon name="search" class="h-4 w-4 text-app-text-muted" /></template>
      </TextInput>

      <template #right>
        <Button variant="ghost" icon="refresh-cw" tooltip="Refresh" @click="reload" />
      </template>
    </SubNavbar>

    <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-6 py-4">
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
                    <AppButton size="sm" icon="check" :loading="verify.isLoading && actingOn === row.name" @click="onVerify(row.name)">
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

    <Dialog v-model="rejectDialog.show" :options="{ title: `Reject ${actingOn}`, size: 'md' }">
      <template #body-content>
        <FormControl
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
// Payment Verification queue (the old "Pending PE Requests" page): payment
// entries raised against a Sales Order's payment terms wait here to be
// verified — Verify submits the entry and marks the term verified, Reject
// needs a reason and sends it back. Same filters as the desk block (see
// fixtures/custom_html_block.json); the tabs add the Verified / Rejected
// history the desk page didn't have.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog, FeatherIcon, FormControl, LoadingIndicator, TextInput } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import SubNavbar from '@/components/common/SubNavbar.vue'
import { useResource } from '@/composables/list/useResource'
import { formatDate, formatFieldValue } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'

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
    ],
    order_by: 'modified desc',
    limit_page_length: 500,
  },
  auto: true,
})
const reload = () => rows.resource.reload()

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

const verify = useResource({
  url: 'verp_staffing.accounts.doctype.sales_order.sales_order.verify_payment_entry',
  onSuccess() {
    notify.success(`${actingOn.value} verified.`)
    reload()
  },
})
function onVerify(name) {
  actingOn.value = name
  verify.resource.submit({ payment_entry: name })
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
