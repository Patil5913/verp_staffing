<template>
  <div class="flex min-h-screen items-start justify-center bg-app-bg px-4 py-10">
    <div class="w-full max-w-3xl">
      <div class="mb-6 text-center">
        <h1 class="text-xl font-semibold text-app-text">Subscription</h1>
        <p class="mt-1 text-p-sm text-app-text-muted">{{ subtitle }}</p>
        <router-link v-if="status.status === 'Active'" to="/" class="mt-3 inline-block text-p-sm font-medium text-app-primary hover:underline">
          &larr; Back to dashboard
        </router-link>
      </div>

      <div v-if="loading" class="flex justify-center py-16"><LoadingIndicator class="h-6 w-6 text-app-text-muted" /></div>

      <div v-else-if="!isAdmin" class="rounded-xl border border-app-border bg-app-panel p-6 text-center text-p-sm text-app-text">
        This site's subscription is not active. Please contact your administrator.
      </div>

      <div v-else class="flex flex-col gap-5">
        <div v-if="errorMessage" class="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-p-sm text-red-700 dark:text-red-300">{{ errorMessage }}</div>
        <div v-if="notice" class="rounded-lg border border-app-border bg-app-panel-2 p-3 text-p-sm text-app-text">{{ notice }}</div>

        <!-- Current entitlement (the verified signed payload). Shown whenever the site has one. -->
        <div v-if="status.plan" class="rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-p-xs font-medium uppercase tracking-wide text-app-text-muted">Plan</div>
              <div class="text-p-base font-semibold text-app-text">{{ status.plan }}</div>
            </div>
            <span class="rounded-full px-3 py-1 text-p-xs font-semibold" :class="statusClass">{{ status.status }}</span>
          </div>

          <dl class="mt-4 grid grid-cols-1 gap-3 text-p-sm sm:grid-cols-2">
            <div>
              <dt class="text-app-text-muted">Expires</dt>
              <dd class="text-app-text">{{ formatDate(status.expires_at) }}<span v-if="daysLeft !== null" class="text-app-text-muted"> ({{ daysLeft }} days left)</span></dd>
            </div>
            <div>
              <dt class="text-app-text-muted">Last verified</dt>
              <dd class="text-app-text">{{ formatDate(status.last_synced_at) }}</dd>
            </div>
            <div>
              <dt class="text-app-text-muted">Apps</dt>
              <dd class="text-app-text">{{ status.enabled_apps.join(', ') || '—' }}</dd>
            </div>
            <div>
              <dt class="text-app-text-muted">Limits</dt>
              <dd class="text-app-text">
                <div v-for="(value, code) in status.limits" :key="code">{{ label(code) }}: {{ value }}</div>
                <div v-if="!Object.keys(status.limits).length">—</div>
              </dd>
            </div>
          </dl>

          <div class="mt-5 flex flex-wrap gap-2">
            <AppButton variant="outline" :loading="refreshing" @click="refresh">Refresh status</AppButton>
            <AppButton v-if="!showPlans" @click="showPlans = true">Renew or change plan</AppButton>
          </div>
        </div>

        <!-- Plan picker: for a new purchase, a renewal, or when the admin asks to change plan. -->
        <template v-if="showPlans || !status.plan">
          <div v-if="!status.plan" class="text-p-sm text-app-text-muted">
            A subscription is required before this site can be set up.
          </div>

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

          <!-- Quantities only, no pricing shown here. Checkout does not apply them yet (see start_checkout). -->
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

          <div class="flex items-center justify-end gap-2 rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
            <AppButton v-if="showPlans && status.plan" variant="outline" @click="showPlans = false">Cancel</AppButton>
            <AppButton :disabled="!selectedPlan" :loading="paying" @click="pay">Continue to payment</AppButton>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
// Subscription page for System Managers. While the site is not Active it is where the admin is
// sent (router guard on window.subscription_status), and it is also reachable while Active to see
// the current entitlement and renew. Payment happens on the subscription dashboard; coming back
// here pulls and verifies the signed entitlement (refresh_status) before the site opens again.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { call, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { normalizeError } from '@/utils/common/errors'
import { hasRole } from '@/utils/common/roles'

const API = 'verp_staffing.core.license.api'
// Subtitle per status: central's codes (stored as reported) and the site's own states.
const SUBTITLES = {
  Active: 'This site is subscribed.',
  Expired: 'Your subscription has expired. Renew to continue.',
  EXPIRED: 'Your subscription has expired. Renew to continue.',
  SUSPENDED: 'This subscription has been suspended. Renew or contact your administrator to continue.',
  PENDING_PAYMENT: 'Payment for this subscription has not been completed yet. Finish checkout to continue.',
  NO_SUBSCRIPTION: 'A subscription is required before this site can be set up.',
  SITE_NOT_FOUND: 'This site is not registered with the subscription dashboard yet.',
  Invalid: 'The stored subscription could not be verified. Re-syncing with the subscription dashboard.',
  STALE: 'The subscription has not been confirmed recently. Re-syncing with the subscription dashboard.',
  PAST_DUE: 'Payment for this subscription is overdue. Pay to restore access.',
  CANCELLED: 'This subscription was cancelled. Choose a plan to subscribe again.',
  DRAFT: 'This subscription is not active yet. Finish checkout to continue.',
  'Sync Error': 'Could not reach the subscription dashboard. Try again shortly.',
  DEFAULT: 'A subscription is required before this site can be set up.',
}
const LIMIT_LABELS = { Storage: 'Storage', BackupFrequency: 'Backup Frequency', User: 'Users' }

const isAdmin = hasRole('System Manager')
const loading = ref(true)
const paying = ref(false)
const refreshing = ref(false)
const errorMessage = ref('')
const notice = ref('')
const showPlans = ref(false)
const status = reactive({ status: '', plan: null, enabled_apps: [], limits: {}, expires_at: null, last_synced_at: null, last_sync_error: null })
const catalogue = reactive({ plans: [] })
const selectedPlanId = ref('')
const addons = reactive({ limitQuantities: {} })

const selectedPlan = computed(() => catalogue.plans.find((p) => p.id === selectedPlanId.value))
const subtitle = computed(() => SUBTITLES[status.status] || SUBTITLES.DEFAULT)
const statusClass = computed(() =>
  status.status === 'Active'
    ? 'bg-green-500/15 text-green-700 dark:text-green-300'
    : 'bg-red-500/15 text-red-700 dark:text-red-300',
)
const daysLeft = computed(() => {
  if (!status.expires_at) return null
  return Math.ceil((new Date(status.expires_at) - new Date()) / 86400000)
})

// Reset the quantity inputs to the newly selected plan's own limit codes.
watch(selectedPlan, (p) => {
  addons.limitQuantities = Object.fromEntries((p?.limitEntries || []).map((l) => [l.limitCode, 0]))
})

const label = (code) => LIMIT_LABELS[code] || code
const money = (v, cur) => `${cur.code} ${Number(v).toFixed(2)}`
const formatDate = (v) => (v ? new Date(v).toLocaleString() : '—')

function applyStatus(s) {
  Object.assign(status, s)
  if (s.last_sync_error) errorMessage.value = s.last_sync_error
}

onMounted(async () => {
  if (!isAdmin) {
    loading.value = false
    return
  }
  try {
    // Coming back from the dashboard, or the stored entitlement failed verification: pull the
    // current entitlement from the dashboard. The payment_confirmed webhook may not have landed
    // yet, so poll a few times when returning from checkout.
    const returning = new URLSearchParams(window.location.search).get('checkout') === 'return'
    let s = await call(`${API}.get_status`)
    if (returning || s.status === 'Invalid' || s.status === 'STALE') {
      s = await call(`${API}.refresh_status`)
      for (let attempt = 0; returning && s.status !== 'Active' && attempt < 3; attempt++) {
        await new Promise((r) => setTimeout(r, 1500))
        s = await call(`${API}.refresh_status`)
      }
    }
    applyStatus(s)
    // Fresh site: the setup wizard is the next step, so continue straight into it.
    if (s.status === 'Active' && window.setup_complete === false) return enterApp()
    if (returning && s.status === 'Active') notice.value = 'Payment confirmed. Your subscription is active.'
    if (returning && s.status !== 'Active') notice.value = 'Payment has not been confirmed yet. If you have completed payment, refresh in a moment.'
    Object.assign(catalogue, await call(`${API}.get_plans`))
  } catch (e) {
    errorMessage.value = serverMessage(e) || 'Could not load the subscription.'
  } finally {
    loading.value = false
  }
})

// Manual re-sync from the dashboard. Keeps the current entitlement on screen if the dashboard
// can't be reached, and shows what went wrong.
async function refresh() {
  errorMessage.value = ''
  refreshing.value = true
  try {
    applyStatus(await call(`${API}.refresh_status`))
    if (status.status === 'Active') notice.value = 'Subscription is up to date.'
  } catch (e) {
    errorMessage.value = serverMessage(e) || 'Could not refresh the subscription.'
  } finally {
    refreshing.value = false
  }
}

// frappe.throw()'d text (e.g. "Invalid entitlement signature", "Cannot reach the subscription
// dashboard...") lands in normalizeError(e).messages; .message already falls back to it.
function serverMessage(e) {
  const err = normalizeError(e)
  return err.messages?.[0] || err.message
}

// Full reload: the router then sends a fresh site on to the setup wizard.
function enterApp() {
  window.location.href = '/verp'
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

</script>
