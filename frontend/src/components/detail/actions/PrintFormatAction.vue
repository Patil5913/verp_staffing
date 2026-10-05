<template>
  <AppButton variant="outline" icon="printer" @click="print">{{ label }}</AppButton>
</template>

<script setup>
import AppButton from '@/components/ui/AppButton.vue'

// Opens the record as a PDF in the named Print Format, through Frappe's own
// download_pdf endpoint - the same format the server-side print uses.
const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  format: { type: String, required: true },
  label: { type: String, default: 'Print' },
})

function print() {
  const params = new URLSearchParams({ doctype: props.doctype, name: props.name, format: props.format, no_letterhead: 0 })
  window.open(`/api/method/frappe.utils.print_format.download_pdf?${params}`, '_blank', 'noopener')
}
</script>
