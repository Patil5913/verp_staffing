<template>
  <div class="flex h-dvh flex-col">
    <div class="flex h-14 shrink-0 border-b border-app-border bg-app-panel pt-[env(safe-area-inset-top)] box-content">
      <SidebarHeader />
      <PortalNavbar />
    </div>
    <div class="flex min-h-0 flex-1">
      <PortalSidebar />
      <main class="min-w-0 flex-1 overflow-y-auto pb-[env(safe-area-inset-bottom)]">
        <slot />
      </main>
    </div>

    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="isMobile && mobileNavOpen" class="fixed inset-0 z-30 bg-black/40" aria-hidden="true" @click="closeMobileNav" />
    </Transition>

    <PendingFeedbackGate />
    <CandidateFormGate />
  </div>
</template>

<script setup>
// The customer's version of AppShell: the same header, sidebar and content
// anatomy, with the portal's own navigation. Customers never load the staff
// sidebar config, and every request they make is scoped server-side.
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import SidebarHeader from '@/components/layout/SidebarHeader.vue'
import PortalNavbar from '@/components/portal/PortalNavbar.vue'
import PortalSidebar from '@/components/portal/PortalSidebar.vue'
import PendingFeedbackGate from '@/components/portal/PendingFeedbackGate.vue'
import CandidateFormGate from '@/components/portal/CandidateFormGate.vue'
import { useSidebar } from '@/composables/layout/useSidebar'
import { getSocket } from '@/utils/common/realtime'
import { notify } from '@/utils/common/notify'
import { usePortal } from '@/composables/portal/usePortal'

const { isMobile, mobileNavOpen, closeMobileNav } = useSidebar()
const { load, refreshUnread, unread } = usePortal()
const route = useRoute()

watch(() => route.fullPath, closeMobileNav)
// A new message while the customer is elsewhere in the portal.
watch(unread, (now, before) => {
  if (now > before && route.name !== 'PortalMessages') notify.info(`You have ${now} unread message${now > 1 ? 's' : ''}.`)
})

onMounted(async () => {
  await load()
  refreshUnread()
  // live badge: new messages, and reading them (here or in the chat iframe)
  if (data.value?.chat_enabled) {
    const socket = getSocket()
    let timer = null
    const soon = () => {
      clearTimeout(timer)
      timer = setTimeout(refreshUnread, 400)
    }
    for (const ev of ['chat_new_message', 'chat_unread_changed', 'chat_room_updated']) socket.on(ev, soon)
  }
  setInterval(() => !document.hidden && route.name !== 'PortalMessages' && refreshUnread(), 30000)
})
</script>
