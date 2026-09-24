<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
    <div class="w-full max-w-md rounded-2xl border border-app-border bg-app-panel p-6 shadow-xl">
      <h2 class="text-lg font-semibold text-app-text">Candidate details needed</h2>
      <p class="mt-2 text-p-sm text-app-text-muted">Please fill in your candidate details so we can continue with your services.</p>
      <div class="mt-5 flex justify-end">
        <AppButton icon="arrow-right" @click="go">Fill details</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
// Blocks every portal page except Candidate Details while the customer's
// form is open (lock_form = 0) and has fields to fill. Uses the tiny
// get_lock_state API, checked again on each route change.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'

const route = useRoute()
const router = useRouter()
const mustFill = ref(false)
const onFormPage = computed(() => route.path === '/portal/candidate-details')
const show = computed(() => mustFill.value && !onFormPage.value)

watch(
  () => route.path,
  async () => {
    try {
      mustFill.value = !!(await call('verp_staffing.www.candidate_details.get_lock_state'))?.must_fill
    } catch {
      mustFill.value = false
    }
  },
  { immediate: true },
)
const go = () => router.push('/portal/candidate-details')
</script>
