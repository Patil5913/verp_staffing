import { ref, watch } from 'vue'
import { call } from 'frappe-ui'

// Whether the current user may change Assign To on a saved record: the
// holder of the department's auto-assign role the record sits with, or
// anyone above them (server: can_change_assign_to). Always true for a new
// record; fails closed if the server can't answer.
export function useCanReassign(doctype, name, isNew, service) {
  const canReassign = ref(true)
  watch(
    [doctype, name, isNew],
    async ([dt, nm, fresh]) => {
      if (!dt || !nm || fresh) return (canReassign.value = true)
      canReassign.value = false
      try {
        const res = await call('verp_staffing.crm.api.helpers.can_change_assign_to_for_record', { doctype: dt, name: nm, service })
        canReassign.value = !!res?.allowed
      } catch {
        canReassign.value = false
      }
    },
    { immediate: true },
  )
  return canReassign
}
