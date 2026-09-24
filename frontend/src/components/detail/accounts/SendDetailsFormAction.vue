<template>
  <AppButton v-if="required" variant="outline" icon="mail" @click="onClick">Send Details Form</AppButton>
  <UnlockFormDialog v-if="required" v-model="showUnlock" :customer="customer" :sales-order="name" />
</template>

<script setup>
// sales_order.js's "Send > Send Details Form": offered only when one of the
// order's items is configured (ERP Configuration -> candidate_details_form_fields)
// as needing the candidate to fill a details form. Emails the customer the
// form link; a customer without an email on their Lead Detail Form can't be
// sent to.
import { computed, ref } from 'vue'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import UnlockFormDialog from '@/components/detail/customer/UnlockFormDialog.vue'
import { useResource } from '@/composables/list/useResource'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  name: { type: String, required: true },
})

const cfg = useResource({
  url: 'frappe.client.get_single_value',
  params: { doctype: 'ERP Configuration', field: 'candidate_details_form_fields' },
  notifyOnError: false,
  auto: true,
})

const required = computed(() => {
  let config = {}
  try {
    config = JSON.parse(cfg.resource.data || '{}')
  } catch {
    return false
  }
  return (props.detail.values.items || []).some((row) => {
    const c = config[String(row.item || '').trim()]
    return c && !Array.isArray(c) && typeof c === 'object' && Boolean(c.is_candidate_form_required)
  })
})

const showUnlock = ref(false)
const customer = computed(() => props.detail.values.customer)
const onClick = () => (showUnlock.value = true)
</script>
