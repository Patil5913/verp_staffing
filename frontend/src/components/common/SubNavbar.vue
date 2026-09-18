<template>
  <!-- The thin bar under the app navbar every list-like page uses: title on
  the left, search / filters in the middle, actions on the right — same
  3-column grid as DocListView so pages line up when you switch between
  them. -->
  <div class="grid h-11 shrink-0 grid-cols-3 items-center gap-3 border-b border-app-border bg-app-panel px-6">
    <div class="flex min-w-0 items-center gap-3">
      <h1 class="min-w-0 shrink-0 truncate text-p-lg font-medium text-app-text">{{ title }}</h1>
      <slot name="left" />
    </div>
    <div class="flex min-w-0 items-center gap-2"><slot /></div>
    <div class="flex items-center justify-end gap-2"><slot name="right" /></div>
  </div>
</template>

<script setup>
defineProps({ title: { type: String, default: '' } })
</script>
