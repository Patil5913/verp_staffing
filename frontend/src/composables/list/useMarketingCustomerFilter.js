import { ref } from 'vue'
import { call } from 'frappe-ui'

// Shared "which Marketing/Customer pairs am I looking at" selection for
// every Interview view (List/Kanban/Calendar) - ported from interview_
// list.js's window.InterviewMarketingFilter + ivw_ensure_marketing_param:
// one persisted selection (marketing_link values) all three views read and
// write through the same "Select Customer" dialog, defaulting to "every
// customer I'm assigned to" the first time, same as desk.
const ASSIGNED_CUSTOMERS_METHOD = 'verp_staffing.marketing.doctype.interview.interview.get_assigned_marketing_customers'
const STORAGE_KEY = 'verp-interview-marketing-customers'

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

const selectedCustomers = ref(readStored())

function setSelectedCustomers(values) {
  selectedCustomers.value = values || []
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedCustomers.value))
  } catch {
    // best-effort only
  }
}

// Seeds the selection with "every customer I'm assigned to" the first time
// a view opens with nothing chosen yet - mirrors desk's default-to-select-all.
let ensuring = null
async function ensureDefaultCustomers() {
  if (selectedCustomers.value.length) return selectedCustomers.value
  if (!ensuring) {
    ensuring = call(ASSIGNED_CUSTOMERS_METHOD)
      .then((rows) => {
        const values = (rows || []).map((r) => r.value)
        setSelectedCustomers(values)
        return values
      })
      .catch(() => [])
      .finally(() => {
        ensuring = null
      })
  }
  return ensuring
}

export function useMarketingCustomerFilter() {
  return { selectedCustomers, setSelectedCustomers, ensureDefaultCustomers }
}
