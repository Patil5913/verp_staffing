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
        </div>
        <div v-else class="text-p-sm text-app-text-muted">No subscription on record yet.</div>

        <div class="flex flex-wrap items-center justify-end gap-2 rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
          <AppButton variant="outline" :loading="refreshing" @click="refresh">Refresh status</AppButton>
          <AppButton @click="$router.push('/site-subscription/plans')">View Plans</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Subscription STATUS page only — the plan/add-on picker lives at /site-subscription/plans
// (SubscriptionPlansPage.vue). The router sends a not-yet-licensed site straight to that plans
// page instead of here (see NO_LICENSE_STATES in router.js); this page is for a site that has a
// license but isn't Active (Suspended/Expired/...), or an Active site's admin checking status.
//
// No "?checkout=return" query is read any more: this page always asks the server for the latest
// signed entitlement (refresh_status) on open, whether that's a return from payment or just a
// normal visit, so there's nothing to distinguish.
import { computed, onMounted, reactive, ref } from 'vue'
import { call, LoadingIndicator } from 'frappe-ui'
import AppButton from '@/components/ui/AppButton.vue'
import { normalizeError } from '@/utils/common/errors'
import { hasRole } from '@/utils/common/roles'
import { useRouter } from 'vue-router'

const API = 'verp_staffing.core.license.api'
// Kept in sync with router.js's own copy.
const NO_LICENSE_STATES = ['Pending', 'NO_SUBSCRIPTION', 'SITE_NOT_FOUND']
// Subtitle per status: central's codes (stored as reported) and the site's own states.
const SUBTITLES = {
  Active: 'This site is subscribed.',
  Expired: 'Your subscription has expired. Renew to continue.',
  EXPIRED: 'Your subscription has expired. Renew to continue.',
  SUSPENDED: 'This subscription has been suspended. Renew or contact your administrator to continue.',
  PENDING_PAYMENT: 'Payment for this subscription has not been completed yet. Finish checkout to continue.',
  Invalid: 'The stored subscription could not be verified. Re-syncing with the subscription dashboard.',
  STALE: 'The subscription has not been confirmed recently. Re-syncing with the subscription dashboard.',
  PAST_DUE: 'Payment for this subscription is overdue. Pay to restore access.',
  CANCELLED: 'This subscription was cancelled. Choose a plan to subscribe again.',
  DRAFT: 'This subscription is not active yet. Finish checkout to continue.',
  'Sync Error': 'Could not reach the subscription dashboard. Try again shortly.',
  DEFAULT: 'A subscription is required before this site can be set up.',
}
const LIMIT_LABELS = { Storage: 'Storage', BackupFrequency: 'Backup Frequency', User: 'Users' }

const router = useRouter()
const isAdmin = hasRole('System Manager')
const loading = ref(true)
const refreshing = ref(false)
const errorMessage = ref('')
const notice = ref('')
const status = reactive({ status: '', plan: null, enabled_apps: [], limits: {}, expires_at: null, last_synced_at: null, last_sync_error: null })

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

const label = (code) => LIMIT_LABELS[code] || code
const formatDate = (v) => (v ? new Date(v).toLocaleString() : '—')

function applyStatus(s) {
  Object.assign(status, s)
  if (s.last_sync_error) errorMessage.value = s.last_sync_error
}

// frappe.throw()'d text (e.g. "Invalid entitlement signature") lands in
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
    // Always pulls from the dashboard on open — covers a return from payment, webhook lag, or a
    // stale/invalid stored state, without needing a query-string flag to tell them apart.
    const s = await call(`${API}.refresh_status`)
    applyStatus(s)
    // Fresh site: the setup wizard is the next step, so continue straight into it.
    if (s.status === 'Active' && window.setup_complete === false) return enterApp()
    if (NO_LICENSE_STATES.includes(s.status)) return router.replace('/site-subscription/plans')
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
  notice.value = ''
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

// Full reload: the router then sends a fresh site on to the setup wizard.
function enterApp() {
  window.location.href = '/verp'
}
</script>
