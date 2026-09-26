<template>
  <div class="flex flex-col gap-6">
    <p v-if="loading" class="py-6 text-center text-p-sm text-app-text-muted">Loading…</p>
    <p v-else-if="!orders.length" class="rounded-xl border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      Create a Sales Order first - agreements are raised against an order.
    </p>
    <template v-else>
      <div class="flex max-w-md flex-col gap-1.5">
        <label class="text-p-sm font-medium text-app-text-muted">Sales Order</label>
        <AppCombobox v-model="selected" :options="options" placeholder="Select a Sales Order" />
      </div>
      <AgreementPanel v-if="selected" :key="selected" :name="selected" :customer="customer" :can-create="canCreate" />
    </template>
  </div>
</template>

<script setup>
// Agreements live on the customer: pick one of their Sales Orders, then create / send / track its
// agreements (E Sign documents built from a Pdf Agreement Template) with AgreementPanel.
import { computed, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import AgreementPanel from '@/components/detail/accounts/AgreementPanel.vue'

defineOptions({ inheritAttrs: false })
const props = defineProps({ customer: { type: String, required: true } })

const orders = ref([])
const selected = ref('')
const loading = ref(true)
const options = computed(() => orders.value.map((o) => ({ label: `${o.name} · ${o.status || 'Draft'}`, value: o.name })))
const canCreate = computed(() => orders.value.find((o) => o.name === selected.value)?.docstatus !== 2)

watch(
  () => props.customer,
  async (customer) => {
    loading.value = true
    try {
      orders.value = (await call('frappe.client.get_list', {
        doctype: 'Sales Order',
        filters: { customer, docstatus: ['<', 2] },
        fields: ['name', 'status', 'docstatus'],
        order_by: 'creation desc',
        limit_page_length: 100,
      })) || []
      selected.value = orders.value[0]?.name || ''
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)
</script>
