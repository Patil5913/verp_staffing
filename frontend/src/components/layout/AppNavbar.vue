<template>
  <header class="flex min-w-0 flex-1 items-center gap-2 pl-2 pr-[max(0.75rem,env(safe-area-inset-right))] md:gap-4 md:px-4">
    <NavbarClock />

    <div class="flex flex-1 justify-center">
      <button
        type="button"
        class="flex h-10 w-full max-w-md items-center gap-2 rounded-md border border-app-border bg-app-bg px-3 py-1.5 text-left text-p-sm text-app-text-muted transition-colors hover:border-app-primary md:h-auto"
        @click="paletteOpen = true"
      >
        <span class="lucide-search size-4 shrink-0" />
        <span class="flex-1 truncate">
          Search...
        </span>
        <kbd
          class="hidden shrink-0 rounded border border-app-border px-1.5 py-0.5 text-2xs sm:inline"
        >
          {{ modKey }}K
        </kbd>
      </button>
    </div>

    <PushToggle v-if="!$route.path.startsWith('/chat')" />
    <ChatBell />
    <NotificationBell />

    <CommandPalette v-model="paletteOpen" />
  </header>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import NavbarClock from '@/components/layout/NavbarClock.vue'
import PushToggle from '@/components/common/PushToggle.vue'
import ChatBell from '@/components/layout/ChatBell.vue'
import NotificationBell from '@/components/overlays/NotificationBell.vue'
import CommandPalette from '@/components/overlays/CommandPalette.vue'

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
