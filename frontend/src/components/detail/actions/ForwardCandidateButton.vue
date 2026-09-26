<template>
  <AppButton v-if="!hideButton" variant="outline" icon="arrow-right" @click="openDialog">Forward Candidate</AppButton>

  <Dialog v-model="open" :options="{ title: 'Forward Candidate', size: 'md' }">
    <template #body-content>
      <div v-if="loadingOptions" class="flex justify-center py-8">
        <LoadingIndicator class="h-5 w-5 text-app-text-muted" />
      </div>

      <StateBanner
        v-else-if="blocked"
        icon="alert-triangle"
        title="Forwarding not allowed"
        :description="`This customer is currently forwarded to ${activeIn.join(' and ')}. No further forwarding is allowed.`"
      />

      <StateBanner
        v-else-if="!options.length"
        icon="info"
        title="No services available"
        description="There's nowhere left to forward this candidate."
      />

      <div v-else class="flex flex-col gap-4">
        <div class="flex flex-col gap-1.5">
          <label class="text-p-sm font-medium text-app-text-muted">Service</label>
          <AppCombobox v-model="service" :options="options" placeholder="Select a service…" />
        </div>

        <div v-if="needsInterviewRound" class="flex flex-col gap-1.5">
          <label class="text-p-sm font-medium text-app-text-muted">Interview Round</label>
          <AppCombobox
            v-model="interviewRound"
            :options="interviewRoundOptions"
            :placeholder="interviewRoundOptions.length ? 'Select an interview round…' : 'No interview rounds scheduled yet'"
          />
        </div>

        <template v-if="isOnboarding">
          <div class="flex flex-col gap-1.5">
            <label class="text-p-sm font-medium text-app-text-muted">Select Interview</label>
            <AppCombobox
              v-model="interview"
              :options="interviewOptions"
              :placeholder="interviewOptions.length ? 'Select an interview…' : 'No interviews found'"
            />
          </div>
          <!-- Pre-filled from the customer's existing Lead Detail Form
          credentials (get_onboarding_credentials) and read-only, same as
          reusable.js's dialog - there's no separate "type it fresh" path,
          only verify what's already on file. -->
          <AppInput label="Candidate Email (Used For Marketing)" :model-value="email" disabled />
          <AppInput label="Email Password" :model-value="password" disabled />
        </template>

        <AppTextarea v-if="isCR" v-model="reasonForForwarding" label="Reason For Forwarding" />

        <AppTextarea v-model="note" :label="`Note${isRUC ? '' : ' (optional)'}`" />
      </div>
    </template>
    <template #actions>
      <AppButton v-if="!blocked && options.length" variant="primary" :disabled="!canSubmit" :loading="forwarding.isLoading" @click="onSubmit">
        Forward
      </AppButton>
    </template>
  </Dialog>
</template>

<script setup>
import AppTextarea from '@/components/ui/AppTextarea.vue'
// Shared "Forward Candidate" flow - every service record page (Training,
// Interview Support, Technical Other Services, Resume, RUC, JDC, Cover
// Letter, ...) exposes the same action (see add_forward_button in
// public/js/reusable.js). Covers the common branches (plain forward, RUC's
// required note, JDC/Interview Support's required interview round, CR's
// required reason, Onboarding's interview + read-only email/password
// pulled from the customer's existing Lead Detail Form credentials).
import { computed, ref, watch } from 'vue'
import { Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'
import { isValidEmail } from '@/utils/detail/fieldFormats'

const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  customer: { type: String, required: true },
  // What `forward_candidate` should record as the record this forward came
  // from - the service name shown on this page, not always == doctype
  // (Technical Other Services forwards under its `service` item's name).
  fromServiceName: { type: String, required: true },
  // Opened from a menu instead (via the exposed openDialog).
  hideButton: { type: Boolean, default: false },
})
const emit = defineEmits(['forwarded'])

const open = ref(false)
const blocked = ref(false)
const activeIn = ref([])
const options = ref([])
const service = ref('')
const note = ref('')
const reasonForForwarding = ref('')
const interviewRound = ref('')
const interviewRoundOptions = ref([])
const interview = ref('')
const interviewOptions = ref([])
const email = ref('')
const password = ref('')

const isRUC = computed(() => service.value === 'RUC')
const isCR = computed(() => service.value.toLowerCase() === 'cr')
const isOnboarding = computed(() => service.value.toLowerCase() === 'onboarding')
const needsInterviewRound = computed(() => ['JDC', 'Interview Support'].includes(service.value))

const canSubmit = computed(() => {
  if (!service.value) return false
  if (isRUC.value && !note.value.trim()) return false
  if (needsInterviewRound.value && !interviewRound.value) return false
  if (isCR.value && !reasonForForwarding.value.trim()) return false
  if (isOnboarding.value && (!interview.value || !email.value || !password.value || !isValidEmail(email.value))) return false
  return true
})

// Customer itself uses a different, simpler endpoint (no doctype/docname -
// it already knows it's forwarding *from* the Customer) with a plain-list
// return instead of the service version's {options: [...]} shape - desk's
// add_forward_button branches the same way on frm.doctype === "Customer".
const isCustomerDoctype = computed(() => props.doctype === 'Customer')
const departments = useResource({
  url: 'verp_staffing.crm.doctype.customer.customer.get_forwardable_departments_from_service',
  notifyOnError: false,
})
const customerDepartments = useResource({
  url: 'verp_staffing.crm.doctype.customer.customer.get_forwardable_departments',
  notifyOnError: false,
})
const loadingOptions = computed(() => departments.isLoading || customerDepartments.isLoading)

async function openDialog() {
  open.value = true
  blocked.value = false
  activeIn.value = []
  options.value = []
  service.value = ''
  note.value = ''
  reasonForForwarding.value = ''
  interviewRound.value = ''
  interviewRoundOptions.value = []
  interview.value = ''
  interviewOptions.value = []
  email.value = ''
  password.value = ''

  const res = isCustomerDoctype.value
    ? await customerDepartments.resource.submit({ customer: props.customer })
    : await departments.resource.submit({ doctype: props.doctype, docname: props.name })
  if (!res) return
  if (res.blocked) {
    blocked.value = true
    activeIn.value = res.active_in || []
    return
  }
  const rawOptions = Array.isArray(res) ? res : res.options || []
  options.value = rawOptions.filter((s) => s.toLowerCase() !== props.doctype.toLowerCase())
}

const interviews = useResource({
  url: 'verp_staffing.crm.api.auto_assign.get_customer_interviews',
  notifyOnError: false,
})

async function loadInterviewRounds() {
  interviewRound.value = ''
  const res = await interviews.resource.submit({ customer: props.customer, service: service.value.toLowerCase() })
  interviewRoundOptions.value = res || []
}

// Onboarding's own interview list (get_customer_interviews with
// service='onboarding' returns {label, value} per Interview, not per
// round) plus a pre-fill of whatever candidate email/password already sit
// on this customer's Lead Detail Form - reusable.js's toggle_fields
// onboarding branch, verified/edited here rather than typed from scratch.
const onboardingInterviews = useResource({
  url: 'verp_staffing.crm.api.auto_assign.get_customer_interviews',
  notifyOnError: false,
})
const credentials = useResource({
  url: 'verp_staffing.crm.doctype.customer.customer.get_onboarding_credentials',
  notifyOnError: false,
})
async function loadOnboardingFields() {
  interview.value = ''
  const [interviewRes, credRes] = await Promise.all([
    onboardingInterviews.resource.submit({ customer: props.customer, service: 'onboarding' }),
    credentials.resource.submit({ customer: props.customer }),
  ])
  interviewOptions.value = interviewRes || []
  email.value = credRes?.marketing_email_id || ''
  password.value = credRes?.marketing_email_password || ''
}

watch(service, (val) => {
  if (['JDC', 'Interview Support'].includes(val)) loadInterviewRounds()
  else if (val.toLowerCase() === 'onboarding') loadOnboardingFields()
})

const addingNote = useResource({
  url: 'verp_staffing.crm.api.notes.add_note',
  notifyOnError: false,
})

const forwarding = useResource({
  url: 'verp_staffing.crm.api.auto_assign.forward_candidate',
})

async function onSubmit() {
  const result = await forwarding.resource.submit({
    customer: props.customer,
    service: service.value,
    interview_round: interviewRound.value || null,
    interview: interview.value || null,
    email: email.value || null,
    password: password.value || null,
    reason_for_forwarding: reasonForForwarding.value || null,
    from_service_name: props.fromServiceName || null,
  })
  if (!result) return

  if (note.value.trim() && result.doctype && result.name) {
    await addingNote.resource.submit({
      reference_doctype: result.doctype,
      reference_name: result.name,
      current_doctype: props.doctype,
      note: note.value,
    })
  }

  notify.success(`Candidate forwarded for ${service.value}.`)
  open.value = false
  emit('forwarded')
}
defineExpose({ openDialog })
</script>
