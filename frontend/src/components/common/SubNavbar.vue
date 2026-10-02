<template>
  <!-- The thin bar under the app navbar every list-like page uses: title on
  the left, search / filters in the middle, actions on the right - same
  3-column grid as DocListView so pages line up when you switch between
  them. The side columns size to their content and the middle one takes the
  rest, so a wide view switcher never runs into the search box; below xl the
  bar wraps instead of squeezing. -->
  <div class="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 border-b border-app-border bg-app-panel py-2 xl:grid xl:h-11 xl:grid-cols-[auto_minmax(0,1fr)_auto] xl:gap-3 xl:py-0 px-3 md:px-6">
    <div class="flex min-w-0 max-w-full flex-none items-center gap-3">
      <h1
        class="flex min-w-0 shrink-0 items-center gap-1.5 truncate rounded-lg border border-app-primary/15 bg-app-primary-tint px-3 py-1 text-p-lg font-semibold tracking-tight text-app-primary"
      >
        <span v-if="icon" :class="['lucide-' + icon, 'size-4', 'shrink-0', 'text-app-primary']" />
        <span class="truncate">{{ title }}</span>
      </h1>
      <slot name="left" />
    </div>
    <div v-if="$slots.default" class="order-last flex w-full min-w-0 items-center gap-2 xl:order-none xl:w-full"><slot /></div>
    <div class="ml-auto flex items-center justify-end gap-2"><slot name="right" /></div>
  </div>
</template>

<script setup>
// `icon` is an optional Lucide name (see utils/layout/sidebarIcons.js) to
// match this page's icon in the sidebar - same badge look DocListView gives
// every doctype's list title.
defineProps({ title: { type: String, default: '' }, icon: { type: String, default: '' } })
</script>
