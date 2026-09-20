<template>
  <!-- The thin bar under the app navbar every list-like page uses: title on
  the left, search / filters in the middle, actions on the right — same
  3-column grid as DocListView so pages line up when you switch between
  them. -->
  <div class="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-app-border bg-app-panel py-2 md:grid md:h-11 md:grid-cols-3 md:py-0 px-3 md:px-6">
    <div class="flex min-w-0 flex-1 items-center gap-3 md:flex-none">
      <h1 class="min-w-0 shrink-0 truncate text-p-lg font-medium text-app-text">{{ title }}</h1>
      <slot name="left" />
    </div>
    <div class="order-last flex w-full min-w-0 items-center gap-2 md:order-none md:w-auto"><slot /></div>
    <div class="ml-auto flex items-center justify-end gap-2"><slot name="right" /></div>
  </div>
</template>

<script setup>
defineProps({ title: { type: String, default: '' } })
</script>
