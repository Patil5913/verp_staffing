<template>
  <div class="mx-auto flex max-w-5xl flex-col gap-4 px-3 py-5 md:px-6">
    <AppSkeleton v-if="loading && !data" variant="block" height="12rem" />
    <StateBanner v-else-if="error" icon="triangle-alert" title="Your portal isn't available" :description="error" />
    <StateBanner v-else-if="!list.length" icon="wrench" title="No technical services" description="This page appears once you have a technical service with us." />
    <template v-else>
      <p v-if="true" class="text-p-sm text-app-text-muted">Sessions, support and progress from our technical team.</p>
      <ServiceCard v-for="(s, i) in list" :key="i" :service="s" />
    </template>
  </div>
</template>

<script setup>
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import ServiceCard from '@/components/portal/ServiceCard.vue'
import { onMounted } from 'vue'
import { usePortal } from '@/composables/portal/usePortal'

const { data, loading, error, technicalServices, load } = usePortal()
const list = technicalServices
onMounted(() => load())
</script>
