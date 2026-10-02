<template>
  <button
    v-if="available"
    type="button"
    class="relative flex h-10 w-10 items-center justify-center rounded-full text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-app-text md:h-8 md:w-8"
    :class="route.path.startsWith('/chat') ? 'bg-app-primary-tint text-app-primary' : ''"
    :aria-label="unread ? `Chat, ${unread} unread` : 'Chat'"
    title="Chat"
    @click="router.push('/chat')"
  >
    <span class="lucide-message-square size-4.5" />
    <span
      v-if="unread"
      class="absolute right-0 top-0 min-w-[16px] rounded-full bg-red-500 px-1 text-center text-[10px] font-bold leading-4 text-white"
    >
      {{ unread > 9 ? '9+' : unread }}
    </span>
  </button>
</template>

<script setup>
// Same spot and style as the notification bell. Shown only when the chat is available to this
// person: the server puts "Chat" in the sidebar exactly when vruglechat is installed and they hold a chat role.
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSidebar } from '@/composables/layout/useSidebar'
import { useChatUnread } from '@/composables/layout/useChatUnread'

const route = useRoute()
const router = useRouter()
const { navItems } = useSidebar()
const available = computed(() => Boolean(navItems.value.chat))
const { unread, start } = useChatUnread()
watch(available, (yes) => yes && start(), { immediate: true })
</script>
