<template>
  <div class="flex min-h-screen items-start justify-center bg-app-bg px-4 py-10">
    <div class="w-full max-w-3xl">
      <div class="mb-6 text-center">
        <h1 class="text-xl font-semibold text-app-text">Choose your plan</h1>
        <p class="mt-1 text-p-sm text-app-text-muted">{{ subtitle }}</p>
      </div>

      <div v-if="loading" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

      <div v-else class="flex flex-col gap-5">
        <div v-if="errorMessage" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-p-sm text-red-700 dark:text-red-300">{{ errorMessage }}</div>
        <div v-if="notice" class="rounded-lg border border-app-border bg-app-panel-2 p-3 text-p-sm text-app-text">{{ notice }}</div>

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
            <p class="mt-1 text-p-sm text-app-text-muted">{{ p.description }}</p>
            <ul class="mt-3 space-y-1 text-p-sm text-app-text">
              <li v-for="l in p.limitEntries" :key="l.limitCode">{{ l.value }} {{ l.unit }} <span class="text-app-text-muted">· {{ label(l.limitCode) }}</span></li>
              <li v-for="a in p.appEntries" :key="a.appName">{{ a.appName }}</li>
            </ul>
          </button>
        </div>

        <div v-if="catalogue.addons.length" class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
          <h2 class="mb-3 text-p-base font-semibold text-app-text">Add-ons</h2>
          <label v-for="a in catalogue.addons" :key="a.id" class="flex cursor-pointer items-center justify-between py-1.5 text-p-sm text-app-text">
            <span class="flex items-center gap-2">
              <input v-model="selectedAddons" type="checkbox" :value="a.id" />
              {{ addonLabel(a) }}
            </span>
            <span class="text-app-text-muted">+ {{ money(a.price, currency) }}</span>
          </label>
        </div>

        <div class="flex items-center justify-between rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
          <div>
            <div class="text-p-xs text-app-text-muted">Estimated total</div>
            <div class="text-lg font-semibold text-app-text">{{ money(total, currency) }}</div>
            <div class="text-p-xs text-app-text-muted">Final pricing, discounts and tax are shown on the payment page.</div>
          </div>
          <AppButton :disabled="!selectedPlan" :loading="paying" @click="pay">Continue to payment</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Shown to everyone until the site holds a valid, unexpired subscription (router guard on
// window.subscription_status). Pick a plan + add-ons, go to the subscription dashboard to pay,
// come back here: we ask the server to pull and verify the signed entitlement, and only then
// reload into the app. Coming back without paying leaves the site blocked.
import { computed, onMounted, reactive, ref } from 'vue'
import { call, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { normalizeError } from '@/utils/common/errors'

const API = 'verp_staffing.core.license.api'

const loading = ref(true)
const paying = ref(false)
const errorMessage = ref('')
const notice = ref('')
const catalogue = reactive({ plans: [], addons: [] })
const selectedPlanId = ref('')
const selectedAddons = ref([])

const selectedPlan = computed(() => catalogue.plans.find((p) => p.id === selectedPlanId.value))
const currency = computed(() => selectedPlan.value?.currency?.code || catalogue.plans[0]?.currency?.code || 'USD')
const total = computed(() => {
  if (!selectedPlan.value) return 0
  const addons = catalogue.addons.filter((a) => selectedAddons.value.includes(a.id))
  return addons.reduce((sum, a) => sum + Number(a.price), Number(selectedPlan.value.basePrice))
})
const subtitle = computed(() =>
  window.subscription_status === 'Expired'
    ? 'Your subscription has expired. Renew to continue.'
    : 'A subscription is required before this site can be set up.',
)

const LIMIT_LABELS = { User: 'Users', Storage: 'Storage' }
const label = (code) => LIMIT_LABELS[code] || code
const money = (v, cur) => `${cur} ${Number(v).toFixed(2)}`
const addonLabel = (a) => (a.type === 'app' ? `${a.appName} app` : `+${a.value} ${label(a.limitCode).toLowerCase()}`)

onMounted(async () => {
  try {
    // Back from the dashboard: the webhook may beat us here, or may not have landed yet — poll
    // the recovery endpoint (POST /api/client/sync) a few times before giving up on this load.
    const returning = new URLSearchParams(window.location.search).get('checkout') === 'return'
    let status = await call(returning ? `${API}.refresh_status` : `${API}.get_status`)
    for (let attempt = 0; returning && status.status !== 'Active' && attempt < 3; attempt++) {
      await new Promise((r) => setTimeout(r, 1500))
      status = await call(`${API}.refresh_status`)
    }
    if (status.status === 'Active') return enterApp()
    if (status.status === 'Sync Error') errorMessage.value = status.last_sync_error || 'Could not reach the subscription dashboard.'
    else if (returning) notice.value = 'Payment has not been confirmed yet. If you have completed payment, reload this page in a moment.'
    Object.assign(catalogue, await call(`${API}.get_plans`))
  } catch (e) {
    errorMessage.value = serverMessage(e) || 'Could not load subscription plans.'
  } finally {
    loading.value = false
  }
})

// frappe.throw()'d text (e.g. "Invalid entitlement signature", "Cannot reach the subscription
// dashboard...") lands in normalizeError(e).messages; .message is a generic fallback that
// doesn't carry it, so prefer the first real message when there is one.
function serverMessage(e) {
  const err = normalizeError(e)
  return err.messages?.[0] || err.message
}

async function pay() {
  errorMessage.value = ''
  paying.value = true
  try {
    const { url } = await call(`${API}.start_checkout`, {
      plan_id: selectedPlanId.value,
      addon_ids: JSON.stringify(selectedAddons.value),
    })
    window.location.href = url
  } catch (e) {
    errorMessage.value = serverMessage(e) || 'Could not start checkout.'
    paying.value = false
  }
}

// Full reload: boot data (subscription_status, setup_complete) and cached state are read fresh.
function enterApp() {
  window.location.href = '/verp'
}
</script>
