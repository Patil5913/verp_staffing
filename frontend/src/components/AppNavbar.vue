<template>
  <header
    class="flex h-14 shrink-0 items-center gap-4 border-b border-app-border bg-app-panel px-4"
  >
    <a
      :href="homeRoute || '/verp'"
      class="flex shrink-0 items-center gap-2"
      @click="onLogoClick"
    >
      <img :src="logoSrc" alt="Vrugle" class="h-6 w-6" />
      <span class="text-base font-semibold text-app-text">
        Vrugle Staffing
      </span>
    </a>

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
import { computed, onMounted, onUnmounted, ref } from 'vue'
import router from '@/router'
import { useSidebar } from '@/composables/useSidebar'
import NotificationBell from './NotificationBell.vue'
import CommandPalette from './CommandPalette.vue'

const { firstAccessibleRoute } = useSidebar()
const homeRoute = computed(() => firstAccessibleRoute())

const paletteOpen = ref(false)
const modKey = /Mac/i.test(navigator.platform) ? '⌘' : 'Ctrl+'
// dynamic binding so Vite's template compiler doesn't try to resolve this
// as a local build asset — it's served at runtime by the Frappe backend
const logoSrc = '/assets/verp_staffing/images/Vrugle-icon-Logo-without-bg.png'

function onLogoClick(e) {
  const target = homeRoute.value
  if (!target) return
  e.preventDefault()
  if (target.startsWith('/verp')) {
    // router's path space excludes the '/verp' history base (see
    // SidebarLink.vue) — pushing the full route would double it up.
    router.push(target.replace(/^\/verp/, '') || '/')
  } else {
    window.location.href = target
  }
}

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
