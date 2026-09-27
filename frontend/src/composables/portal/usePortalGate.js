import { computed, ref } from 'vue'
import { call } from 'frappe-ui'

// Whether the candidate details form and/or a sent agreement are still
// pending for the signed-in customer. While either is true, the portal
// blocks every other tab (see CandidateFormGate.vue / PortalSidebar.vue)
// until both are cleared.
const mustFillForm = ref(false)
const mustSignAgreement = ref(false)
const checked = ref(false)

async function refresh() {
  const [formState, agreements] = await Promise.all([
    call('verp_staffing.www.candidate_details.get_lock_state').catch(() => null),
    call('verp_staffing.esign.portal.list_my_agreements').catch(() => []),
  ])
  mustFillForm.value = !!formState?.must_fill
  mustSignAgreement.value = (agreements || []).some((a) => a.needs_signature)
  checked.value = true
}

const blocked = computed(() => mustFillForm.value || mustSignAgreement.value)

const FORM_PATH = '/portal/candidate-details'
const AGREEMENTS_PREFIX = '/portal/agreements'

function isAllowedPath(path) {
  return path === FORM_PATH || path.startsWith(AGREEMENTS_PREFIX)
}

// Where the gate should send the customer: the form first, then agreements.
const gateTarget = computed(() => (mustFillForm.value ? FORM_PATH : AGREEMENTS_PREFIX))

export function usePortalGate() {
  return { mustFillForm, mustSignAgreement, blocked, checked, refresh, isAllowedPath, gateTarget }
}
