<template>
  <div class="flex min-w-0 flex-col gap-2">
    <label v-if="label" class="text-p-sm font-medium text-app-text-muted">
      {{ label }}<span v-if="required" class="text-red-600"> *</span>
    </label>

    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="day in DAYS"
        :key="day"
        type="button"
        :disabled="disabled"
        class="h-8 w-11 rounded-lg border text-p-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60"
        :class="
          days.includes(day)
            ? 'border-app-primary bg-app-primary/10 text-app-primary'
            : 'border-app-border bg-app-panel text-app-text-muted hover:border-app-primary/50'
        "
        @click="toggleDay(day)"
      >
        {{ day }}
      </button>
    </div>

    <div class="flex items-center gap-2">
      <input
        type="time"
        step="60"
        :value="start"
        :disabled="disabled"
        class="h-12 w-full min-w-0 rounded-lg border border-app-border bg-app-panel px-3 text-p-base text-app-text outline-none transition-colors focus:border-app-primary focus:ring-2 focus:ring-app-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
        @input="onStart($event.target.value)"
      />
      <span class="shrink-0 text-p-sm text-app-text-muted">to</span>
      <input
        type="time"
        step="60"
        :value="end"
        :disabled="disabled"
        class="h-12 w-full min-w-0 rounded-lg border border-app-border bg-app-panel px-3 text-p-base text-app-text outline-none transition-colors focus:border-app-primary focus:ring-2 focus:ring-app-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
        @input="onEnd($event.target.value)"
      />
    </div>

    <p v-if="error" class="text-p-xs text-red-600">{{ error }}</p>
  </div>
</template>

<script setup>
// A day-of-week + time-range picker for Lead Detail Form's
// availability_for_interview - stored as the same plain "Mon - Fri, 9:30 AM -
// 10:00 PM" style Data string the field always had (see fieldFormats.js's
// parseAvailability/formatAvailability), just edited with chips + native time
// inputs instead of typing that string by hand.
import { computed, ref, watch } from 'vue'
import { DAYS, parseAvailability, formatAvailability } from '@/utils/detail/availability'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const days = ref([])
const start = ref('')
const end = ref('')

watch(
  () => props.modelValue,
  (v) => {
    const parsed = parseAvailability(v)
    days.value = parsed.days
    start.value = parsed.start
    end.value = parsed.end
  },
  { immediate: true },
)

function emitValue() {
  emit('update:modelValue', formatAvailability({ days: days.value, start: start.value, end: end.value }))
}

function toggleDay(day) {
  if (props.disabled) return
  days.value = days.value.includes(day) ? days.value.filter((d) => d !== day) : [...days.value, day].sort((a, b) => DAYS.indexOf(a) - DAYS.indexOf(b))
  emitValue()
}

function onStart(value) {
  start.value = value
  emitValue()
}

function onEnd(value) {
  end.value = value
  emitValue()
}
</script>
