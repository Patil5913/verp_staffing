import { computed, watch } from 'vue'
import { useResource } from '@/composables/list/useResource'

// Shared plumbing for the two "customer context" panels service records
// show (CustomerContextPanel / CustomerHistoryPanel). Mirrors the desk
// helpers in public/js/reusable.js: get_display_fields() reads the
// department -> fieldnames allowlist off ERP Configuration, and
// render_customer_related_html() feeds it to get_data_by_customer.
export function useCustomerContext(customerRef, displayKey, fixedFields) {
  const displayFields = useResource({
    url: 'frappe.client.get_single_value',
    params: { doctype: 'ERP Configuration', field: 'department_display_form_fields' },
    notifyOnError: false,
    // A fixed list needs no ERP Configuration lookup at all.
    auto: !fixedFields?.value,
  })

  // Same allowlist shape, but the editable side — a field configured here
  // renders as an upload/edit control instead of a readonly value (see
  // detail_view.py's department_access_form_fields, used the same way by
  // Lead/Opportunity/Customer's Candidate Profile tab).
  const accessFields = useResource({
    url: 'frappe.client.get_single_value',
    params: { doctype: 'ERP Configuration', field: 'department_access_form_fields' },
    notifyOnError: false,
    auto: !fixedFields?.value,
  })

  function lookup(resource) {
    let config = {}
    try {
      config = JSON.parse(resource.resource.data || '{}')
    } catch {
      config = {}
    }
    const wanted = String(displayKey.value || '').toLowerCase()
    const key = Object.keys(config).find((k) => k.toLowerCase() === wanted)
    return key && Array.isArray(config[key]) ? config[key] : []
  }

  const fields = computed(() => (fixedFields?.value ? fixedFields.value : lookup(displayFields)))
  const writableFields = computed(() => (fixedFields?.value ? [] : lookup(accessFields)))

  const records = useResource({
    url: 'verp_staffing.quota.utils.customer_data.get_data_by_customer',
    notifyOnError: false,
  })

  // A field configured as access (editable) should show even if it isn't
  // also in the display allowlist — merge both lists for the actual fetch.
  const fetchFields = computed(() => [...new Set([...fields.value, ...writableFields.value])])

  watch(
    [customerRef, fetchFields],
    ([customer, list]) => {
      if (customer && list.length) records.resource.submit({ customer, fields: list })
    },
    { immediate: true },
  )

  return { fields, writableFields, displayFields, records }
}
