<template>
  <AppButton v-if="required" variant="outline" icon="mail" :loading="sending" @click="send">Send Details Form</AppButton>
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
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

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

const sending = ref(false)
async function send() {
  sending.value = true
  try {
    const customer = props.detail.values.customer
    const recipient = await call('verp_staffing.crm.doctype.customer.customer.get_customer_email', { customer })
    if (!recipient) {
      notify.error('This customer has no email on their Lead Detail Form — add one before sending.')
      return
    }
    const ok = await call('verp_staffing.accounts.doctype.sales_order.sales_order.send_details_form_notification', {
      recipient,
      sales_order: props.name,
      customer,
    })
    if (!ok) notify.error('Failed to send the email — try again.')
    else notify.success('Details form sent successfully.')
  } catch (error) {
    notify.error(normalizeError(error).message)
  } finally {
    sending.value = false
  }
}
</script>
