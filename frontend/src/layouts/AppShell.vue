<template>
  <div class="flex h-dvh flex-col">
    <div
      class="flex h-14 shrink-0 border-b border-app-border bg-app-panel pt-[env(safe-area-inset-top)] box-content"
    >
      <SidebarHeader />
      <AppNavbar />
    </div>
    <div class="flex min-h-0 flex-1">
      <AppSidebar />
      <main class="min-w-0 flex-1 overflow-y-auto pb-[env(safe-area-inset-bottom)]">
        <slot />
      </main>
    </div>

    <!-- Phones: tapping outside the drawer closes it -->
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isMobile && mobileNavOpen"
        class="fixed inset-0 z-30 bg-black/40"
        aria-hidden="true"
        @click="closeMobileNav"
      />
    </Transition>
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import SidebarHeader from '@/components/layout/SidebarHeader.vue'
import AppNavbar from '@/components/layout/AppNavbar.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import { useSidebar } from '@/composables/layout/useSidebar'

const { load, isMobile, mobileNavOpen, closeMobileNav } = useSidebar()
const route = useRoute()

// picking a destination in the drawer should reveal it
watch(() => route.fullPath, closeMobileNav)

onMounted(() => {
  load(window.user)
})
</script>
