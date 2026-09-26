<template>
  <div class="mx-auto flex max-w-3xl flex-col gap-4 px-3 py-5 md:px-6">
    <AppSkeleton v-if="loading" variant="block" height="8rem" />
    <StateBanner v-else-if="error" icon="triangle-alert" title="Couldn't load your agreements" :description="error" />
    <StateBanner v-else-if="!items.length" icon="file-signature" title="No agreements yet" description="When we send you an agreement to sign, it will appear here." />

    <template v-else>
      <div>
        <h1 class="text-xl font-semibold text-app-text">Your agreements</h1>
        <p class="text-p-sm text-app-text-muted">
          {{ pending.length ? `${pending.length} waiting for your signature` : 'Nothing is waiting for your signature.' }}
        </p>
      </div>

      <div v-for="a in items" :key="a.name" class="flex flex-col gap-3 rounded-2xl border bg-app-panel p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between" :class="a.needs_signature ? 'border-amber-400/60' : 'border-app-border'">
        <div class="flex min-w-0 items-start gap-3">
          <span class="flex size-10 shrink-0 items-center justify-center rounded-xl" :class="a.needs_signature ? 'bg-amber-500/15 text-amber-600' : a.status === 'Fully Signed' ? 'bg-green-500/15 text-green-600' : 'bg-app-panel-2 text-app-text-muted'">
            <span :class="a.needs_signature ? 'lucide-pen-tool' : a.status === 'Fully Signed' ? 'lucide-badge-check' : 'lucide-clock'" class="size-5" />
          </span>
          <div class="min-w-0">
            <p class="truncate text-p-base font-medium text-app-text">{{ a.title || a.name }}</p>
            <p class="mt-0.5 flex flex-wrap items-center gap-x-2 text-p-xs text-app-text-muted">
              <span v-if="a.sales_order">{{ a.sales_order }}</span>
              <span>Sent {{ formatDatetime(a.creation) }}</span>
            </p>
            <div class="mt-1.5"><DocStatusBadge :status="a.needs_signature ? 'Pending' : a.status === 'Fully Signed' ? 'Signed' : 'Awaiting others'" /></div>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2 sm:justify-end">
          <AppButton v-if="a.needs_signature" icon="pen-tool" @click="router.push(`/portal/agreements/${a.name}`)">Review &amp; sign</AppButton>
          <a v-if="a.signed_pdf" :href="a.signed_pdf" target="_blank" rel="noopener"><AppButton variant="outline" size="sm" icon="download">Signed copy</AppButton></a>
          <a v-if="a.certificate_pdf" :href="a.certificate_pdf" target="_blank" rel="noopener"><AppButton variant="outline" size="sm" icon="badge-check">Certificate</AppButton></a>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// The customer's agreements, inside their portal - sign here instead of via an emailed link.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import StateBanner from '@/components/common/StateBanner.vue'
import { formatDatetime } from '@/utils/list/formatValue'
import { normalizeError } from '@/utils/common/errors'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const error = ref('')
const pending = computed(() => items.value.filter((a) => a.needs_signature))

onMounted(async () => {
  try {
    items.value = (await call('verp_staffing.esign.portal.list_my_agreements')) || []
  } catch (e) {
    error.value = normalizeError(e).message
  } finally {
    loading.value = false
  }
})
</script>
