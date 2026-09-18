<template>
  <Badge v-if="label" variant="subtle" :theme="theme">{{ label }}</Badge>
</template>

<script setup>
// The status pill shown beside a record's title / in list-like panels. For a
// submittable doctype pass `docstatus` (0/1/2 -> Draft/Submitted/Cancelled);
// otherwise pass the doctype's own `status` text and the same keyword theming
// the list view uses picks the colour.
import { computed } from 'vue'
import { Badge } from 'frappe-ui'
import { statusBadgeTheme } from '@/utils/list/statusTheme'

const props = defineProps({
  status: { type: String, default: '' },
  docstatus: { type: Number, default: null },
})

const DOCSTATUS = { 0: ['Draft', 'orange'], 1: ['Submitted', 'green'], 2: ['Cancelled', 'red'] }

const label = computed(() => {
  if (props.status) return props.status
  return props.docstatus === null ? '' : DOCSTATUS[props.docstatus]?.[0] || ''
})
const theme = computed(() => {
  if (props.status) return statusBadgeTheme(props.status)
  return DOCSTATUS[props.docstatus]?.[1] || 'gray'
})
</script>
