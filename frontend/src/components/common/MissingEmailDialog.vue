<template>
  <Dialog v-model="show" :options="{ title: 'Email Missing', size: 'sm', icon: { name: 'mail', appearance: 'warning' } }">
    <template #body-content>
      <div class="flex flex-col gap-4">
        <p class="text-p-sm text-app-text-muted">{{ message }}</p>
        <AppInput label="Email" type="email" v-model="email" required @keydown.enter="onConfirm" />
      </div>
    </template>
    <template #actions>
      <AppButton icon="send" :loading="loading" :disabled="!email.trim()" @click="onConfirm">Save &amp; Continue</AppButton>
    </template>
  </Dialog>
</template>

<script setup>
// The recovery step for Sales Order's pre-submit checks (validate_
// candidate_form_requirements) and agreement.py's send_existing_agreement
// both throwing "Email is required to send ..." - instead of a dead-end
// error, this collects one, saves it to the customer's Lead Detail Form
// (customer.py's save_customer_email), and lets the caller retry whatever
// it was originally trying to do.
import { ref, watch } from 'vue'
import { Dialog, call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { notify } from '@/utils/common/notify'

const show = defineModel({ type: Boolean, default: false })
const props = defineProps({
  customer: { type: String, required: true },
  message: { type: String, default: 'This customer has no email on file yet - add one to continue.' },
})
const emit = defineEmits(['saved'])

const email = ref('')
const loading = ref(false)
watch(show, (open) => {
  if (open) email.value = ''
})

async function onConfirm() {
  const value = email.value.trim()
  if (!value) return
  loading.value = true
  try {
    await call('verp_staffing.crm.doctype.customer.customer.save_customer_email', { customer: props.customer, email: value })
    show.value = false
    emit('saved')
  } catch (e) {
    notify.error(e?.messages?.[0] || 'Failed to save the email.')
  } finally {
    loading.value = false
  }
}
</script>
