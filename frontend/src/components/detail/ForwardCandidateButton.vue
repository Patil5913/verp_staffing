<template>
  <AppButton variant="outline" icon="arrow-right" @click="openDialog">Forward Candidate</AppButton>

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

        <div v-if="isCR" class="flex flex-col gap-1.5">
          <label class="text-p-sm font-medium text-app-text-muted">Reason For Forwarding</label>
          <textarea
            v-model="reasonForForwarding"
            rows="3"
            class="w-full resize-none rounded-lg border border-app-border bg-app-panel px-3 py-1.5 text-p-sm text-app-text focus:border-app-primary focus:outline-none focus:ring-2 focus:ring-app-primary/20"
          />
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="text-p-sm font-medium text-app-text-muted">
            Note{{ isRUC ? '' : ' (optional)' }}
          </label>
          <textarea
            v-model="note"
            rows="3"
            class="w-full resize-none rounded-lg border border-app-border bg-app-panel px-3 py-1.5 text-p-sm text-app-text focus:border-app-primary focus:outline-none focus:ring-2 focus:ring-app-primary/20"
          />
        </div>
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
// Shared "Forward Candidate" flow — every service record page (Training,
// Interview Support, Technical Other Services, Resume, RUC, JDC, Cover
// Letter, ...) exposes the same action (see add_forward_button in
// public/js/reusable.js). Covers the common branches (plain forward, RUC's
// required note, JDC/Interview Support's required interview round, CR's
// required reason) — Onboarding's extra email/password credential capture
// is deliberately not ported here; forwarding to Onboarding still works,
// just without pre-filling/collecting those fields.
import { computed, ref, watch } from 'vue'
import { Dialog, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import AppCombobox from '@/components/common/AppCombobox.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useResource } from '@/composables/list/useResource'
import { notify } from '@/utils/common/notify'

const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  customer: { type: String, required: true },
  // What `forward_candidate` should record as the record this forward came
  // from — the service name shown on this page, not always == doctype
  // (Technical Other Services forwards under its `service` item's name).
  fromServiceName: { type: String, required: true },
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

const isRUC = computed(() => service.value === 'RUC')
const isCR = computed(() => service.value.toLowerCase() === 'cr')
const needsInterviewRound = computed(() => ['JDC', 'Interview Support'].includes(service.value))

const canSubmit = computed(() => {
  if (!service.value) return false
  if (isRUC.value && !note.value.trim()) return false
  if (needsInterviewRound.value && !interviewRound.value) return false
  if (isCR.value && !reasonForForwarding.value.trim()) return false
  return true
})

const departments = useResource({
  url: 'verp_staffing.crm.doctype.customer.customer.get_forwardable_departments_from_service',
  notifyOnError: false,
})
const loadingOptions = computed(() => departments.isLoading)

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

  const res = await departments.resource.submit({ doctype: props.doctype, docname: props.name })
  if (!res) return
  if (res.blocked) {
    blocked.value = true
    activeIn.value = res.active_in || []
    return
  }
  options.value = (res.options || []).filter((s) => s.toLowerCase() !== props.doctype.toLowerCase())
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

watch(service, (val) => {
  if (['JDC', 'Interview Support'].includes(val)) loadInterviewRounds()
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
</script>
