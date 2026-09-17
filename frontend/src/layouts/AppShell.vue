<template>
  <div class="flex h-screen flex-col">
    <div class="flex h-14 shrink-0 border-b border-app-border bg-app-panel">
      <SidebarHeader />
      <AppNavbar />
    </div>
    <div class="flex min-h-0 flex-1">
      <AppSidebar />
      <main class="min-w-0 flex-1 overflow-y-auto">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import SidebarHeader from '@/components/layout/SidebarHeader.vue'
import AppNavbar from '@/components/layout/AppNavbar.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import { useSidebar } from '@/composables/layout/useSidebar'

const { load } = useSidebar()

onMounted(() => {
  load(window.user)
})
</script>
