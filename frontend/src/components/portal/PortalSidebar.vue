<template>
  <nav
    class="fixed inset-y-0 left-0 z-40 h-full shrink-0 overflow-hidden border-r border-app-border bg-app-panel pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)] transition-[width,transform] duration-200 ease-in-out md:static md:z-auto md:translate-x-0 md:pb-0 md:pt-0"
    :class="[sidebarOpen ? 'w-64' : 'w-16', isMobile && !mobileNavOpen ? '-translate-x-full' : 'translate-x-0']"
  >
    <div class="relative flex h-full flex-col" :class="sidebarOpen ? 'w-64' : 'w-16'">
      <button
        v-if="isMobile"
        type="button"
        aria-label="Close menu"
        class="absolute right-2 top-2 z-10 inline-flex size-8 items-center justify-center rounded-lg text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-app-text"
        @click="closeMobileNav()"
      >
        <span class="lucide-x size-5" />
      </button>
      <ScrollArea class="flex-1 px-2 py-3" :class="isMobile ? 'pt-12' : ''">
        <SidebarLink
          v-for="item in items"
          :key="item.route"
          :route="item.route"
          :label="item.label"
          :icon="item.icon"
          :active="route.path.startsWith(item.route.replace(/^\/verp/, ''))"
          :collapsed="!sidebarOpen"
        />
      </ScrollArea>
      <ProfileMenu :collapsed="!sidebarOpen" />
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ScrollArea from '@/components/ui/ScrollArea.vue'
import SidebarLink from '@/components/layout/SidebarLink.vue'
import ProfileMenu from '@/components/layout/ProfileMenu.vue'
import { useSidebar } from '@/composables/layout/useSidebar'
import { usePortal } from '@/composables/portal/usePortal'
import { usePortalGate } from '@/composables/portal/usePortalGate'

const route = useRoute()
const { sidebarOpen, isMobile, mobileNavOpen, closeMobileNav } = useSidebar()
const { data, technicalServices } = usePortal()
const { blocked } = usePortalGate()

// Icon classes are written out in full so Tailwind's icon plugin generates them: lucide-layout-dashboard
// lucide-user-round lucide-briefcase lucide-calendar-days lucide-wrench lucide-receipt lucide-file-text lucide-file-signature lucide-message-square
const items = computed(() => {
  // While the candidate details form or an agreement is pending, only those
  // two tabs stay reachable (CandidateFormGate blocks direct navigation too).
  if (blocked.value) {
    return [
      { route: '/verp/portal/candidate-details', label: 'Candidate Details', icon: 'user-round' },
      { route: '/verp/portal/agreements', label: 'Agreements', icon: 'file-signature' },
    ]
  }
  return [
    { route: '/verp/portal/dashboard', label: 'Dashboard', icon: 'layout-dashboard' },
    { route: '/verp/portal/services', label: 'Services', icon: 'briefcase' },
    { route: '/verp/portal/interviews', label: 'Interviews', icon: 'calendar-days' },
    // only when the customer has availed a technical service
    ...(technicalServices.value.length ? [{ route: '/verp/portal/technical', label: 'Technical', icon: 'wrench' }] : []),
    { route: '/verp/portal/accounts', label: 'Accounts', icon: 'receipt' },
    { route: '/verp/portal/documents', label: 'Documents', icon: 'file-text' },
    { route: '/verp/portal/candidate-details', label: 'Candidate Details', icon: 'user-round' },
    { route: '/verp/portal/agreements', label: 'Agreements', icon: 'file-signature' },
    ...(data.value?.chat_enabled ? [{ route: '/verp/portal/messages', label: 'Messages', icon: 'message-square' }] : []),
  ]
})
</script>
