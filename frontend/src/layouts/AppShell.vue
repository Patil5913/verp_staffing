<template>
  <div class="flex h-screen flex-col">
    <AppNavbar />
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
import AppNavbar from '@/components/AppNavbar.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useSidebar } from '@/composables/useSidebar'

const { load } = useSidebar()

onMounted(() => {
  load(window.user)
})
</script>
