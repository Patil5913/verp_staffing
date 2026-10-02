import { computed, reactive, ref } from 'vue'
import { call } from 'frappe-ui'
import { serviceBucket } from '@/utils/portal/status'

// The customer portal's store: one fetch of everything the pages show (the
// server derives the customer from the signed-in user, nothing is passed in),
// plus the interview list and the unread-message count.
const data = ref(null)
const loading = ref(false)
const error = ref('')
const interviews = ref([])
const interviewsLoaded = ref(false)
const unread = ref(0)
const accounts = ref(null)
const accountsLoading = ref(false)
const docNames = reactive({}) // field -> file name uploaded during this visit

async function load(force = false) {
  if (loading.value || (data.value && !force)) return
  loading.value = true
  error.value = ''
  try {
    data.value = await call('verp_staffing.www.customer.get_portal_data')
  } catch (e) {
    error.value = e?.messages?.[0] || e?.message || 'Could not load your portal.'
  } finally {
    loading.value = false
  }
}

async function loadInterviews(force = false) {
  if (interviewsLoaded.value && !force) return
  try {
    const history = await call('verp_staffing.www.customer.get_customer_history', { interview_limit: 200, interview_offset: 0 })
    interviews.value = history?.departments?.Interview || []
  } catch {
    interviews.value = []
  } finally {
    interviewsLoaded.value = true
  }
}

async function loadAccounts(force = false) {
  if (accountsLoading.value || (accounts.value && !force)) return
  accountsLoading.value = true
  try {
    accounts.value = await call('verp_staffing.crm.api.customer_portal.get_portal_accounts')
  } catch {
    accounts.value = { invoices: [], orders: [], totals: { billed: 0, paid: 0, outstanding: 0, pending: 0, overdue: 0 } }
  } finally {
    accountsLoading.value = false
  }
}

const MAX_UPLOAD_BYTES = 1 * 1024 * 1024 // the server checks again; this is the fast-fail path

// Replaces one of the customer's own documents. Throws an Error with a readable message.
async function uploadDocument(field, file) {
  if (file.size > MAX_UPLOAD_BYTES) throw new Error('File size must be under 1 MB.')
  const body = new FormData()
  body.append('file', file)
  body.append('field', field)
  const res = await fetch('/api/method/verp_staffing.www.customer.upload_lead_document', {
    method: 'POST',
    headers: { 'X-Frappe-CSRF-Token': window.csrf_token },
    body,
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok || json.message?.status !== 'success') {
    let message = 'Upload failed. Please try again.'
    try {
      message = JSON.parse(JSON.parse(json._server_messages)[0]).message
    } catch {
      // keep the generic message
    }
    throw new Error(message)
  }
  docNames[field] = file.name
}

async function refreshUnread() {
  if (!data.value?.chat_enabled) return
  try {
    unread.value = Number(await call('vruglechat.api.get_unread_total')) || 0
  } catch {
    // the count is a nicety
  }
}

// Every service record (Sales Orders and Interviews have their own pages)
const services = computed(() => {
  const departments = data.value?.history?.departments || {}
  const other = new Set(data.value?.other_service_doctypes || [])
  const technical = new Set(data.value?.technical_doctypes || [])
  const rows = []
  for (const [dept, records] of Object.entries(departments)) {
    if (dept === 'Sales Order' || dept === 'Interview') continue
    for (const rec of records || []) {
      rows.push({ dept, rec, title: other.has(dept) ? rec.service_name || dept : dept, isOther: other.has(dept), technical: technical.has(dept) })
    }
  }
  return rows
})
// the technical team's services get their own page, shown only when the customer has any
const technicalServices = computed(() => services.value.filter((s) => s.technical))
const generalServices = computed(() => services.value.filter((s) => !s.technical))

const counts = computed(() => {
  const c = { completed: 0, progress: 0, pending: 0, rework: 0 }
  for (const s of services.value) c[serviceBucket(s.rec.status)]++
  return c
})

const pendingCount = computed(() => (data.value?.feedback_rounds?.length || 0) + (data.value?.pending_feedback_items?.length || 0))

export function usePortal() {
  return { data, loading, error, load, interviews, interviewsLoaded, loadInterviews, unread, refreshUnread, services, technicalServices, generalServices, counts, pendingCount, accounts, accountsLoading, loadAccounts, uploadDocument, docNames }
}
