<template>
  <label
    class="group inline-flex items-center gap-2.5 text-p-sm text-app-text"
    :class="disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'"
  >
    <span class="relative inline-flex size-[18px] shrink-0">
      <input
        type="checkbox"
        class="peer absolute inset-0 m-0 size-full cursor-[inherit] appearance-none rounded-[6px] opacity-0"
        :checked="Boolean(modelValue)"
        :indeterminate.prop="indeterminate"
        :disabled="disabled"
        @change="emit('update:modelValue', $event.target.checked)"
      />
      <!-- Box: outlined when off, filled with a check (or dash) when on -->
      <span
        class="pointer-events-none flex size-full items-center justify-center rounded-[6px] border-[1.5px] transition-all duration-150 peer-focus-visible:ring-2 peer-focus-visible:ring-app-primary/40 peer-focus-visible:ring-offset-1"
        :class="
          modelValue || indeterminate
            ? 'border-app-primary bg-app-primary shadow-[0_1px_2px_var(--app-primary-tint)]'
            : 'border-app-border bg-app-panel group-hover:border-app-primary/60'
        "
      >
        <svg
          viewBox="0 0 16 16"
          class="size-3 text-white transition-all duration-150"
          :class="modelValue || indeterminate ? 'scale-100 opacity-100' : 'scale-50 opacity-0'"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path v-if="indeterminate && !modelValue" d="M3.5 8h9" />
          <path v-else d="M3.5 8.5l3 3 6-7" />
        </svg>
      </span>
    </span>
    <span v-if="label || $slots.default" class="min-w-0 flex-1"><slot>{{ label }}</slot></span>
  </label>
</template>

<script setup>
// The app's checkbox: a rounded box that fills with the primary colour and
// draws a check on selection. `indeterminate` shows a dash (a "select all"
// header with only some rows picked).
defineProps({
  modelValue: { type: [Boolean, Number], default: false },
  label: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  indeterminate: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
</script>
