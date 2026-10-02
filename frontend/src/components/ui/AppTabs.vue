<template>
  <div class="flex items-center gap-1 border-b border-app-border">
    <button
      v-for="tab in normalized"
      :key="tab.value"
      type="button"
      class="-mb-px border-b-2 px-3 py-2 text-p-sm font-medium transition-colors"
      :class="tab.value === modelValue ? 'border-app-primary text-app-primary' : 'border-transparent text-app-text-muted hover:text-app-text'"
      @click="emit('update:modelValue', tab.value)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  // [{ label, value }] or plain strings.
  tabs: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const normalized = computed(() => props.tabs.map((t) => (typeof t === 'string' ? { label: t, value: t } : t)))
</script>
