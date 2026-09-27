<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
    <div class="w-full max-w-md rounded-2xl border border-app-border bg-app-panel p-6 shadow-xl">
      <h2 class="text-lg font-semibold text-app-text">{{ title }}</h2>
      <p class="mt-2 text-p-sm text-app-text-muted">{{ message }}</p>
      <div class="mt-5 flex justify-end">
        <AppButton icon="arrow-right" @click="go">{{ buttonLabel }}</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
// Blocks every other portal page while the candidate details form is open
// (lock_form = 0, must_fill) and/or a sent agreement is still unsigned.
// Checked again on each route change; see usePortalGate for the shared state.
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import { usePortalGate } from '@/composables/portal/usePortalGate'

const route = useRoute()
const router = useRouter()
const { mustFillForm, mustSignAgreement, blocked, isAllowedPath, gateTarget, refresh } = usePortalGate()

const onAllowedPage = computed(() => isAllowedPath(route.path))
const show = computed(() => blocked.value && !onAllowedPage.value)

const title = computed(() => (mustFillForm.value ? 'Candidate details needed' : 'Agreement needs your signature'))
const message = computed(() =>
  mustFillForm.value
    ? 'Please fill in your candidate details so we can continue with your services.'
    : 'Please review and sign your agreement before continuing.',
)
const buttonLabel = computed(() => (mustFillForm.value ? 'Fill details' : 'Review agreement'))

watch(() => route.path, refresh, { immediate: true })
const go = () => router.push(gateTarget.value)
</script>
