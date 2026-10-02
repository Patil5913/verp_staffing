<template>
  <Dialog v-model="open" :options="{ title: 'Keyboard Shortcuts', size: 'md' }">
    <template #body-content>
      <p class="mb-3 text-p-sm text-app-text-muted">
        Press
        <kbd class="rounded border border-app-border px-1.5 py-0.5 text-2xs"
          >{{ modKey }}K</kbd
        >
        anywhere to search and jump to a module.
      </p>
      <ul
        v-if="shortcutItems.length"
        class="max-h-80 divide-y divide-app-border overflow-y-auto"
      >
        <li
          v-for="item in shortcutItems"
          :key="item.key"
          class="flex items-center justify-between gap-3 py-2 text-p-base text-app-text"
        >
          <span class="min-w-0 truncate">{{ item.label }}</span>
          <kbd
            class="shrink-0 rounded border border-app-border px-1.5 py-0.5 text-2xs text-app-text-muted"
          >
            {{ item.shortcut }}
          </kbd>
        </li>
      </ul>
      <p v-else class="py-6 text-center text-p-sm text-app-text-muted">
        No item-specific shortcuts configured yet.
      </p>
    </template>
  </Dialog>
</template>

<script setup>
import { computed } from 'vue'
import { Dialog } from 'frappe-ui'
import { useSidebar } from '@/composables/layout/useSidebar'

const open = defineModel({ default: false })

const { flatList } = useSidebar()
const shortcutItems = computed(() =>
  flatList.value.filter((item) => item.shortcut),
)
const modKey = /Mac/i.test(navigator.platform) ? '⌘' : 'Ctrl+'
</script>
