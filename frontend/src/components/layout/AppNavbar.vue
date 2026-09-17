<template>
  <header class="flex min-w-0 flex-1 items-center gap-4 px-4">
    <div class="flex flex-1 justify-center">
      <button
        type="button"
        class="flex w-full max-w-md items-center gap-2 rounded-md border border-app-border bg-app-bg px-3 py-1.5 text-left text-p-sm text-app-text-muted transition-colors hover:border-app-primary"
        @click="paletteOpen = true"
      >
        <span class="lucide-search size-4 shrink-0" />
        <span class="flex-1 truncate">
          Search modules, doctypes, reports...
        </span>
        <kbd
          class="hidden shrink-0 rounded border border-app-border px-1.5 py-0.5 text-2xs sm:inline"
        >
          {{ modKey }}K
        </kbd>
      </button>
    </div>

    <NotificationBell />

    <CommandPalette v-model="paletteOpen" />
  </header>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import NotificationBell from '../overlays/NotificationBell.vue'
import CommandPalette from '../overlays/CommandPalette.vue'

const paletteOpen = ref(false)
const modKey = /Mac/i.test(navigator.platform) ? '⌘' : 'Ctrl+'

function onKeydown(e) {
  const isMod = e.metaKey || e.ctrlKey
  if (isMod && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    paletteOpen.value = true
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>
