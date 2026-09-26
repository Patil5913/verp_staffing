<template>
  <div class="flex flex-col gap-6">
    <SectionCard title="Agreements" :subtitle="`${cards.length} ${cards.length === 1 ? 'agreement' : 'agreements'}`">
      <template #actions>
        <AppButton variant="outline" size="sm" icon="refresh-cw" :loading="loadingCards" @click="loadCards">Refresh</AppButton>
      </template>

      <p v-if="!cards.length && !loadingCards" class="rounded-lg border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
        No agreements created yet.
      </p>

      <div v-else class="flex flex-col gap-3">
        <div v-for="ag in cards" :key="ag.name" class="flex flex-col gap-2 rounded-lg border border-app-border bg-app-panel-2/40 p-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <router-link :to="`/${encodeURIComponent(ag.kind === 'E Sign' ? 'E Sign' : 'Agreement')}/${encodeURIComponent(ag.name)}`" class="text-p-sm font-medium text-app-primary hover:underline">{{ ag.name }}</router-link>
              <p class="text-p-xs text-app-text-muted">Template: <span class="text-app-text">{{ ag.template || '-' }}</span></p>
            </div>
            <DocStatusBadge :status="ag.status || 'Draft'" />
          </div>

          <div v-if="ag.kind === 'E Sign' && ag.signers?.length" class="flex flex-wrap items-center gap-x-4 gap-y-1 text-p-xs text-app-text-muted">
            <span v-for="s in ag.signers" :key="s.email" class="inline-flex items-center gap-1.5">
              {{ s.email }} <DocStatusBadge :status="s.signed ? 'Signed' : 'Pending'" />
            </span>
          </div>
          <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-p-xs text-app-text-muted">
            <template v-if="ag.email_status">
              <span class="inline-flex items-center gap-1.5">Email <DocStatusBadge :status="ag.email_status" /></span>
              <span>{{ formatDatetime(ag.email_modified) }}</span>
              <span v-if="ag.email_error" class="text-red-600">{{ ag.email_error }}</span>
            </template>
            <span v-else>Email: not sent</span>
          </div>

          <div class="flex flex-wrap gap-2">
            <a v-if="ag.pdf" :href="ag.pdf" target="_blank" rel="noopener">
              <AppButton variant="outline" size="sm" icon="file-text">View PDF</AppButton>
            </a>
            <template v-if="ag.status !== 'Agreement signed' && ag.status !== 'Fully Signed'">
              <AppButton v-if="ag.can_resend || !ag.email_status" size="sm" icon="send" :loading="sendingName === ag.name" @click="send(ag)">
                {{ ag.email_status ? 'Resend Email' : 'Send Email' }}
              </AppButton>
              <AppButton v-else size="sm" variant="outline" disabled>Resend available in {{ remaining(ag.resend_after) }}</AppButton>
            </template>
          </div>
        </div>
      </div>
    </SectionCard>

    <SectionCard v-if="canCreate" title="Create Agreement" :subtitle="`Fill a template for ${name}.`">
      <TemplateFillForm ref="form" />
      <div v-if="hasTemplate" class="flex flex-wrap gap-2">
        <AppButton icon="save" :loading="saving && !sendAfter" :disabled="saving" @click="create(false)">Save</AppButton>
        <AppButton variant="outline" icon="send" :loading="saving && sendAfter" :disabled="saving" @click="create(true)">Save &amp; Send</AppButton>
      </div>
    </SectionCard>

    <MissingEmailDialog v-model="missingEmailOpen" :customer="customer" @saved="onEmailSaved" />
  </div>
</template>

<script setup>
// The Agreements panel for one Sales Order, shown on the Customer's Agreements tab. Agreements are E Sign documents built from
// a Pdf Agreement Template (TemplateFillForm): the template's values are filled
// into the PDF and its Signature slots become the customer's signer fields, so
// signing, OTP, audit trail and certificate all come from the E Sign engine.
// Agreements created before that (kind: 'Agreement') still list and resend as before.
import { computed, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import MissingEmailDialog from '@/components/common/MissingEmailDialog.vue'
import TemplateFillForm from '@/components/detail/esign/TemplateFillForm.vue'
import { formatDatetime } from '@/utils/list/formatValue'
import { notify } from '@/utils/common/notify'
import { isEmailMissingError, normalizeError } from '@/utils/common/errors'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  // The Sales Order the agreements belong to (used from the Customer's Agreements tab).
  name: { type: String, required: true },
  customer: { type: String, default: '' },
  canCreate: { type: Boolean, default: true },
})

const cards = ref([])
const loadingCards = ref(false)
async function loadCards() {
  if (!props.name) return
  loadingCards.value = true
  try {
    cards.value = (await call('verp_staffing.esign.template_flow.get_sales_order_agreements', { sales_order: props.name })) || []
  } finally {
    loadingCards.value = false
  }
}
watch(() => props.name, loadCards, { immediate: true })

function remaining(seconds) {
  if (seconds <= 0) return 'now'
  const mins = Math.floor(seconds / 60)
  return mins > 0 ? `${mins} min${mins > 1 ? 's' : ''}` : `${seconds % 60} sec`
}

const sendingName = ref('')
async function send(ag) {
  sendingName.value = ag.name
  try {
    if (ag.kind === 'E Sign') {
      await call('verp_staffing.esign.doctype.e_sign.e_sign.send_all_signers', { agreement: ag.name })
      notify.success('Agreement sent.')
    } else {
      const r = await call('verp_staffing.crm.api.agreement.send_existing_agreement', { agreement: ag.name })
      if (r?.success) notify.success('Agreement sent.')
      else notify.error('Failed to send the agreement.')
    }
    loadCards()
  } catch (error) {
    if (isEmailMissingError(error)) openMissingEmail(() => send(ag))
    else notify.error(normalizeError(error).message)
  } finally {
    sendingName.value = ''
  }
}

// Collects the customer's email when it's missing, then re-runs what was blocked.
const missingEmailOpen = ref(false)
const missingEmailRetry = ref(null)
function openMissingEmail(retry) {
  missingEmailRetry.value = retry
  missingEmailOpen.value = true
}
function onEmailSaved() {
  missingEmailRetry.value?.()
}

const form = ref(null)
const hasTemplate = computed(() => !!form.value?.template)
const saving = ref(false)
const sendAfter = ref(false)
async function create(send) {
  saving.value = true
  sendAfter.value = send
  try {
    const r = await call('verp_staffing.esign.template_flow.create_from_template', {
      sales_order: props.name,
      template: form.value.template,
      data: form.value.payload(),
      send: send ? 1 : 0,
    })
    notify.success(send ? 'Agreement created and sent.' : 'Agreement created.')
    if (r?.portal_access === 'granted') notify.success('The customer had no portal access, so it was sent to them - they can sign from their portal.')
    else if (r?.portal_access === 'failed') notify.error(`Couldn't give the customer portal access (${r.portal_access_error}). They will get an emailed signing link instead.`)
    form.value.reset()
    loadCards()
  } catch (error) {
    // Nothing was created (the E Sign is only made once the email is known), so retrying is safe.
    if (isEmailMissingError(error)) openMissingEmail(() => create(send))
    else notify.error(normalizeError(error).message)
  } finally {
    saving.value = false
  }
}
</script>
