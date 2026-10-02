<template>
  <section :id="id" class="flex flex-col gap-3 scroll-mt-6">
    <div>
      <h2 class="text-p-lg font-semibold text-app-text">{{ title }}</h2>
      <p v-if="source" class="font-mono text-p-xs text-app-text-muted">{{ source }}</p>
    </div>
    <div class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
      <slot />
    </div>
  </section>
</template>

<script setup>
// One entry of the /components gallery: a title, where the component lives,
// and a live demo in the slot.
defineProps({
  id: { type: String, default: '' },
  title: { type: String, required: true },
  source: { type: String, default: '' },
})
</script>
