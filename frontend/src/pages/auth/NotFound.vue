<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-4 px-3 md:px-6 py-8">
    <StateBanner
      icon="alert-triangle"
      title="Page not found"
      :description="`There's nothing at ${path}.`"
    >
      <AppButton variant="solid" theme="blue" @click="router.push('/')">
        Go to Dashboard
      </AppButton>
    </StateBanner>
  </div>
</template>

<script setup>
import AppButton from '@/components/ui/AppButton.vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBanner from '@/components/common/StateBanner.vue'

const route = useRoute()
const router = useRouter()
const path = computed(() => route.fullPath)
</script>
