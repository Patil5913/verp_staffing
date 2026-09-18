<template>
  <SectionCard title="Invoices" subtitle="One invoice is raised per payment term.">
    <p v-if="detail.isNew.value" class="py-4 text-center text-p-sm text-app-text-muted">Save the Sales Order first to see linked invoices.</p>
    <p v-else-if="!invoices.length && !loading" class="py-4 text-center text-p-sm text-app-text-muted">No invoices created yet.</p>
    <div v-else class="overflow-x-auto rounded-lg border border-app-border">
      <table class="w-full text-left text-p-sm">
        <thead class="bg-app-panel-2 text-p-xs text-app-text-muted">
          <tr>
            <th class="px-3 py-2 font-medium">Invoice</th>
            <th class="px-3 py-2 font-medium">Company</th>
            <th class="px-3 py-2 font-medium">Date</th>
            <th class="px-3 py-2 font-medium">Created By</th>
            <th class="px-3 py-2 text-right font-medium">Grand Total</th>
            <th class="px-3 py-2 text-right font-medium">Outstanding</th>
            <th class="px-3 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="inv in invoices" :key="inv.name" class="border-t border-app-border">
            <td class="px-3 py-2">
              <router-link :to="`/Sales%20Invoice/${encodeURIComponent(inv.name)}`" class="text-app-primary hover:underline">{{ inv.name }}</router-link>
            </td>
            <td class="px-3 py-2">{{ inv.company }}</td>
            <td class="px-3 py-2">{{ formatDate(inv.posting_date) }}</td>
            <td class="px-3 py-2">{{ inv.owner_fullname || inv.owner }}</td>
            <td class="px-3 py-2 text-right tabular-nums">{{ formatFieldValue(inv.grand_total, { fieldtype: 'Currency' }) }} {{ inv.currency }}</td>
            <td class="px-3 py-2 text-right tabular-nums">{{ formatFieldValue(inv.outstanding_amount, { fieldtype: 'Currency' }) }}</td>
            <td class="px-3 py-2"><DocStatusBadge :docstatus="inv.docstatus" /></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="hasMore" class="flex justify-center">
      <AppButton variant="outline" size="sm" :loading="loading" @click="loadPage">Load more</AppButton>
    </div>
  </SectionCard>
</template>

<script setup>
// Invoices raised from this Sales Order (sales_order.js's render_invoices_tab),
// paged 5 at a time via get_linked_invoices.
import { ref, watch } from 'vue'
import { call } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { formatDate, formatFieldValue } from '@/utils/list/formatValue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, required: true },
})

const PAGE = 5
const invoices = ref([])
const loading = ref(false)
const hasMore = ref(false)

async function loadPage() {
  loading.value = true
  try {
    const result = await call('verp_staffing.accounts.doctype.sales_order.sales_order.get_linked_invoices', {
      sales_order: props.name,
      limit_start: invoices.value.length,
      limit_page_length: PAGE,
    })
    invoices.value = [...invoices.value, ...(result?.invoices || [])]
    hasMore.value = Boolean(result?.has_more)
  } finally {
    loading.value = false
  }
}

watch(
  () => props.name,
  (name) => {
    invoices.value = []
    if (name && name !== 'new') loadPage()
  },
  { immediate: true },
)
</script>
