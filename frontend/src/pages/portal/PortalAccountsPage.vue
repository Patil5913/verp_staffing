<template>
  <div class="mx-auto flex max-w-5xl flex-col gap-5 px-3 py-5 md:px-6">
    <AppSkeleton v-if="!accounts" variant="block" height="14rem" />

    <template v-else>
      <!-- balance at a glance -->
      <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div v-for="t in tiles" :key="t.label" class="rounded-xl border border-app-border bg-app-panel p-4">
          <span class="block text-p-sm text-app-text-muted">{{ t.label }}</span>
          <span class="mt-1 block text-2xl font-bold text-app-text" :class="t.tone">{{ t.value }}</span>
        </div>
      </div>

      <!-- invoices -->
      <SectionCard title="Invoices" subtitle="Print any invoice as a PDF">
        <div class="mb-3"><AppTabs v-model="filter" :tabs="tabs" /></div>
        <StateBanner v-if="!shownInvoices.length" icon="receipt" title="No invoices here" :description="accounts.invoices.length ? 'Nothing matches this filter.' : 'Your invoices will appear here once they are issued.'" />
        <div v-else class="overflow-x-auto rounded-lg border border-app-border">
          <table class="w-full text-p-sm">
            <thead class="bg-app-panel-2 text-left text-2xs uppercase text-app-text-muted">
              <tr><th class="px-3 py-2">Invoice</th><th class="px-3 py-2">Date</th><th class="px-3 py-2">Due</th><th class="px-3 py-2 text-right">Total</th><th class="px-3 py-2 text-right">Balance</th><th class="px-3 py-2">Status</th><th class="px-3 py-2" /></tr>
            </thead>
            <tbody>
              <tr v-for="inv in shownInvoices" :key="inv.name" class="border-t border-app-border">
                <td class="whitespace-nowrap px-3 py-2 font-medium text-app-text">{{ inv.name }}</td>
                <td class="whitespace-nowrap px-3 py-2">{{ inv.posting_date }}</td>
                <td class="whitespace-nowrap px-3 py-2">{{ inv.due_date || '-' }}</td>
                <td class="whitespace-nowrap px-3 py-2 text-right">{{ money(inv.grand_total, inv.currency) }}</td>
                <td class="whitespace-nowrap px-3 py-2 text-right font-medium">{{ money(inv.outstanding_amount, inv.currency) }}</td>
                <td class="px-3 py-2"><AppBadge :label="inv.status" :theme="invoiceTheme(inv.status)" /></td>
                <td class="px-3 py-2 text-right"><AppButton variant="outline" size="sm" icon="printer" @click="print(inv.name)">Print</AppButton></td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      <!-- orders + signed agreements -->
      <SectionCard title="Orders & agreements" subtitle="Your signed agreement is available once it has been signed">
        <StateBanner v-if="!accounts.orders.length" icon="file-signature" title="No orders yet" />
        <div v-else class="overflow-x-auto rounded-lg border border-app-border">
          <table class="w-full text-p-sm">
            <thead class="bg-app-panel-2 text-left text-2xs uppercase text-app-text-muted">
              <tr><th class="px-3 py-2">Order</th><th class="px-3 py-2">Date</th><th class="px-3 py-2 text-right">Total</th><th class="px-3 py-2" /></tr>
            </thead>
            <tbody>
              <tr v-for="o in accounts.orders" :key="o.name" class="border-t border-app-border">
                <td class="whitespace-nowrap px-3 py-2 font-medium text-app-text">{{ o.name }}</td>
                <td class="whitespace-nowrap px-3 py-2">{{ o.posting_date }}</td>
                <td class="whitespace-nowrap px-3 py-2 text-right">{{ money(o.grand_total, o.currency) }}</td>
                <td class="px-3 py-2 text-right"><AppButton v-if="o.agreement_signed" variant="outline" size="sm" icon="download" @click="downloadAgreement(o.agreement)">Signed agreement</AppButton></td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AppBadge from '@/components/ui/AppBadge.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import AppTabs from '@/components/ui/AppTabs.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { usePortal } from '@/composables/portal/usePortal'
import { invoiceTheme, money } from '@/utils/portal/status'

const { accounts, loadAccounts, load } = usePortal()
onMounted(() => {
  load()
  loadAccounts()
})

const filter = ref('all')
const tabs = computed(() => {
  const inv = accounts.value?.invoices || []
  const n = (s) => inv.filter((i) => i.status === s).length
  return [
    { label: `All (${inv.length})`, value: 'all' },
    { label: `Pending (${n('Pending') + n('Overdue')})`, value: 'unpaid' },
    { label: `Paid (${n('Paid')})`, value: 'Paid' },
  ]
})
const shownInvoices = computed(() => {
  const inv = accounts.value?.invoices || []
  if (filter.value === 'unpaid') return inv.filter((i) => i.status !== 'Paid')
  return filter.value === 'all' ? inv : inv.filter((i) => i.status === filter.value)
})

const currency = computed(() => accounts.value?.invoices?.[0]?.currency || accounts.value?.orders?.[0]?.currency)
const tiles = computed(() => {
  const t = accounts.value?.totals || {}
  return [
    { label: 'Total billed', value: money(t.billed, currency.value) },
    { label: 'Paid', value: money(t.paid, currency.value), tone: 'text-green-600' },
    { label: 'Outstanding', value: money(t.outstanding, currency.value), tone: t.outstanding > 0 ? 'text-amber-600' : '' },
    { label: 'Overdue invoices', value: t.overdue || 0, tone: t.overdue ? 'text-red-600' : '' },
  ]
})

// plain navigations: the server prints or streams the file after checking it is this customer's
const print = (name) => {
  window.open(`/verp/portal/invoices/${encodeURIComponent(name)}/print`, '_blank', 'noopener')
}
const downloadAgreement = (name) => {
  window.location.href = `/verp/portal/agreements/${encodeURIComponent(name)}/download`
}
</script>
