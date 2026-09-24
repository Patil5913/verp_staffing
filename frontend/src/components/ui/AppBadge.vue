<template>
  <span
    class="inline-flex shrink-0 items-center whitespace-nowrap rounded-full font-medium"
    :class="[TONES[theme] || TONES.gray, size === 'md' ? 'px-2.5 py-1 text-p-sm' : 'px-2 py-0.5 text-p-xs']"
  >
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup>
// Small coloured pill for a status or tag. Themes match frappe-ui's names so
// existing `theme="green"` call sites carry over.
defineProps({
  label: { type: String, default: '' },
  theme: { type: String, default: 'gray' }, // gray | cyan | blue | green | orange | yellow | red
  size: { type: String, default: 'sm' }, // sm | md
})

const TONES = {
  gray: 'bg-app-panel-2 text-app-text-muted',
  cyan: 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-300',
  blue: 'bg-blue-500/10 text-blue-700 dark:text-blue-300',
  green: 'bg-green-500/10 text-green-700 dark:text-green-300',
  orange: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
  yellow: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-300',
  red: 'bg-red-500/10 text-red-700 dark:text-red-300',
}
</script>
