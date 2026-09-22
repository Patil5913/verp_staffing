<template>
  <div class="flex min-w-0 flex-col gap-1.5">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">
      {{ label }}<span v-if="required" class="text-red-600"> *</span>
    </label>
    <input
      type="time"
      step="1"
      :value="displayValue"
      :disabled="disabled"
      class="h-9 w-full min-w-0 rounded-lg border bg-app-panel px-3 text-p-sm text-app-text outline-none transition-colors focus:border-app-primary focus:ring-2 focus:ring-app-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
      :class="error ? 'border-red-500' : 'border-app-border'"
      @input="$event.target.value && emit('update:modelValue', $event.target.value)"
    />
    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
  </div>
</template>

<script setup>
// A Time fieldtype had no control at all — FieldControl's TYPE_MAP simply
// had nothing for it, so it fell through to a plain text box with no picker.
// Not folded into AppDatePicker: that component is built entirely around a
// calendar grid, and a bare hour/minute value needs none of that — the
// browser's own <input type=time> is exactly this, styled to match.
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

// Frappe stores Time as HH:mm:ss; <input type=time> wants that exact shape
// (with step=1 asking it to show/accept seconds) or it silently blanks.
const displayValue = computed(() => {
  const v = props.modelValue || ''
  if (!v) return ''
  return /^\d{2}:\d{2}$/.test(v) ? `${v}:00` : v
})
</script>
