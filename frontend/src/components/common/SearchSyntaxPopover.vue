<template>
  <!-- The "i" inside a search box: a popover of example filters. The list scrolls when it is taller
  than the screen, and a click anywhere outside (or Escape) closes it. -->
  <Popover trigger="click" placement="bottom-end" hide-on-blur>
    <template #target="{ togglePopover }">
      <FeatherIcon name="info" class="h-4 w-4 cursor-pointer text-app-text-muted hover:text-app-primary" @click="togglePopover()" />
    </template>
    <template #body="{ close }">
      <div class="my-2 flex max-h-[min(32rem,calc(100vh-8rem))] w-[min(26rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-xl border border-app-border bg-app-panel shadow-xl">
        <div class="flex shrink-0 items-center gap-2 border-b border-app-border bg-app-panel-2 px-4 py-3">
          <FeatherIcon name="search" class="h-4 w-4 text-app-primary" />
          <h4 class="text-p-base font-semibold text-app-text">Search syntax</h4>
        </div>
        <p class="shrink-0 border-b border-app-border px-4 py-2 text-p-xs text-app-text-muted">Click a filter below to apply it to the search bar.</p>
        <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <div class="flex flex-col divide-y divide-app-border">
            <div v-for="group in groups" :key="group.title" class="flex flex-col gap-2.5 px-4 py-3">
              <p class="text-p-xs font-semibold uppercase tracking-wide text-app-text-muted">{{ group.title }}</p>
              <div v-for="row in group.rows" :key="row.example" class="flex flex-col gap-1">
                <button
                  type="button"
                  class="block w-fit max-w-full whitespace-pre-wrap break-words rounded-md bg-app-panel-2 px-2 py-1 text-left font-mono text-p-xs text-app-primary hover:bg-app-primary-tint"
                  @click="(emit('select', row.example), close())"
                >{{ row.example }}</button>
                <span class="text-p-sm leading-snug text-app-text-muted">{{ row.description }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { FeatherIcon, Popover } from 'frappe-ui'

defineProps({ groups: { type: Array, required: true } })
const emit = defineEmits(['select'])
</script>
