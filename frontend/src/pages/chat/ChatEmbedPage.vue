<template>
  <div class="h-full">
    <!-- Same origin, so the session, CSRF token and the shared verp-theme
         preference carry over; the chat keeps its own build (apps/vruglechat). -->
    <iframe
      v-if="available"
      :src="src"
      title="Vrugle Chat"
      class="block h-full w-full border-0"
      allow="clipboard-write"
    />
    <div v-else-if="loaded" class="mx-auto flex max-w-3xl flex-col gap-4 px-3 py-8 md:px-6">
      <StateBanner
        icon="message-square"
        title="Chat isn't available"
        description="The Vrugle Chat app isn't installed on this site, or your roles don't include it. Ask an administrator if you need it."
      >
        <AppButton variant="solid" theme="blue" @click="router.push('/')">Go to Dashboard</AppButton>
      </StateBanner>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { useSidebar } from '@/composables/layout/useSidebar'

const route = useRoute()
const router = useRouter()

// A mention notification links to /verp/chat?room=<name>: open that conversation.
const src = computed(() => (route.query.room ? `/chat/${encodeURIComponent(String(route.query.room))}` : '/chat'))

// The server only puts "Chat" in the sidebar when vruglechat is installed and
// the user holds a chat role (utils/sidebar.py), so its presence is the check.
const { loaded, navItems } = useSidebar()
const available = computed(() => Boolean(navItems.value.chat))
</script>
