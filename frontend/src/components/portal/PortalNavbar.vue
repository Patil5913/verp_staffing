<template>
  <header class="flex min-w-0 flex-1 items-center gap-2 pl-2 pr-[max(0.75rem,env(safe-area-inset-right))] md:gap-4 md:px-4">
    <h1 class="min-w-0 flex-1 truncate text-base font-semibold text-app-text">{{ route.meta.title || 'Customer Portal' }}</h1>

    <span v-if="customerTitle" class="hidden max-w-[16rem] truncate text-p-sm text-app-text-muted sm:block">{{ customerTitle }}</span>

    <button
      v-if="data?.chat_enabled"
      type="button"
      class="relative flex size-9 items-center justify-center rounded-lg text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-app-text"
      aria-label="Messages"
      title="Messages"
      @click="router.push('/portal/messages')"
    >
      <span class="lucide-message-square size-5" />
      <span
        v-if="unread"
        class="absolute right-0.5 top-0.5 min-w-[16px] rounded-full bg-red-500 px-1 text-center text-[10px] font-bold leading-4 text-white"
      >
        {{ unread > 9 ? '9+' : unread }}
      </span>
    </button>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePortal } from '@/composables/portal/usePortal'

const route = useRoute()
const router = useRouter()
const { data, unread } = usePortal()
const customerTitle = computed(() => data.value?.customer_title || '')
</script>
