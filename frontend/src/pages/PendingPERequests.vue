<template>
  <div class="mx-auto flex max-w-5xl flex-col gap-4 px-6 py-8">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-semibold text-app-text">Pending PE Requests</h1>
      <Button variant="ghost" icon="refresh-cw" @click="rows.resource.reload()" />
    </div>

    <StateBanner
      v-if="rows.isPermissionError"
      icon="lock"
      title="Permission denied"
      description="You don't have access to view Payment Entry."
    />
    <StateBanner
      v-else-if="rows.hasError"
      icon="alert-triangle"
      title="Couldn't load pending requests"
      :description="rows.errorMessage"
    />
    <div v-else-if="rows.isLoading && !rows.resource.data" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>
    <StateBanner
      v-else-if="!rows.resource.data?.length"
      icon="check-circle"
      title="Nothing pending"
      description="There are no payment entries waiting for verification."
    />

    <div v-else class="overflow-hidden rounded-lg border border-app-border bg-app-panel">
      <table class="w-full text-left text-p-base">
        <thead class="border-b border-app-border text-p-sm text-app-text-muted">
          <tr>
            <th class="px-4 py-2 font-medium">Payment Entry</th>
            <th class="px-4 py-2 font-medium">Party</th>
            <th class="px-4 py-2 font-medium">Posting Date</th>
            <th class="px-4 py-2 font-medium">Amount</th>
            <th class="px-4 py-2 font-medium">Mode</th>
            <th class="px-4 py-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows.resource.data"
            :key="row.name"
            class="border-b border-app-border last:border-0"
          >
            <td class="px-4 py-2 font-medium text-app-text">{{ row.name }}</td>
            <td class="px-4 py-2">{{ row.party_name || row.party }}</td>
            <td class="px-4 py-2">{{ formatDate(row.posting_date) }}</td>
            <td class="px-4 py-2">{{ row.paid_amount }} {{ row.currency }}</td>
            <td class="px-4 py-2">{{ row.mode_of_payment }}</td>
            <td class="px-4 py-2">
              <div class="flex justify-end gap-2">
                <Button
                  variant="outline"
                  theme="green"
                  :loading="verify.loading && actingOn === row.name"
                  @click="onVerify(row.name)"
                >
                  Verify
                </Button>
                <Button
                  variant="outline"
                  theme="red"
                  :loading="reject.loading && actingOn === row.name"
                  @click="openReject(row.name)"
                >
                  Reject
                </Button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Dialog v-model="rejectDialog.show" :options="{ title: 'Reject payment entry' }">
      <template #body-content>
        <FormControl
          type="textarea"
          label="Remarks"
          v-model="rejectDialog.remarks"
          required
          description="Required — explains why this payment entry was rejected."
        />
      </template>
      <template #actions>
        <Button
          variant="solid"
          theme="red"
          :loading="reject.loading"
          :disabled="!rejectDialog.remarks.trim()"
          @click="submitReject"
        >
          Reject
        </Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, Dialog, FormControl, LoadingIndicator } from 'frappe-ui'
import { useResource } from '@/composables/list/useResource'
import { formatDate } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'
import StateBanner from '@/components/common/StateBanner.vue'

// Mirrors the filters the existing "Pending PE Requests" Custom HTML Block
// uses (see verp_staffing/fixtures/custom_html_block.json) so this page
// shows exactly the same queue.
const rows = useResource({
  url: 'frappe.client.get_list',
  params: {
    doctype: 'Payment Entry',
    filters: [
      ['verification_status', '=', 'Pending Verification'],
      ['payment_term_row', 'is', 'set'],
    ],
    fields: ['name', 'party', 'party_name', 'posting_date', 'paid_amount', 'currency', 'mode_of_payment', 'modified'],
    order_by: 'modified desc',
    limit_page_length: 100,
  },
  auto: true,
})

const actingOn = ref(null)

const verify = useResource({
  url: 'verp_staffing.accounts.doctype.sales_order.sales_order.verify_payment_entry',
  onSuccess() {
    notify.success(`${actingOn.value} verified.`)
    rows.resource.reload()
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
    rows.resource.reload()
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
