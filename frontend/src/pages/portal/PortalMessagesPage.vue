<template>
  <div class="h-full">
    <!-- Same origin, so the session and theme carry over; the chat keeps its own build (apps/vruglechat). -->
    <iframe v-if="available" :src="src" title="Messages" class="block h-full w-full border-0" allow="clipboard-write" />
    <div v-else class="mx-auto max-w-3xl px-3 py-8 md:px-6">
      <StateBanner icon="message-square" title="Messages aren't available" description="Chat isn't set up for your account. Please contact your account manager." />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import StateBanner from '@/components/common/StateBanner.vue'
import { usePortal } from '@/composables/portal/usePortal'

const route = useRoute()
const { data, load } = usePortal()
onMounted(() => load())

const available = computed(() => data.value?.chat_enabled !== false)
const src = computed(() => (route.query.room ? `/chat/${encodeURIComponent(String(route.query.room))}` : '/chat'))
</script>
