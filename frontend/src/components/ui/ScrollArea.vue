<template>
  <div class="verp-scroll-area">
    <slot />
  </div>
</template>

<script setup>
// A themed, thin scrollbar wrapper - native scrolling (wheel/touch/momentum/
// keyboard/a11y) is kept as-is, only the scrollbar's look is replaced, since
// the default OS scrollbar is what looked out of place, not scrolling itself.
</script>

<style scoped>
.verp-scroll-area {
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: smooth;
  scrollbar-width: thin;
  scrollbar-color: var(--app-border) transparent;
}

.verp-scroll-area::-webkit-scrollbar {
  width: 6px;
}

.verp-scroll-area::-webkit-scrollbar-track {
  background: transparent;
}

.verp-scroll-area::-webkit-scrollbar-thumb {
  background-color: var(--app-border);
  border-radius: 9999px;
}

.verp-scroll-area::-webkit-scrollbar-thumb:hover {
  background-color: var(--app-text-muted);
}
</style>
