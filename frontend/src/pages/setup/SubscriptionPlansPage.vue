<template>
  <div class="flex min-h-screen items-start justify-center bg-app-bg px-4 py-10">
    <div class="w-full max-w-3xl">
      <div class="mb-6 text-center">
        <h1 class="text-xl font-semibold text-app-text">Choose a plan</h1>
        <p class="mt-1 text-p-sm text-app-text-muted">Pricing for anything selected here is shown on the payment page.</p>
        <router-link to="/site-subscription" class="mt-3 inline-block text-p-sm font-medium text-app-primary hover:underline">
          &larr; Back to subscription status
        </router-link>
      </div>

      <div v-if="loading" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

      <div v-else-if="!isAdmin" class="rounded-xl border border-app-border bg-app-panel p-6 text-center text-p-sm text-app-text">
        This site's subscription is not active. Please contact your administrator.
      </div>

      <div v-else class="flex flex-col gap-5">
        <div v-if="errorMessage" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-p-sm text-red-700 dark:text-red-300">{{ errorMessage }}</div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <button
            v-for="p in catalogue.plans" :key="p.id" type="button"
            class="rounded-xl border p-5 text-left shadow-sm transition"
            :class="selectedPlanId === p.id ? 'border-app-primary bg-app-panel ring-2 ring-app-primary/30' : 'border-app-border bg-app-panel hover:border-app-primary/50'"
            @click="selectedPlanId = p.id"
          >
            <div class="flex items-baseline justify-between">
              <span class="text-p-base font-semibold text-app-text">{{ p.planName }}</span>
              <span class="text-p-sm text-app-text-muted">{{ money(p.basePrice, p.currency) }} / {{ p.billingCycle.toLowerCase() }}</span>
            </div>
            <div v-if="p.appEntries.length" class="mt-3">
              <div class="text-p-xs font-medium uppercase tracking-wide text-app-text-muted">Apps included</div>
              <ul class="mt-1 space-y-0.5 text-p-sm text-app-text">
                <li v-for="a in p.appEntries" :key="a.id">{{ a.appName }}</li>
              </ul>
            </div>
            <div v-if="p.limitEntries.length" class="mt-3">
              <div class="text-p-xs font-medium uppercase tracking-wide text-app-text-muted">Limits</div>
              <ul class="mt-1 space-y-0.5 text-p-sm text-app-text">
                <li v-for="l in p.limitEntries" :key="l.id">{{ label(l.limitCode) }}: {{ l.value }} {{ l.unit.unitName }}</li>
              </ul>
            </div>
          </button>
        </div>

        <!-- Quantities only, no pricing shown here. Checkout does not apply them yet (see
             core/license/client.py's start_checkout). -->
        <div v-if="selectedPlan && selectedPlan.limitEntries.length" class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
          <h2 class="mb-1 text-p-base font-semibold text-app-text">Add-ons</h2>
          <p class="mb-3 text-p-xs text-app-text-muted">Pricing for anything added here is shown on the payment page.</p>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <AppInput
              v-for="l in selectedPlan.limitEntries" :key="l.id"
              type="number" :label="`Additional ${label(l.limitCode)} (${l.unit.unitName})`" min="0"
              v-model.number="addons.limitQuantities[l.limitCode]"
              :placeholder="`${l.value} included`"
            />
          </div>
        </div>

        <div class="flex items-center justify-end rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
          <AppButton :disabled="!selectedPlan" :loading="paying" @click="pay">Continue to payment</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Plan + add-on picker, split out of SubscriptionPage.vue so that page is only ever the status
// view. Reached either because the router sent a not-yet-licensed site straight here
// (NO_LICENSE_STATES in router.js), or because the admin clicked "View Plans" from the status
// page (to buy for the first time, renew, or change plan while Active).
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { call, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { normalizeError } from '@/utils/common/errors'
import { hasRole } from '@/utils/common/roles'

const API = 'verp_staffing.core.license.api'
const LIMIT_LABELS = { Storage: 'Storage', BackupFrequency: 'Backup Frequency', User: 'Users' }

const isAdmin = hasRole('System Manager')
const loading = ref(true)
const paying = ref(false)
const errorMessage = ref('')
const catalogue = reactive({ plans: [] })
const selectedPlanId = ref('')
const addons = reactive({ limitQuantities: {} })

const selectedPlan = computed(() => catalogue.plans.find((p) => p.id === selectedPlanId.value))

// Reset the quantity inputs to the newly selected plan's own limit codes.
watch(selectedPlan, (p) => {
  addons.limitQuantities = Object.fromEntries((p?.limitEntries || []).map((l) => [l.limitCode, 0]))
})

const label = (code) => LIMIT_LABELS[code] || code
const money = (v, cur) => `${cur.code} ${Number(v).toFixed(2)}`

// frappe.throw()'d text (e.g. "Cannot reach the subscription dashboard...") lands in
// normalizeError(e).messages; .message already falls back to it.
function serverMessage(e) {
  const err = normalizeError(e)
  return err.messages?.[0] || err.message
}

onMounted(async () => {
  if (!isAdmin) {
    loading.value = false
    return
  }
  try {
    Object.assign(catalogue, await call(`${API}.get_plans`))
  } catch (e) {
    errorMessage.value = serverMessage(e) || 'Could not load subscription plans.'
  } finally {
    loading.value = false
  }
})

async function pay() {
  errorMessage.value = ''
  paying.value = true
  try {
    const { url } = await call(`${API}.start_checkout`, {
      plan_id: selectedPlanId.value,
      limit_quantities: JSON.stringify(addons.limitQuantities),
    })
    window.location.href = url
  } catch (e) {
    errorMessage.value = serverMessage(e) || 'Could not start checkout.'
    paying.value = false
  }
}
</script>
