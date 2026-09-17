<template>
  <div class="flex h-full flex-col bg-app-bg">
    <!-- Single navbar: back + title, tabs (dynamic per doctype), actions -->
    <div
      class="flex h-14 shrink-0 items-center gap-4 border-b border-app-border bg-app-panel px-6 shadow-sm"
    >
      <div class="flex min-w-0 shrink-0 items-center gap-3">
        <AppButton variant="ghost" size="icon" icon="arrow-left" @click="emit('back')" />
        <h1 class="min-w-0 max-w-xs truncate text-p-lg font-medium text-app-text">{{ title }}</h1>
      </div>

      <div class="h-6 w-px shrink-0 bg-app-border" />

      <!-- Reserve growth room here: tab count/labels vary by doctype -->
      <nav class="flex h-full min-w-0 flex-1 items-center gap-1 overflow-x-auto">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="shrink-0 border-b-2 px-1 py-3 text-p-sm font-medium transition-colors"
          :class="
            tab.key === activeTab
              ? 'border-app-primary text-app-text'
              : 'border-transparent text-app-text-muted hover:text-app-text'
          "
          @click="emit('update:activeTab', tab.key)"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div class="flex shrink-0 items-center gap-2">
        <slot name="actions" />
      </div>
    </div>

    <!-- Body: each tab owns its own scrolling, so a tab like Activity can
    dock a composer to its bottom instead of scrolling away with the page. -->
    <div class="min-h-0 flex-1 overflow-hidden">
      <slot :name="`tab-${activeTab}`" />
    </div>
  </div>
</template>

<script setup>
import AppButton from '@/components/common/AppButton.vue'

defineProps({
  title: { type: String, default: '' },
  tabs: { type: Array, required: true }, // [{ key, label }]
  activeTab: { type: String, required: true },
})
const emit = defineEmits(['back', 'update:activeTab'])
</script>
