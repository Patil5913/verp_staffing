<template>
  <section class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <header v-if="title || $slots.actions" class="flex items-center justify-between gap-3">
      <div class="min-w-0">
        <h3 class="truncate text-p-base font-medium text-app-text">{{ title }}</h3>
        <p v-if="subtitle" class="text-p-sm text-app-text-muted">{{ subtitle }}</p>
      </div>
      <div class="flex shrink-0 items-center gap-2"><slot name="actions" /></div>
    </header>
    <slot />
  </section>
</template>

<script setup>
// The rounded "panel" every detail-page block (customer details, history,
// summaries, ...) sits in — same chrome as DocDetailView's field card and
// ChildTableField, so custom panels line up with the generic ones.
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
})
</script>
