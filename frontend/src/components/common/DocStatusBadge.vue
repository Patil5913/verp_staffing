<template>
  <AppBadge v-if="label" :theme="theme">{{ label }}</AppBadge>
</template>

<script setup>
import AppBadge from '@/components/ui/AppBadge.vue'
// The status pill shown beside a record's title / in list-like panels. For a
// submittable doctype pass `docstatus` (0/1/2 -> Draft/Submitted/Cancelled);
// otherwise pass the doctype's own `status` text and the same keyword theming
// the list view uses picks the colour.
import { computed } from 'vue'
import { statusBadgeTheme } from '@/utils/list/statusTheme'

const props = defineProps({
  status: { type: String, default: '' },
  docstatus: { type: Number, default: null },
  // Opts into DOCTYPE_FIELD_OVERRIDES (statusTheme.js) for a status field
  // whose vocabulary doesn't fit the generic keyword matching - e.g. Sales
  // Order's payment_status / Payment Entry's verification_status, both
  // Pending Verification/Verified/Rejected. Optional: omitted, this badge
  // behaves exactly as before (generic keyword theming only).
  doctype: { type: String, default: '' },
  field: { type: String, default: '' },
  // Skips theme lookup entirely and uses this instead - for a status that
  // isn't a real field at all (e.g. Sales Invoice's computed Paid/Unpaid/
  // Partly Paid), so there's no doctype+field to key a DOCTYPE_FIELD_
  // OVERRIDES entry on in the first place.
  theme: { type: String, default: '' },
})

const DOCSTATUS = { 0: ['Draft', 'orange'], 1: ['Submitted', 'green'], 2: ['Cancelled', 'red'] }

const label = computed(() => {
  if (props.status) return props.status
  return props.docstatus === null ? '' : DOCSTATUS[props.docstatus]?.[0] || ''
})
const theme = computed(() => {
  if (props.theme) return props.theme
  if (props.status) return statusBadgeTheme(props.status, { doctype: props.doctype, fieldname: props.field })
  return DOCSTATUS[props.docstatus]?.[1] || 'gray'
})
</script>
