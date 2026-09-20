<template>
  <div
    class="flex h-full shrink-0 items-center transition-[width] duration-200 ease-in-out md:border-r md:border-app-border"
    :class="
      isMobile
        ? 'flex-row-reverse gap-2 pl-[max(0.75rem,env(safe-area-inset-left))] pr-1'
        : sidebarOpen
          ? 'w-64 gap-2 px-4'
          : 'w-16 justify-center px-2'
    "
  >
    <a
      :href="homeRoute || '/verp'"
      class="flex min-w-0 items-center gap-2"
      :class="sidebarOpen && !isMobile ? 'flex-1' : ''"
      @click="onLogoClick"
    >
      <img :src="logoSrc" alt="Vrugle" class="h-6 w-6 shrink-0" />
      <span
        v-if="sidebarOpen && !isMobile"
        class="truncate text-base font-semibold text-app-text"
      >
        Vrugle Staffing
      </span>
    </a>

    <button
      type="button"
      class="flex shrink-0 items-center justify-center rounded-md text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-app-text"
      :class="isMobile ? 'size-10' : 'size-7'"
      :aria-label="isMobile ? 'Open menu' : sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
      @click="isMobile ? toggleMobileNav() : toggleSidebar()"
    >
      <span :class="isMobile ? 'lucide-menu size-5' : 'lucide-panel-left size-4'" />
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import router from '@/router'
import { useSidebar } from '@/composables/layout/useSidebar'

const { sidebarOpen, toggleSidebar, isMobile, toggleMobileNav, firstAccessibleRoute } = useSidebar()
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
