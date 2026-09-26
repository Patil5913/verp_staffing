<template>
  <label class="inline-flex items-start gap-3" :class="disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'">
    <span class="relative mt-0.5 inline-flex h-5 w-9 shrink-0">
      <input
        type="checkbox"
        role="switch"
        class="peer absolute inset-0 m-0 size-full cursor-[inherit] appearance-none opacity-0"
        :checked="Boolean(modelValue)"
        :disabled="disabled"
        @change="emit('update:modelValue', $event.target.checked ? 1 : 0)"
      />
      <span
        class="pointer-events-none absolute inset-0 rounded-full border transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-app-primary/40"
        :class="modelValue ? 'border-app-primary bg-app-primary' : 'border-app-border bg-app-panel-2'"
      />
      <span
        class="pointer-events-none absolute left-0.5 top-0.5 size-4 rounded-full bg-white shadow transition-transform"
        :class="modelValue ? 'translate-x-4' : 'translate-x-0'"
      />
    </span>
    <span v-if="label || description" class="min-w-0">
      <span class="block text-p-sm font-medium text-app-text">{{ label }}</span>
      <span v-if="description" class="block text-p-xs text-app-text-muted">{{ description }}</span>
    </span>
  </label>
</template>

<script setup>
// On/off toggle for a Check field that switches a behaviour (rather than
// picking rows, which is AppCheckbox). Emits 1/0 to match Frappe Check values.
defineProps({
  modelValue: { type: [Boolean, Number], default: false },
  label: { type: String, default: '' },
  description: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
</script>
