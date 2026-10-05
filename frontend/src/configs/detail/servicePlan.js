import { watch } from 'vue'

const num = (v) => Number(v) || 0

// Only services are sellable as a bundle item here, and the same item can't
// be added to a plan twice - same two rules (is_service + no duplicates
// within the table) Sales Order's own item rows use (see accounts.js's
// uniqueItemQuery), via the generic rowLinkQueries hook.
const serviceItemQuery = (row, rows, idx) => ({
  item: {
    filters: {
      is_service: 1,
      name: ['not in', (rows || []).filter((r, i) => i !== idx && r.item).map((r) => r.item)],
    },
  },
})

function servicePlanSetup(detail) {
  watch(
    () => detail.values.items,
    (items) => {
      detail.values.total_amount = (items || []).reduce((sum, row) => sum + num(row.rate), 0)
    },
    { deep: true, immediate: true },
  )
}

export const servicePlanConfig = {
  doctype: 'Service Plan',
  timeline: 'full',
  setup: servicePlanSetup,
  readOnlyFields: () => ['total_amount'],
  tabs: [
    {
      key: 'details',
      label: 'Details',
      sections: [
        { type: 'fields', title: 'Service Plan', fieldnames: ['title', 'is_active'] },
        { type: 'auto', fieldname: 'items', rowLinkQueries: serviceItemQuery },
        { type: 'fields', title: 'Total', fieldnames: ['total_amount'] },
      ],
    },
  ],
}
