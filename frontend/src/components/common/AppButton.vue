<template>
  <button
    type="button"
    class="inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-full text-p-sm font-medium tracking-tight transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-primary/40 disabled:cursor-not-allowed disabled:opacity-50"
    :class="[sizeClasses, variantClasses]"
    :disabled="disabled || loading"
    @click="(e) => !loading && !disabled && emit('click', e)"
  >
    <LoadingIndicator v-if="loading" class="h-3.5 w-3.5" />
    <FeatherIcon v-else-if="icon" :name="icon" class="h-3.5 w-3.5 shrink-0" />
    <span v-if="$slots.default"><slot /></span>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { FeatherIcon, LoadingIndicator } from 'frappe-ui'

// This app's own button, in place of frappe-ui's stock <Button> — a pill
// shape with a lifted, colored primary state instead of the flat desk-gray
// look, so primary actions (Save, Create Opportunity, etc.) read as this
// product's UI rather than an embedded Frappe form.
const props = defineProps({
  variant: { type: String, default: 'primary' }, // primary | outline | ghost | danger
  size: { type: String, default: 'md' }, // sm | md | icon
  icon: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['click'])

const sizeClasses = computed(() => {
  if (props.size === 'icon') return 'h-9 w-9'
  return props.size === 'sm' ? 'h-8 px-3.5' : 'h-9 px-4'
})

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'outline':
      return 'border border-app-border bg-app-panel text-app-text hover:border-app-primary/50 hover:text-app-primary active:scale-[0.98]'
    case 'ghost':
      return 'text-app-text-muted hover:bg-app-panel-2 hover:text-app-text active:scale-[0.98]'
    case 'danger':
      return 'bg-red-600 text-white shadow-[0_1px_2px_rgba(220,38,38,0.35)] hover:bg-red-500 hover:shadow-[0_4px_12px_rgba(220,38,38,0.35)] active:scale-[0.98]'
    default:
      return 'bg-app-primary text-white shadow-[0_1px_2px_rgba(0,0,0,0.12)] hover:bg-app-primary-hover hover:shadow-[0_4px_14px_var(--app-primary-tint)] active:scale-[0.98]'
  }
})
</script>
