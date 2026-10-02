<template>
  <SectionCard v-if="detail.values.error" title="Error" subtitle="Why the last attempt to send failed.">
    <pre class="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-red-500/10 p-3 font-mono text-p-xs text-red-800">{{ detail.values.error }}</pre>
  </SectionCard>
</template>

<script setup>
import SectionCard from '@/components/common/SectionCard.vue'

defineProps({
  detail: { type: Object, required: true },
  doctype: { type: String, default: '' },
  name: { type: String, default: '' },
  locked: { type: Boolean, default: false },
})
</script>
