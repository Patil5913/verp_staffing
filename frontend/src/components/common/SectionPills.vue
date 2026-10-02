<template>
  <nav class="flex shrink-0 gap-2 overflow-x-auto border-b border-app-border bg-app-panel px-3 py-2 md:px-6">
    <button
      v-for="s in sections"
      :key="s.id"
      type="button"
      class="shrink-0 rounded-full border border-app-border bg-app-panel px-3 py-1 text-p-xs font-medium text-app-text-muted transition-colors hover:border-app-primary hover:text-app-primary"
      @click="jump(s.id)"
    >
      {{ s.label }}
    </button>
  </nav>
</template>

<script setup>
// Pill row that scrolls to sections of a long settings tab. Place it above
// the tab's scroll area (not inside it) so it stays pinned under the sub
// navbar. Each section just needs the matching element id.
defineProps({ sections: { type: Array, required: true } }) // [{ id, label }]
function jump(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>
