import { ref } from 'vue'
import { call } from 'frappe-ui'

// How many Payment Entries wait for verification — the same set the Pending Payment
// Requests page lists as "Pending Verification". Shared by every caller, fetched on first
// use and refreshed every minute; a user without access just gets 0 (the count call is
// refused), so no dot.
const count = ref(0)
let timer = null

async function refresh() {
  try {
    count.value =
      (await call('frappe.client.get_count', {
        doctype: 'Payment Entry',
        filters: [
          ['verification_status', '=', 'Pending Verification'],
          ['payment_term_row', 'is', 'set'],
          ['docstatus', '<', 2],
        ],
      })) || 0
  } catch {
    count.value = 0
  }
}

export function usePendingPaymentRequests() {
  if (!timer) {
    refresh()
    timer = setInterval(refresh, 60_000)
  }
  return { count, refresh }
}
