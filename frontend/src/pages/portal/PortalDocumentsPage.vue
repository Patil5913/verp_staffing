<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-4 px-3 py-5 md:px-6">
    <AppSkeleton v-if="loading && !data" variant="block" height="10rem" />
    <StateBanner v-else-if="error" icon="triangle-alert" title="Your portal isn't available" :description="error" />
    <StateBanner v-else-if="data && !data.lead_documents.length" icon="file-text" title="No documents to show" />
    <SectionCard v-else-if="data" title="Your documents" subtitle="Upload or replace them any time. Max 1 MB each.">
      <PortalDocumentList />
    </SectionCard>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import PortalDocumentList from '@/components/portal/PortalDocumentList.vue'
import { usePortal } from '@/composables/portal/usePortal'

const { data, loading, error, load } = usePortal()
onMounted(() => load())
</script>
