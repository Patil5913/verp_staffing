<template>
  <div class="flex flex-col gap-4">
    <p v-if="!customer" class="rounded-xl border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      No customer selected.
    </p>
    <div v-else-if="orders.isLoading && !orders.resource.data" class="flex justify-center py-10">
      <LoadingIndicator class="h-5 w-5 text-app-text-muted" />
    </div>
    <p v-else-if="!(orders.resource.data || []).length" class="rounded-xl border border-dashed border-app-border px-3 md:px-6 py-8 text-center text-p-sm text-app-text-muted">
      No Sales Orders found. If you created one against this customer it may not be visible to you due to ownership permissions.
    </p>

    <SectionCard v-for="so in orders.resource.data" :key="so.name" :title="so.name" :subtitle="subtitle(so)">
      <template #actions>
        <DocStatusBadge :status="so.status" />
        <DocStatusBadge v-if="so.docstatus !== 1" :docstatus="so.docstatus" />
        <AppButton variant="outline" size="sm" icon="external-link" @click="router.push(`/Sales%20Order/${encodeURIComponent(so.name)}`)">
          Open
        </AppButton>
      </template>

      <div v-if="so.payment_terms.filter((t) => t.name).length" class="overflow-x-auto rounded-lg border border-app-border">
        <table class="w-full text-left text-p-sm">
          <thead class="bg-app-panel-2 text-p-xs text-app-text-muted">
            <tr>
              <th class="px-3 py-2 font-medium">#</th>
              <th class="px-3 py-2 font-medium">Condition</th>
              <th class="px-3 py-2 font-medium">Due</th>
              <th class="px-3 py-2 text-right font-medium">Amount</th>
              <th class="px-3 py-2 font-medium">Status</th>
              <th class="px-3 py-2 font-medium">Payment Entry</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in so.payment_terms.filter((t) => t.name)" :key="t.name" class="border-t border-app-border">
              <td class="px-3 py-1.5">{{ t.idx }}</td>
              <td class="px-3 py-1.5">{{ t.payment_condition || '—' }}</td>
              <td class="px-3 py-1.5">{{ formatDate(t.due_date) || '—' }}</td>
              <td class="px-3 py-1.5 text-right tabular-nums">{{ formatFieldValue(t.amount, { fieldtype: 'Currency' }) }}</td>
              <td class="px-3 py-1.5"><DocStatusBadge :status="t.payment_status" /></td>
              <td class="px-3 py-1.5">
                <router-link v-if="t.payment_entry" :to="`/Payment%20Entry/${encodeURIComponent(t.payment_entry)}`" class="text-app-primary hover:underline">
                  {{ t.payment_entry }}
                </router-link>
                <span v-else class="text-app-text-muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="text-p-sm text-app-text-muted">No payment terms on this order.</p>
    </SectionCard>
  </div>
</template>

<script setup>
// The customer's Sales Orders and their payment-term schedules — the "Sales
// Order" tab on CR / Onboardings / Customer (desk's render_owned_sales_orders),
// already scoped server-side to the orders the user is allowed to see.
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { useResource } from '@/composables/list/useResource'
import { formatDate, formatFieldValue } from '@/utils/list/formatValue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  customer: { type: String, default: '' },
  detail: { type: Object, default: null },
})

const router = useRouter()
const customer = computed(() => props.customer || props.detail?.values.customer || '')

const orders = useResource({
  url: 'verp_staffing.accounts.doctype.sales_order.sales_order.get_owned_sales_orders',
  notifyOnError: false,
})
watch(customer, (value) => value && orders.resource.submit({ customer: value }), { immediate: true })

const subtitle = (so) =>
  [formatDate(so.posting_date), so.grand_total != null ? `${so.currency || ''} ${formatFieldValue(so.grand_total, { fieldtype: 'Currency' })}` : '', `Owner: ${so.owner || '—'}`]
    .filter(Boolean)
    .join(' · ')
</script>
