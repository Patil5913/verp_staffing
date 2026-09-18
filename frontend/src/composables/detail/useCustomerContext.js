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

  const fields = computed(() => {
    if (fixedFields?.value) return fixedFields.value
    let config = {}
    try {
      config = JSON.parse(displayFields.resource.data || '{}')
    } catch {
      config = {}
    }
    const wanted = String(displayKey.value || '').toLowerCase()
    const key = Object.keys(config).find((k) => k.toLowerCase() === wanted)
    return key && Array.isArray(config[key]) ? config[key] : []
  })

  const records = useResource({
    url: 'verp_staffing.quota.utils.customer_data.get_data_by_customer',
    notifyOnError: false,
  })

  watch(
    [customerRef, fields],
    ([customer, list]) => {
      if (customer && list.length) records.resource.submit({ customer, fields: list })
    },
    { immediate: true },
  )

  return { fields, displayFields, records }
}
