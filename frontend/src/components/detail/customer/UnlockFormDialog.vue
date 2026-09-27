<template>
  <Dialog v-model="open" :options="{ title: 'Unlock Candidate Form', size: 'md' }">
    <template #body-content>
      <div class="flex flex-col gap-3 text-p-sm text-app-text">
        <p>
          The candidate form will become open for the candidate, and the customer can fill in their details from the portal.
          They'll get an email with a link to the form.
        </p>
        <p v-if="!loading && !hasAccess" class="text-app-text-muted">This customer doesn't have portal access yet - it'll be created for them automatically when you send.</p>
        <p v-if="recipient" class="text-app-text-muted">Email will be sent to <b class="text-app-text">{{ recipient }}</b>.</p>
        <p v-else-if="!loading" class="text-red-600">This customer has no email on their Lead Detail Form - add one before sending.</p>
      </div>
    </template>
    <template #actions>
      <AppButton icon="send" :loading="sending" :disabled="!recipient" @click="send">Send Email</AppButton>
    </template>
  </Dialog>
  <MissingEmailDialog v-model="showMissing" :customer="customer" @saved="open = true" />
</template>

<script setup>
// "Unlock Form": reopens a customer's candidate form (Customer.lock_form ->
// 0, done by send_details_form_notification itself) and emails them the
// portal link. Shared by the Customer page and the Sales Order button.
import { ref, watch } from 'vue'
import { call, Dialog } from 'frappe-ui'
import MissingEmailDialog from '@/components/common/MissingEmailDialog.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

const open = defineModel({ type: Boolean, default: false })
const props = defineProps({
  customer: { type: String, required: true },
  salesOrder: { type: String, default: '' },
})
const emit = defineEmits(['sent'])

const recipient = ref('')
const loading = ref(false)
const sending = ref(false)
const hasAccess = ref(true)
const showMissing = ref(false)

async function checkAccess() {
  const r = await call('frappe.client.get_value', { doctype: 'Customer', filters: props.customer, fieldname: 'chat_access' }).catch(() => null)
  hasAccess.value = r?.chat_access === 'Active'
}

watch(open, async (isOpen) => {
  if (!isOpen) return
  recipient.value = ''
  loading.value = true
  try {
    await checkAccess()
    recipient.value = (await call('verp_staffing.crm.doctype.customer.customer.get_customer_email', { customer: props.customer })) || ''
    // No email on file: collect one (saved to the Lead Detail Form), then return here.
    if (!recipient.value) {
      open.value = false
      showMissing.value = true
    }
  } catch {
    recipient.value = ''
  } finally {
    loading.value = false
  }
})

async function send() {
  sending.value = true
  try {
    const r = await call('verp_staffing.accounts.doctype.sales_order.sales_order.send_details_form_notification', {
      recipient: recipient.value,
      sales_order: props.salesOrder || '',
      customer: props.customer,
    })
    notify.success('Form unlocked and email sent.')
    if (r?.portal_access === 'granted') notify.success('The customer had no portal access, so it was given to them - they can fill the form from their portal.')
    else if (r?.portal_access === 'failed') notify.error(`Couldn't give the customer portal access (${r.portal_access_error}). They will get the emailed form link instead.`)
    open.value = false
    emit('sent')
  } catch (e) {
    notify.error(normalizeError(e).message)
  } finally {
    sending.value = false
  }
}
</script>
