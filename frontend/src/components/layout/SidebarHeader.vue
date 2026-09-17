<template>
  <div
    class="flex h-full shrink-0 items-center border-r border-app-border transition-[width] duration-200 ease-in-out"
    :class="sidebarOpen ? 'w-64 gap-2 px-4' : 'w-16 justify-center px-2'"
  >
    <a
      :href="homeRoute || '/verp'"
      class="flex min-w-0 items-center gap-2"
      :class="sidebarOpen ? 'flex-1' : ''"
      @click="onLogoClick"
    >
      <img :src="logoSrc" alt="Vrugle" class="h-6 w-6 shrink-0" />
      <span
        v-if="sidebarOpen"
        class="truncate text-base font-semibold text-app-text"
      >
        Vrugle Staffing
      </span>
    </a>

    <button
      type="button"
      class="flex size-7 shrink-0 items-center justify-center rounded-md text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-app-text"
      :aria-label="sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
      @click="toggleSidebar"
    >
      <span class="lucide-panel-left size-4" />
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import router from '@/router'
import { useSidebar } from '@/composables/layout/useSidebar'

const { sidebarOpen, toggleSidebar, firstAccessibleRoute } = useSidebar()
const homeRoute = computed(() => firstAccessibleRoute())
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
</script>
