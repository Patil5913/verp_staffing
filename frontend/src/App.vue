<template>
  <FrappeUIProvider>
    <component :is="layout">
      <router-view />
    </component>
    <UnsavedChangesDialog />
  </FrappeUIProvider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider } from 'frappe-ui'
import AppShell from '@/layouts/AppShell.vue'
import BlankLayout from '@/layouts/BlankLayout.vue'
import PortalShell from '@/layouts/PortalShell.vue'
import UnsavedChangesDialog from '@/components/common/UnsavedChangesDialog.vue'

const route = useRoute()

// Public routes (currently just Login) get no navbar/sidebar chrome, and
// crucially never mount AppShell - which is what was firing the
// permission-filtered sidebar fetch (and its "failed to load" toast) for a
// Guest on the login page.
const layout = computed(() => (route.meta.public || route.meta.standalone ? BlankLayout : route.meta.portal ? PortalShell : AppShell))
</script>
