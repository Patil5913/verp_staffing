<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-4 px-6 py-8">
    <StateBanner
      icon="alert-triangle"
      title="Page not found"
      :description="`There's nothing at ${path}.`"
    >
      <Button variant="solid" theme="blue" @click="router.push('/')">
        Go to Dashboard
      </Button>
    </StateBanner>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'

const route = useRoute()
const router = useRouter()
const path = computed(() => route.fullPath)
</script>
