<template>
  <button
    type="button"
    class="inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap text-p-sm font-medium tracking-tight transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-primary/40 disabled:cursor-not-allowed disabled:opacity-50"
    :class="[sizeClasses, roundedClasses, variantClasses]"
    :disabled="disabled || loading"
    :title="tooltip || undefined"
    @click="(e) => !loading && !disabled && emit('click', e)"
  >
    <LoadingIndicator v-if="loading" class="h-3.5 w-3.5" />
    <FeatherIcon v-else-if="iconName" :name="iconName" class="h-3.5 w-3.5 shrink-0" />
    <span v-if="$slots.default || label"><slot>{{ label }}</slot></span>
  </button>
</template>

<script setup>
import { computed, useSlots } from 'vue'
import { FeatherIcon, LoadingIndicator } from 'frappe-ui'

// This app's own button, in place of frappe-ui's stock <Button> - a pill
// shape with a lifted, colored primary state instead of the flat desk-gray
// look, so primary actions (Save, Create Opportunity, etc.) read as this
// product's UI rather than an embedded Frappe form.
const props = defineProps({
  // primary | outline | ghost | danger | surface. `solid` / `subtle` (frappe-ui's names) map to
  // primary / outline, and theme="red" turns either into its destructive form.
  variant: { type: String, default: 'primary' },
  theme: { type: String, default: '' },
  size: { type: String, default: 'md' }, // sm | md | icon
  icon: { type: String, default: '' },
  iconLeft: { type: String, default: '' },
  label: { type: String, default: '' },
  tooltip: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['click'])
const slots = useSlots()

const iconName = computed(() => props.iconLeft || props.icon)
// A button with an icon and no text is a square icon button.
const iconOnly = computed(() => Boolean(iconName.value) && !slots.default && !props.label)
const resolvedVariant = computed(() => {
  const v = props.variant === 'solid' ? 'primary' : props.variant === 'subtle' ? 'outline' : props.variant
  return props.theme === 'red' && v === 'primary' ? 'danger' : v
})

const sizeClasses = computed(() => {
  if (props.size === 'icon') return 'h-8 w-8'
  if (iconOnly.value) return props.size === 'sm' ? 'h-7 w-7' : 'h-8 w-8'
  return props.size === 'sm' ? 'h-7 px-3.5' : 'h-8 px-4'
})

// Same rounding everywhere - the list view's icon buttons (Add New,
// Customize, Refresh, ...) and text buttons (Create Opportunity, Create
// Customer, ...) should read as the same button family.
const roundedClasses = computed(() => 'rounded-lg')

const variantClasses = computed(() => {
  switch (resolvedVariant.value) {
    case 'outline':
      return props.theme === 'red'
        ? 'border border-red-300 bg-app-panel text-red-600 hover:bg-red-50 active:scale-[0.98]'
        : 'border border-app-border bg-app-panel text-app-text hover:border-app-primary/50 hover:text-app-primary active:scale-[0.98]'
    case 'ghost':
      return 'text-app-text-muted hover:bg-app-panel-2 hover:text-app-text active:scale-[0.98]'
    case 'surface':
      return 'border border-app-border bg-app-panel-2 text-app-text hover:border-app-primary/50 hover:text-app-primary active:scale-[0.98]'
    case 'danger':
      return 'bg-red-600 text-white shadow-[0_1px_2px_rgba(220,38,38,0.35)] hover:bg-red-500 hover:shadow-[0_4px_12px_rgba(220,38,38,0.35)] active:scale-[0.98]'
    default:
      return 'bg-app-primary text-white shadow-[0_1px_2px_rgba(0,0,0,0.12)] hover:bg-app-primary-hover hover:shadow-[0_4px_14px_var(--app-primary-tint)] active:scale-[0.98]'
  }
})
</script>
