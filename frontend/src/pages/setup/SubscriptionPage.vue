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

        <!-- Quantities only, no pricing shown here — and not yet applied by checkout at all (see
             start_checkout's note); central only copies the plan's own limits as-is today. -->
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
// Shown to everyone until the site holds a valid, unexpired subscription (router guard on
// window.subscription_status). Pick a plan, optionally more users / Storage / BackupFrequency
// than it includes, go to the subscription dashboard to pay, come back here: we ask the server
// to pull and verify the signed entitlement, and only then reload into the app. Coming back
// without paying leaves the site blocked.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { call, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { normalizeError } from '@/utils/common/errors'

const API = 'verp_staffing.core.license.api'
const LIMIT_LABELS = { Storage: 'Storage', BackupFrequency: 'Backup Frequency' }

const loading = ref(true)
const paying = ref(false)
const errorMessage = ref('')
const notice = ref('')
const catalogue = reactive({ plans: [] })
const selectedPlanId = ref('')
// No "extra users" input: the entitlement/checkout data model has no seat-count concept at all
// (no field for it anywhere in the Plan/SubscriptionVersion/entitlement shapes) — only per-limit
// quantities (Storage, BackupFrequency) exist to even ask the admin about.
const addons = reactive({ limitQuantities: {} })

const selectedPlan = computed(() => catalogue.plans.find((p) => p.id === selectedPlanId.value))
const subtitle = computed(() =>
  window.subscription_status === 'Expired'
    ? 'Your subscription has expired. Renew to continue.'
    : 'A subscription is required before this site can be set up.',
)

// Reset the quantity inputs to the newly selected plan's own limits, not whatever was typed for
// a previous plan's (possibly different) limit codes.
watch(selectedPlan, (p) => {
  addons.limitQuantities = Object.fromEntries((p?.limitEntries || []).map((l) => [l.limitCode, 0]))
})

const label = (code) => LIMIT_LABELS[code] || code
const money = (v, cur) => `${cur.code} ${Number(v).toFixed(2)}`

onMounted(async () => {
  try {
    // Back from the dashboard: the payment_confirmed webhook may beat us here, or may not have
    // landed yet — poll the recovery endpoint (POST /api/client/sync) a few times before giving up.
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
// dashboard...") lands in normalizeError(e).messages; .message already falls back to it, this
// just makes the intent explicit at each call site.
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
      limit_quantities: JSON.stringify(addons.limitQuantities),
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
