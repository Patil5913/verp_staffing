<template>
  <AppButton variant="outline" icon="shopping-cart" @click="router.push(`/Sales%20Order/new?customer=${encodeURIComponent(detail.values.customer)}`)">
    Create Sales Order
  </AppButton>
</template>

<script setup>
// desk's `frappe.new_doc("Sales Order", { customer })` — opens a new Sales
// Order with the customer prefilled (useDocDetail applies the query string).
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'

defineOptions({ inheritAttrs: false })
defineProps({ detail: { type: Object, required: true } })
const router = useRouter()
</script>
