import { createResource } from 'frappe-ui'

// ERP Configuration -> candidate_details_form_fields, loaded once and shared:
// each service (Item) may be flagged `is_agreement_required`.
const config = createResource({
  url: 'frappe.client.get_single_value',
  params: { doctype: 'ERP Configuration', field: 'candidate_details_form_fields' },
  // Not auto: this module loads with the app config bundle, possibly before the
  // session is usable — a fetch then would fail once and never retry.
  auto: false,
})
let requested = false
function ensureLoaded() {
  if (config.data !== null && config.data !== undefined) return
  if (config.loading || requested) return
  requested = true
  config.fetch()
}

function serviceFlags() {
  try {
    return JSON.parse(config.data || '{}') || {}
  } catch {
    return {}
  }
}

// sales_order.js's get_requirements_from_config().agreement_required, but read
// from the order as last SAVED (the meta snapshot the save response refreshes),
// not the live form — editing items doesn't change it until Save.
export function agreementRequired(detail) {
  ensureLoaded()
  const rows = detail.meta.resource.data?.tables?.find((t) => t.fieldname === 'items')?.rows || []
  const flags = serviceFlags()
  return rows.some((row) => {
    const c = flags[String(row.item || '').trim()]
    return c && !Array.isArray(c) && typeof c === 'object' && Boolean(c.is_agreement_required)
  })
}
