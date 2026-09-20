<template>
  <div class="flex flex-col items-center gap-2 rounded-lg border border-app-border bg-app-panel px-3 md:px-6 py-12 text-center">
    <span :class="['lucide-' + icon, 'size-8', 'text-app-text-muted']" />
    <div class="text-p-base font-medium text-app-text">{{ title }}</div>
    <div v-if="description" class="max-w-sm text-p-sm text-app-text-muted">{{ description }}</div>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: 'info' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>
