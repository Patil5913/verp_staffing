<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-8">
    <StateBanner icon="lock" title="You don't have access to this page" :description="description">
      <AppButton variant="solid" theme="blue" @click="router.push('/')">Go to Dashboard</AppButton>
    </StateBanner>
  </div>
</template>

<script setup>
import AppButton from '@/components/common/AppButton.vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBanner from '@/components/common/StateBanner.vue'

const route = useRoute()
const router = useRouter()

const description = computed(() => {
  const from = route.query.from
  return from ? `Your roles don't include access to ${from}. Ask an administrator if you need it.` : 'Your roles don\'t include access to it. Ask an administrator if you need it.'
})
</script>
