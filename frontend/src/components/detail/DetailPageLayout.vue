<template>
  <div class="flex h-full flex-col bg-app-bg">
    <!-- Single navbar: back + title, tabs (dynamic per doctype), actions -->
    <div
      class="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-app-border bg-app-panel px-3 py-2 shadow-sm md:h-14 md:flex-nowrap md:gap-4 md:px-6 md:py-0"
    >
      <div class="flex min-w-0 flex-1 items-center gap-2 md:flex-none md:shrink-0 md:gap-3">
        <AppButton variant="ghost" size="icon" icon="arrow-left" @click="emit('back')" />
        <h1 class="min-w-0 max-w-full truncate md:max-w-xs text-p-lg font-medium text-app-text">{{ title }}</h1>
        <slot name="title-extra" />
      </div>

      <div class="hidden h-6 w-px shrink-0 bg-app-border md:block" />

      <!-- Reserve growth room here: tab count/labels vary by doctype -->
      <nav class="[scrollbar-width:none] order-last flex h-full min-w-0 w-full items-center gap-3 overflow-x-auto md:order-none md:w-auto md:flex-1 md:gap-1">
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

      <div class="flex max-w-full shrink-0 flex-wrap items-center justify-end gap-2">
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
import AppButton from '@/components/ui/AppButton.vue'

defineProps({
  title: { type: String, default: '' },
  tabs: { type: Array, required: true }, // [{ key, label }]
  activeTab: { type: String, required: true },
})
const emit = defineEmits(['back', 'update:activeTab'])
</script>
